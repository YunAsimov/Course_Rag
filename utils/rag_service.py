import os
import threading
from pathlib import Path
from typing import Optional

from utils.config_handler import load_agent_config, load_chroma_config, load_prompts_config, load_rag_config
from utils.file_handler import get_md5_file_hex, listdir_with_allowed_type, load_file_records
from utils.logger_handler import logger
from utils.path_tool import get_abs_path
from utils.rag_chunking import chunk_document
from utils.rag_generator import AnswerGenerator
from utils.rag_models import Document
from utils.rag_retriever import BM25Retriever


class RAGService:
    def __init__(self):
        self.rag_conf = load_rag_config()
        self.retrieval_conf = load_chroma_config()
        self.prompts_conf = load_prompts_config()
        self.agent_conf = load_agent_config()

        self.data_dir = get_abs_path(self.rag_conf["data_dir"])
        self.allowed_extensions = tuple(self.rag_conf["allowed_extensions"])

        self.documents: list[Document] = []
        self.chunks = []
        self.retriever: Optional[BM25Retriever] = None
        self.generator = AnswerGenerator(self.agent_conf, self.prompts_conf)
        self.index_summary = {}
        self._index_lock = threading.RLock()

        self._build_index()

    def _collect_index_data(self) -> tuple[list[Document], list, BM25Retriever, dict]:
        logger.info("[索引] 开始构建知识库索引: %s", self.data_dir)
        file_paths = listdir_with_allowed_type(self.data_dir, self.allowed_extensions)

        doc_count = 0
        chunk_count = 0
        documents: list[Document] = []
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

        retriever = BM25Retriever(chunks, title_boost=self.retrieval_conf["title_boost"])
        index_summary = {
            "documents": doc_count,
            "chunks": chunk_count,
            "data_dir": self.data_dir,
            "backend": self.retrieval_conf["backend"],
            "remote_llm_enabled": bool(self.agent_conf.get("enabled")),
        }
        logger.info("[索引] 构建完成，文档 %s 份，切片 %s 个", doc_count, chunk_count)
        return documents, chunks, retriever, index_summary

    def _build_index(self) -> None:
        documents, chunks, retriever, index_summary = self._collect_index_data()
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
                "answer": "请输入一个具体问题，例如“为什么文本数据通常使用余弦相似度？”",
                "mode": "validation",
                "sources": [],
            }

        with self._index_lock:
            retriever = self.retriever
            top_k = self.retrieval_conf["top_k"]
            min_score = self.retrieval_conf["min_score"]
            max_context_chars = self.retrieval_conf["max_context_chars"]

        if not retriever:
            return {
                "answer": "检索器尚未初始化，无法回答问题。",
                "mode": "error",
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
                }
                for result in results
            ],
        }

    def get_ui_context(self) -> dict:
        with self._index_lock:
            stats = self.index_summary.copy()
        return {
            "app_name": self.rag_conf["app_name"],
            "suggested_questions": self.prompts_conf["suggested_questions"],
            "stats": stats,
            "allowed_extensions": list(self.allowed_extensions),
            "allowed_extensions_label": ", ".join(self.allowed_extensions),
        }
