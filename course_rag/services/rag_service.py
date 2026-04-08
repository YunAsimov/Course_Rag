import hashlib
import json
import os
import re
import threading
from pathlib import Path
from typing import Optional

from course_rag.core.config_handler import (
    load_agent_config,
    load_chroma_config,
    load_prompts_config,
    load_rag_config,
)
from course_rag.core.file_handler import get_md5_file_hex, listdir_with_allowed_type, load_file_records
from course_rag.core.logger_handler import logger
from course_rag.core.path_tool import get_abs_path
from course_rag.services.rag_chunking import chunk_document
from course_rag.services.rag_generator import AnswerGenerator
from course_rag.services.rag_models import Chunk, Document
from course_rag.services.rag_retriever import (
    BM25Retriever,
    EmbeddingRetriever,
    HybridRetriever,
    OpenAICompatibleEmbeddingClient,
    PersistentChromaEmbeddingRetriever,
)


class RAGService:
    def __init__(self, data_dir: Optional[str] = None, build_async: bool = False):
        self.rag_conf = load_rag_config()
        self.retrieval_conf = load_chroma_config()
        self.prompts_conf = load_prompts_config()
        self.agent_conf = load_agent_config()

        configured_dir = data_dir or self.rag_conf["data_dir"]
        self.data_dir = self._resolve_data_dir(configured_dir)
        self.allowed_extensions = tuple(self.rag_conf["allowed_extensions"])
        self.vector_store_dir = self._resolve_vector_store_dir()
        self.index_cache_dir = self._resolve_index_cache_dir()

        self.documents: list[Document] = []
        self.chunks = []
        self.retriever: Optional[object] = None
        self.generator = AnswerGenerator(self.agent_conf, self.prompts_conf)
        self._index_lock = threading.RLock()
        self._build_lock = threading.Lock()
        self._build_thread: Optional[threading.Thread] = None
        self.index_summary = {
            "documents": 0,
            "chunks": 0,
            "data_dir": self._data_dir_label(),
            "backend": "initializing",
            "requested_backend": str(self.retrieval_conf["backend"] or "local_bm25").strip().lower(),
            "remote_llm_enabled": bool(self.agent_conf.get("enabled")),
            "embedding_model_name": self.rag_conf.get("embedding_model_name", ""),
            "embedding_retrieval_ready": False,
            "vector_store_backend": str(self.retrieval_conf.get("vector_store_backend", "none") or "none").strip().lower(),
            "vector_store_dir": self.vector_store_dir,
            "vector_collection_name": self._vector_collection_name(),
            "index_cache_hit": False,
            "bm25_cache_hit": False,
            "source_signature": "",
            "status": "indexing" if build_async else "idle",
            "ready": False,
            "indexing": bool(build_async),
            "message": "知识库索引构建中，请稍候。" if build_async else "知识库尚未构建。",
        }

        if build_async:
            self.start_background_index()
        else:
            self._build_index()

    def start_background_index(self) -> None:
        thread = self._build_thread
        if thread and thread.is_alive():
            return

        self._build_thread = threading.Thread(
            target=self._build_index,
            name=f"rag-index-{Path(self.data_dir).stem}",
            daemon=True,
        )
        self._build_thread.start()

    def _resolve_data_dir(self, data_dir: str) -> str:
        candidate = Path(data_dir)
        if candidate.is_absolute():
            return str(candidate.resolve())
        return str(Path(get_abs_path(data_dir)).resolve())

    def _data_dir_label(self) -> str:
        project_root = Path(get_abs_path(".")).resolve()
        try:
            return os.path.relpath(self.data_dir, project_root)
        except ValueError:
            return self.data_dir

    def _resolve_vector_store_dir(self) -> str:
        configured_dir = str(self.retrieval_conf.get("vector_store_dir", "storage/vector_store/chroma"))
        candidate = Path(configured_dir)
        if candidate.is_absolute():
            return str(candidate.resolve())
        return str(Path(get_abs_path(configured_dir)).resolve())

    def _vector_collection_name(self) -> str:
        raw_prefix = str(self.retrieval_conf.get("vector_collection_prefix", "course_rag")).strip().lower()
        prefix = re.sub(r"[^a-z0-9_-]+", "_", raw_prefix) or "course_rag"
        data_stem = re.sub(r"[^a-z0-9_-]+", "_", Path(self.data_dir).stem.lower()) or "data"
        data_hash = hashlib.md5(self.data_dir.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{data_stem}_{data_hash}"


    def _resolve_index_cache_dir(self) -> str:
        return str(Path(get_abs_path("storage/index_cache")).resolve())

    def _index_snapshot_path(self) -> Path:
        data_hash = hashlib.md5(self.data_dir.encode("utf-8")).hexdigest()[:12]
        return Path(self.index_cache_dir) / f"{data_hash}.json"

    def _build_source_manifest(self, file_paths: list[str]) -> list[dict]:
        project_root = Path(get_abs_path(".")).resolve()
        manifest: list[dict] = []
        for file_path in sorted(file_paths):
            stat = os.stat(file_path)
            manifest.append(
                {
                    "path": os.path.relpath(file_path, project_root).replace("\\", "/"),
                    "size": int(stat.st_size),
                    "mtime_ns": int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))),
                }
            )
        manifest.sort(key=lambda item: item["path"])
        return manifest

    def _build_source_signature(self, manifest: list[dict]) -> str:
        payload = {
            "snapshot_version": 1,
            "manifest": manifest,
            "chunk_size": self.retrieval_conf["chunk_size"],
            "chunk_overlap": self.retrieval_conf["chunk_overlap"],
            "allowed_extensions": sorted(self.allowed_extensions),
        }
        raw_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.md5(raw_text.encode("utf-8")).hexdigest()

    def _load_index_snapshot(self, source_signature: str) -> Optional[tuple[list[Document], list[Chunk], Optional[dict]]]:
        snapshot_path = self._index_snapshot_path()
        if not snapshot_path.is_file():
            return None
        try:
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[索引] 读取索引快照失败，转为实时构建: %s", exc)
            return None

        if payload.get("source_signature") != source_signature:
            return None

        try:
            documents = [
                Document(
                    doc_id=str(item["doc_id"]),
                    title=str(item["title"]),
                    source_path=str(item["source_path"]),
                    doc_type=str(item["doc_type"]),
                    text=str(item["text"]),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in payload.get("documents", [])
            ]
            chunks = [
                Chunk(
                    chunk_id=str(item["chunk_id"]),
                    doc_id=str(item["doc_id"]),
                    title=str(item["title"]),
                    source_path=str(item["source_path"]),
                    text=str(item["text"]),
                    order=int(item.get("order") or 0),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in payload.get("chunks", [])
            ]
        except Exception as exc:
            logger.warning("[索引] 索引快照格式无效，转为实时构建: %s", exc)
            return None

        return documents, chunks, payload.get("bm25_state")

    def _save_index_snapshot(self, source_signature: str, documents: list[Document], chunks: list[Chunk], bm25_state: Optional[dict]) -> None:
        snapshot_path = self._index_snapshot_path()
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source_signature": source_signature,
            "documents": [
                {
                    "doc_id": document.doc_id,
                    "title": document.title,
                    "source_path": document.source_path,
                    "doc_type": document.doc_type,
                    "text": document.text,
                    "metadata": document.metadata,
                }
                for document in documents
            ],
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "source_path": chunk.source_path,
                    "text": chunk.text,
                    "order": int(chunk.order),
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ],
            "bm25_state": bm25_state or {},
        }
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _build_retriever(self, chunks: list, skip_vector_sync: bool = False, bm25_state: Optional[dict] = None):
        requested_backend = str(self.retrieval_conf["backend"] or "local_bm25").strip().lower()
        vector_store_backend = str(self.retrieval_conf.get("vector_store_backend", "chroma") or "chroma").strip().lower()
        bm25_retriever = BM25Retriever(chunks, title_boost=self.retrieval_conf["title_boost"], cached_state=bm25_state)
        embedding_retriever: Optional[object] = None
        vector_collection_name = self._vector_collection_name()

        if requested_backend in {"hybrid_bm25_embedding", "hybrid", "embedding_only", "remote_embedding"}:
            embedding_client = OpenAICompatibleEmbeddingClient(
                base_url=self.agent_conf.get("base_url", ""),
                api_key=self.agent_conf.get("api_key", ""),
                model_name=self.rag_conf.get("embedding_model_name", ""),
                timeout_seconds=self.agent_conf.get("timeout_seconds", 30),
                batch_size=self.retrieval_conf["embedding_batch_size"],
            )
            if vector_store_backend in {"chroma", "persistent_chroma"}:
                embedding_retriever = PersistentChromaEmbeddingRetriever(
                    chunks,
                    embedding_client,
                    persist_directory=self.vector_store_dir,
                    collection_name=vector_collection_name,
                    min_score=self.retrieval_conf["embedding_min_score"],
                    sync_batch_size=self.retrieval_conf["vector_store_sync_batch_size"],
                    skip_sync=skip_vector_sync,
                )
                if not embedding_retriever.is_ready:
                    logger.warning(
                        "[索引] Chroma 持久化向量库未就绪，尝试回退到内存 embedding: %s",
                        getattr(embedding_retriever, "failure_reason", "unknown_error"),
                    )
                    embedding_retriever = EmbeddingRetriever(
                        chunks,
                        embedding_client,
                        min_score=self.retrieval_conf["embedding_min_score"],
                    )
            else:
                embedding_retriever = EmbeddingRetriever(
                    chunks,
                    embedding_client,
                    min_score=self.retrieval_conf["embedding_min_score"],
                )

        if requested_backend in {"embedding_only", "remote_embedding"}:
            if embedding_retriever and embedding_retriever.is_ready:
                retriever = embedding_retriever
            else:
                logger.warning("[索引] embedding_only 未就绪，回退到 BM25")
                retriever = bm25_retriever
        elif requested_backend in {"hybrid_bm25_embedding", "hybrid"}:
            retriever = HybridRetriever(
                bm25=bm25_retriever,
                embedding=embedding_retriever,
                bm25_weight=self.retrieval_conf["bm25_weight"],
                embedding_weight=self.retrieval_conf["embedding_weight"],
                rrf_k=self.retrieval_conf["rrf_k"],
                candidate_top_k=self.retrieval_conf["candidate_top_k"],
            )
        else:
            retriever = bm25_retriever

        return retriever, {
            "requested_backend": requested_backend,
            "actual_backend": getattr(retriever, "backend_name", requested_backend),
            "embedding_model_name": self.rag_conf.get("embedding_model_name", ""),
            "embedding_retrieval_ready": bool(embedding_retriever and embedding_retriever.is_ready),
            "bm25_cache_hit": bool(getattr(bm25_retriever, "cache_hit", False)),
            "bm25_state": bm25_retriever.export_state(),
            "embedding_failure_reason": getattr(embedding_retriever, "failure_reason", ""),
            "vector_store_backend": getattr(embedding_retriever, "vector_store_backend", "none"),
            "vector_store_dir": self.vector_store_dir,
            "vector_collection_name": vector_collection_name if embedding_retriever else "",
            "vector_sync_stats": getattr(embedding_retriever, "sync_stats", {}),
        }

    def _collect_index_data(self) -> tuple[list[Document], list, object, dict]:
        logger.info("[索引] 开始构建知识库索引: %s", self.data_dir)
        file_paths = listdir_with_allowed_type(self.data_dir, self.allowed_extensions)
        source_manifest = self._build_source_manifest(file_paths)
        source_signature = self._build_source_signature(source_manifest)

        snapshot = self._load_index_snapshot(source_signature)
        index_cache_hit = snapshot is not None
        bm25_state = None
        if snapshot:
            documents, chunks, bm25_state = snapshot
            doc_count = len(documents)
            chunk_count = len(chunks)
            logger.info("[索引] 文件未变化，复用本地索引快照: %s", self._index_snapshot_path())
        else:
            doc_count = 0
            chunk_count = 0
            documents = []
            chunks = []

            for file_path in file_paths:
                relative_path = os.path.relpath(file_path, get_abs_path("."))
                records = load_file_records(file_path)
                file_hash = get_md5_file_hex(file_path)
                file_has_chunks = False

                for record_index, record in enumerate(records, start=1):
                    text = (record.get("text") or "").strip()
                    if not text:
                        continue

                    metadata = record.get("metadata", {}).copy()
                    metadata.update({"md5": file_hash})
                    document = Document(
                        doc_id=f"{Path(file_path).stem}-{record_index}",
                        title=record.get("title") or Path(file_path).stem,
                        source_path=relative_path,
                        doc_type=Path(file_path).suffix.lower(),
                        text=text,
                        metadata=metadata,
                    )
                    document_chunks = chunk_document(
                        document,
                        chunk_size=self.retrieval_conf["chunk_size"],
                        chunk_overlap=self.retrieval_conf["chunk_overlap"],
                    )
                    if not document_chunks:
                        continue

                    documents.append(document)
                    chunks.extend(document_chunks)
                    chunk_count += len(document_chunks)
                    file_has_chunks = True

                if file_has_chunks:
                    doc_count += 1

        retriever, retrieval_status = self._build_retriever(chunks, skip_vector_sync=index_cache_hit, bm25_state=bm25_state)

        if (not index_cache_hit) or (index_cache_hit and not retrieval_status["bm25_cache_hit"]):
            self._save_index_snapshot(source_signature, documents, chunks, retrieval_status["bm25_state"])
        index_summary = {
            "documents": doc_count,
            "chunks": chunk_count,
            "data_dir": self._data_dir_label(),
            "backend": retrieval_status["actual_backend"],
            "requested_backend": retrieval_status["requested_backend"],
            "remote_llm_enabled": bool(self.agent_conf.get("enabled")),
            "embedding_model_name": retrieval_status["embedding_model_name"],
            "embedding_retrieval_ready": retrieval_status["embedding_retrieval_ready"],
            "vector_store_backend": retrieval_status["vector_store_backend"],
            "vector_store_dir": retrieval_status["vector_store_dir"],
            "vector_collection_name": retrieval_status["vector_collection_name"],
            "vector_sync_stats": retrieval_status["vector_sync_stats"],
            "index_cache_hit": index_cache_hit,
            "bm25_cache_hit": retrieval_status["bm25_cache_hit"],
            "source_signature": source_signature,
        }
        if retrieval_status["embedding_failure_reason"]:
            index_summary["embedding_failure_reason"] = retrieval_status["embedding_failure_reason"]
        logger.info(
            "[索引] 构建完成，文档 %s 份，切片 %s 个，检索后端 %s",
            doc_count,
            chunk_count,
            index_summary["backend"],
        )
        return documents, chunks, retriever, index_summary

    def _build_index(self) -> None:
        with self._build_lock:
            with self._index_lock:
                current_summary = self.index_summary.copy()
                current_summary.update(
                    {
                        "status": "indexing",
                        "ready": False,
                        "indexing": True,
                        "message": "知识库索引构建中，请稍候。",
                    }
                )
                self.index_summary = current_summary

            try:
                documents, chunks, retriever, index_summary = self._collect_index_data()
            except Exception as exc:
                logger.exception("[索引] 构建失败: %s", exc)
                with self._index_lock:
                    failed_summary = self.index_summary.copy()
                    failed_summary.update(
                        {
                            "status": "error",
                            "ready": bool(self.retriever),
                            "indexing": False,
                            "message": "知识库索引构建失败，请稍后重试。",
                            "index_error": str(exc),
                        }
                    )
                    self.index_summary = failed_summary
                return

            index_summary.update(
                {
                    "status": "ok",
                    "ready": True,
                    "indexing": False,
                    "message": "知识库已准备就绪。",
                }
            )
            with self._index_lock:
                self.documents = documents
                self.chunks = chunks
                self.retriever = retriever
                self.index_summary = index_summary

    def reload_index(self) -> dict:
        self._build_index()
        with self._index_lock:
            return self.index_summary.copy()

    def list_material_files(self) -> list[dict]:
        file_paths = listdir_with_allowed_type(self.data_dir, self.allowed_extensions)
        project_root = get_abs_path(".")
        materials: list[dict] = []

        for file_path in file_paths:
            file_stat = os.stat(file_path)
            relative_path = os.path.relpath(file_path, project_root)
            suffix = Path(file_path).suffix.lower()
            materials.append(
                {
                    "name": Path(file_path).name,
                    "title": Path(file_path).stem,
                    "path": relative_path,
                    "doc_type": suffix,
                    "size_bytes": file_stat.st_size,
                    "updated_at": file_stat.st_mtime,
                }
            )

        materials.sort(key=lambda item: (-item["updated_at"], item["name"].lower()))
        return materials

    def delete_material_file(self, relative_path: str) -> dict:
        clean_path = (relative_path or "").strip()
        if not clean_path:
            raise ValueError("缺少待删除的文件路径。")

        data_root = Path(self.data_dir).resolve()
        project_root = Path(get_abs_path(".")).resolve()
        material_path = (project_root / clean_path).resolve()

        if material_path != data_root and data_root not in material_path.parents:
            raise PermissionError("不允许删除资料目录之外的文件。")
        if not material_path.is_file():
            raise FileNotFoundError("目标文件不存在。")
        if material_path.suffix.lower() not in {extension.lower() for extension in self.allowed_extensions}:
            raise ValueError("该文件类型不在当前资料库允许范围内。")

        deleted_name = material_path.name
        material_path.unlink()
        stats = self.reload_index()
        return {
            "name": deleted_name,
            "path": os.path.relpath(material_path, project_root),
            "stats": stats,
        }

    def ask(self, question: str) -> dict:
        clean_question = question.strip()
        if not clean_question:
            return {
                "answer": "请输入一个具体问题，例如“为什么文本数据通常使用余弦相似度？”。",
                "mode": "validation",
                "sources": [],
            }

        with self._index_lock:
            retriever = self.retriever
            top_k = self.retrieval_conf["top_k"]
            min_score = self.retrieval_conf["min_score"]
            max_context_chars = self.retrieval_conf["max_context_chars"]
            chunk_count = len(self.chunks)
            indexing = bool(self.index_summary.get("indexing"))
            status_message = self.index_summary.get("message", "")

        if indexing:
            return {
                "question": clean_question,
                "answer": status_message or "知识库索引构建中，请稍候再提问。",
                "mode": "indexing",
                "sources": [],
            }

        if not retriever or chunk_count == 0:
            return {
                "answer": "当前用户的资料库还是空的。先上传课程资料，再进行提问。",
                "mode": "empty_index",
                "sources": [],
            }

        results = retriever.search(
            clean_question,
            top_k=top_k,
            min_score=min_score,
        )
        answer, mode = self.generator.generate(
            clean_question,
            results,
            max_context_chars=max_context_chars,
        )

        return {
            "question": clean_question,
            "answer": answer,
            "mode": mode,
            "sources": [
                {
                    "title": result.chunk.title,
                    "path": result.chunk.source_path,
                    "score": round(result.score, 3),
                    "snippet": result.chunk.text[:320].strip(),
                    "metadata": result.chunk.metadata,
                    "page_number": result.chunk.metadata.get("page_number"),
                    "section_heading": result.chunk.metadata.get("section_heading"),
                    "page_heading": result.chunk.metadata.get("page_heading"),
                    "retrieval_details": result.details,
                }
                for result in results
            ],
        }

    def get_ui_context(self) -> dict:
        if not self.index_summary.get("ready") and not self.index_summary.get("indexing"):
            self.start_background_index()
        with self._index_lock:
            stats = self.index_summary.copy()
        return {
            "app_name": self.rag_conf["app_name"],
            "suggested_questions": self.prompts_conf["suggested_questions"],
            "stats": stats,
            "allowed_extensions": list(self.allowed_extensions),
            "allowed_extensions_label": ", ".join(self.allowed_extensions),
        }


class UserRAGServiceManager:
    def __init__(self, store):
        self.store = store
        self.rag_conf = load_rag_config()
        self.allowed_extensions = tuple(self.rag_conf["allowed_extensions"])
        self.prompts_conf = load_prompts_config()
        self._services: dict[str, RAGService] = {}
        self._lock = threading.RLock()
        self._public_service = RAGService(data_dir=self.rag_conf["data_dir"], build_async=True)

    def get_public_context(self) -> dict:
        return self._public_service.get_ui_context()

    def get_service(self, username: str) -> RAGService:
        normalized = (username or "").strip()
        if not normalized:
            raise ValueError("用户名不能为空。")

        material_dir = self.store.get_user_material_dir(normalized).resolve()
        with self._lock:
            service = self._services.get(normalized)
            if service is None or Path(service.data_dir).resolve() != material_dir:
                service = RAGService(data_dir=str(material_dir), build_async=True)
                self._services[normalized] = service
        return service

    def reload_user_index(self, username: str) -> dict:
        self.store.sync_materials(username, self.allowed_extensions)
        service = self.get_service(username)
        return service.reload_index()

    def get_ui_context(self, username: str) -> dict:
        self.store.sync_materials(username, self.allowed_extensions)
        service = self.get_service(username)
        return service.get_ui_context()

    def ask(self, username: str, question: str) -> dict:
        service = self.get_service(username)
        return service.ask(question)

    def list_material_files(self, username: str) -> list[dict]:
        self.store.sync_materials(username, self.allowed_extensions)
        return self.store.list_materials(username, sync=False)

    def delete_material_file(self, username: str, relative_path: str) -> dict:
        service = self.get_service(username)
        result = service.delete_material_file(relative_path)
        self.store.sync_materials(username, self.allowed_extensions)
        result["stats"] = service.index_summary.copy()
        return result
