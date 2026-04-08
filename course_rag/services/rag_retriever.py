import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import requests

from course_rag.core.logger_handler import logger
from course_rag.services.rag_models import Chunk, RetrievalResult

try:
    import chromadb
except ImportError:
    chromadb = None

ASCII_RE = re.compile(r"[a-z0-9_+\-]+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
TOKEN_STOPWORDS = {
    "为什",
    "什么",
    "请结",
    "结合",
    "合课",
    "课程",
    "程资",
    "资料",
    "料简",
    "简要",
    "要说",
    "说明",
    "一下",
    "一般",
    "怎么",
    "如何",
    "请问",
    "问题",
    "这个",
}


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens: list[str] = ASCII_RE.findall(lowered)

    for sequence in CJK_RE.findall(lowered):
        if len(sequence) == 1:
            tokens.append(sequence)
            continue

        tokens.extend(sequence[i : i + 2] for i in range(len(sequence) - 1))

    return [token for token in tokens if token and token not in TOKEN_STOPWORDS]


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def _dot_product(left: list[float], right: list[float]) -> float:
    return sum(l * r for l, r in zip(left, right))


def _serialize_chunk_text(chunk: Chunk) -> str:
    heading_parts = [
        part
        for part in (
            chunk.title,
            chunk.metadata.get("section_heading"),
            chunk.metadata.get("page_heading"),
        )
        if part
    ]
    if heading_parts:
        return "\n".join([*heading_parts, chunk.text])
    return chunk.text


def _stable_chunk_signature(chunk: Chunk, serialized_text: str) -> str:
    payload = {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "source_path": chunk.source_path,
        "order": int(chunk.order),
        "text": serialized_text,
        "metadata": {
            key: value
            for key, value in sorted(chunk.metadata.items())
            if isinstance(value, (str, int, float, bool)) and value not in ("", None)
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(encoded.encode("utf-8")).hexdigest()


class OpenAICompatibleEmbeddingClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: int = 30,
        batch_size: int = 16,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.model_name = (model_name or "").strip()
        self.timeout_seconds = int(timeout_seconds or 30)
        requested_batch_size = int(batch_size or 16)
        self.batch_size = max(1, min(10, requested_batch_size))
        if requested_batch_size != self.batch_size:
            logger.info(
                "[索引] embedding batch_size %s 超出当前接口限制，已调整为 %s",
                requested_batch_size,
                self.batch_size,
            )

    @property
    def is_ready(self) -> bool:
        return bool(self.base_url and self.api_key and self.model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.is_ready:
            raise RuntimeError("embedding client not ready")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        embeddings: list[list[float]] = []

        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = requests.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.model_name,
                    "input": batch,
                },
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            data = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
            if len(data) != len(batch):
                raise ValueError("embedding 返回数量与输入不一致")
            embeddings.extend(item["embedding"] for item in data)

        return embeddings


class BM25Retriever:
    backend_name = "local_bm25"

    def __init__(self, chunks: list[Chunk], title_boost: float = 0.45, cached_state: Optional[dict] = None):
        self.chunks = chunks
        self.title_boost = title_boost
        self.doc_freq: dict[str, int] = defaultdict(int)
        self.term_freqs: list[Counter] = []
        self.heading_token_sets: list[set[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_length = 0.0
        self.cache_hit = False

        if cached_state and self._load_cached_state(cached_state):
            self.cache_hit = True
            logger.info("[索引] BM25 索引命中本地快照，跳过重新分词统计")
        else:
            self._build_from_chunks()

    def _build_from_chunks(self) -> None:
        self.doc_freq = defaultdict(int)
        self.term_freqs = []
        self.heading_token_sets = []
        self.doc_lengths = []
        self.avg_doc_length = 0.0

        for chunk in self.chunks:
            tokens = tokenize(chunk.text)
            term_freq = Counter(tokens)
            self.term_freqs.append(term_freq)
            heading_text = " ".join(
                part
                for part in (
                    chunk.metadata.get("section_heading"),
                    chunk.metadata.get("page_heading"),
                    chunk.title,
                )
                if part
            )
            self.heading_token_sets.append(set(tokenize(heading_text)))
            self.doc_lengths.append(sum(term_freq.values()))

            for token in term_freq.keys():
                self.doc_freq[token] += 1

        if self.doc_lengths:
            self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)

    def _load_cached_state(self, cached_state: dict) -> bool:
        try:
            term_freqs = [Counter(item) for item in (cached_state.get("term_freqs") or [])]
            heading_token_sets = [set(item) for item in (cached_state.get("heading_token_sets") or [])]
            doc_lengths = [int(item) for item in (cached_state.get("doc_lengths") or [])]
            avg_doc_length = float(cached_state.get("avg_doc_length") or 0.0)
            raw_doc_freq = cached_state.get("doc_freq") or {}
            doc_freq = defaultdict(int, {str(key): int(value) for key, value in raw_doc_freq.items()})
        except Exception:
            return False

        expected_count = len(self.chunks)
        if len(term_freqs) != expected_count or len(heading_token_sets) != expected_count or len(doc_lengths) != expected_count:
            return False

        self.term_freqs = term_freqs
        self.heading_token_sets = heading_token_sets
        self.doc_lengths = doc_lengths
        self.avg_doc_length = avg_doc_length
        self.doc_freq = doc_freq
        return True

    def export_state(self) -> dict:
        return {
            "doc_freq": dict(self.doc_freq),
            "term_freqs": [dict(term_freq) for term_freq in self.term_freqs],
            "heading_token_sets": [sorted(tokens) for tokens in self.heading_token_sets],
            "doc_lengths": [int(length) for length in self.doc_lengths],
            "avg_doc_length": float(self.avg_doc_length),
        }

    def _idf(self, token: str) -> float:
        doc_count = len(self.chunks)
        freq = self.doc_freq.get(token, 0)
        return math.log(1 + (doc_count - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 4, min_score: float = 0.1) -> list[RetrievalResult]:
        query_tokens = tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        scored_items: list[tuple[RetrievalResult, int]] = []
        query_token_set = set(query_tokens)
        ascii_query_tokens = {token for token in query_token_set if re.fullmatch(r"[a-z0-9_+\-]{3,}", token)}

        for index, chunk in enumerate(self.chunks):
            term_freq = self.term_freqs[index]
            heading_tokens = self.heading_token_sets[index]
            doc_length = self.doc_lengths[index] or 1
            score = 0.0
            for token in query_token_set:
                freq = term_freq.get(token, 0)
                if not freq:
                    continue
                numerator = freq * (1.5 + 1)
                denominator = freq + 1.5 * (1 - 0.75 + 0.75 * doc_length / max(self.avg_doc_length, 1))
                score += self._idf(token) * numerator / denominator

            if ascii_query_tokens:
                ascii_hits = sum(1 for token in ascii_query_tokens if term_freq.get(token, 0))
                if ascii_hits == 0:
                    score *= 0.35
                else:
                    score += ascii_hits * 0.75

            heading_hits = len(query_token_set & heading_tokens)
            if heading_hits:
                score += heading_hits * 0.9

            if any(token in chunk.title.lower() for token in query_token_set if len(token) > 1):
                score += self.title_boost

            if score >= min_score:
                scored_items.append(
                    (
                        RetrievalResult(
                            chunk=chunk,
                            score=score,
                            details={"bm25_score": round(score, 4)},
                        ),
                        heading_hits,
                    )
                )

        scored_items.sort(key=lambda item: (item[1], item[0].score), reverse=True)
        return [item[0] for item in scored_items[:top_k]]


class EmbeddingRetriever:
    backend_name = "remote_embedding"
    vector_store_backend = "memory"

    def __init__(self, chunks: list[Chunk], client: OpenAICompatibleEmbeddingClient, min_score: float = 0.15):
        self.chunks = chunks
        self.client = client
        self.default_min_score = float(min_score)
        self.chunk_embeddings: list[list[float]] = []
        self.is_ready = False
        self.failure_reason = ""

        if not self.chunks:
            self.failure_reason = "empty_chunks"
            return
        if not self.client.is_ready:
            self.failure_reason = "embedding_client_not_ready"
            logger.info("[索引] 未检测到 embedding 所需配置，向量检索不会启用")
            return

        try:
            logger.info("[索引] 开始构建内存 embedding 向量索引，共 %s 个切片", len(self.chunks))
            texts = [_serialize_chunk_text(chunk) for chunk in self.chunks]
            embeddings = self.client.embed_texts(texts)
            if len(embeddings) != len(self.chunks):
                raise ValueError("embedding 返回数量与切片数量不一致")
            self.chunk_embeddings = [_normalize_vector(embedding) for embedding in embeddings]
            self.is_ready = True
            logger.info("[索引] 内存 embedding 向量索引构建完成")
        except Exception as exc:
            self.failure_reason = str(exc)
            logger.warning("[索引] 内存 embedding 向量索引构建失败，回退到 BM25: %s", exc)

    def search(self, query: str, top_k: int = 4, min_score: Optional[float] = None) -> list[RetrievalResult]:
        if not self.is_ready or not self.chunks:
            return []

        threshold = self.default_min_score if min_score is None else float(min_score)

        try:
            query_embedding = self.client.embed_texts([query])[0]
        except Exception as exc:
            logger.warning("[检索] 查询 embedding 生成失败，跳过向量检索: %s", exc)
            return []

        normalized_query = _normalize_vector(query_embedding)
        scored_results: list[RetrievalResult] = []

        for chunk, chunk_embedding in zip(self.chunks, self.chunk_embeddings):
            score = _dot_product(normalized_query, chunk_embedding)
            if score >= threshold:
                scored_results.append(
                    RetrievalResult(
                        chunk=chunk,
                        score=score,
                        details={"embedding_score": round(score, 4), "vector_store": "memory"},
                    )
                )

        scored_results.sort(key=lambda item: item.score, reverse=True)
        return scored_results[:top_k]


class PersistentChromaEmbeddingRetriever:
    backend_name = "persistent_chroma_embedding"
    vector_store_backend = "chroma"

    def __init__(
        self,
        chunks: list[Chunk],
        client: OpenAICompatibleEmbeddingClient,
        persist_directory: str,
        collection_name: str,
        min_score: float = 0.15,
        sync_batch_size: int = 100,
        skip_sync: bool = False,
    ):
        self.chunks = chunks
        self.client = client
        self.default_min_score = float(min_score)
        self.persist_directory = str(Path(persist_directory).resolve())
        self.collection_name = collection_name.strip()
        self.sync_batch_size = max(1, int(sync_batch_size or 100))
        self.skip_sync = bool(skip_sync)
        self.chunk_lookup = {chunk.chunk_id: chunk for chunk in self.chunks}
        self.db_client = None
        self.collection = None
        self.is_ready = False
        self.failure_reason = ""
        self.sync_stats = {
            "total": 0,
            "reused": 0,
            "upserted": 0,
            "deleted": 0,
        }

        if not self.chunks:
            self.failure_reason = "empty_chunks"
            return
        if not self.client.is_ready:
            self.failure_reason = "embedding_client_not_ready"
            logger.info("[索引] 未检测到 embedding 所需配置，持久化向量库不会启用")
            return
        if chromadb is None:
            self.failure_reason = "chromadb_not_installed"
            logger.warning("[索引] chromadb 未安装，回退到内存 embedding 或 BM25")
            return
        if not self.collection_name:
            self.failure_reason = "missing_collection_name"
            logger.warning("[索引] 缺少向量集合名称，无法构建 Chroma 向量库")
            return

        try:
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
            self.db_client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.db_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            if self.skip_sync and self._can_reuse_collection_without_sync():
                self.sync_stats = {
                    "total": len(self.chunks),
                    "reused": len(self.chunks),
                    "upserted": 0,
                    "deleted": 0,
                }
                logger.info(
                    "[索引] Chroma 向量库命中本地快照，直接复用已落盘集合，collection=%s",
                    self.collection_name,
                )
            else:
                self._sync_collection()
            self.is_ready = True
        except Exception as exc:
            self.failure_reason = str(exc)
            logger.warning("[索引] Chroma 持久化向量库构建失败，回退到内存 embedding 或 BM25: %s", exc)

    def _build_metadata(self, chunk: Chunk, signature: str) -> dict:
        metadata = {
            "chunk_signature": signature,
            "doc_id": chunk.doc_id,
            "title": chunk.title,
            "source_path": chunk.source_path,
            "order": int(chunk.order),
        }
        for key in ("section_heading", "page_heading", "page_number", "md5"):
            value = chunk.metadata.get(key)
            if isinstance(value, bool):
                metadata[key] = value
            elif isinstance(value, int):
                metadata[key] = int(value)
            elif isinstance(value, float):
                metadata[key] = float(value)
            elif isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        return metadata

    def _existing_metadata_by_id(self) -> dict[str, dict]:
        if not self.collection:
            return {}
        payload = self.collection.get(include=["metadatas"])
        ids = payload.get("ids") or []
        metadatas = payload.get("metadatas") or []
        return {
            str(chunk_id): (metadata or {})
            for chunk_id, metadata in zip(ids, metadatas)
        }

    def _can_reuse_collection_without_sync(self) -> bool:
        if not self.collection:
            return False
        try:
            return int(self.collection.count()) == len(self.chunks)
        except Exception:
            return False

    def _batched(self, values: list[str]) -> list[list[str]]:
        return [values[index : index + self.sync_batch_size] for index in range(0, len(values), self.sync_batch_size)]

    def _sync_collection(self) -> None:
        current_entries: dict[str, dict] = {}
        for chunk in self.chunks:
            serialized_text = _serialize_chunk_text(chunk)
            signature = _stable_chunk_signature(chunk, serialized_text)
            current_entries[chunk.chunk_id] = {
                "chunk": chunk,
                "text": serialized_text,
                "signature": signature,
                "metadata": self._build_metadata(chunk, signature),
            }

        existing_by_id = self._existing_metadata_by_id()
        current_ids = set(current_entries.keys())
        existing_ids = set(existing_by_id.keys())
        stale_ids = sorted(existing_ids - current_ids)

        for batch_ids in self._batched(stale_ids):
            self.collection.delete(ids=batch_ids)

        upsert_ids = [
            chunk_id
            for chunk_id, entry in current_entries.items()
            if existing_by_id.get(chunk_id, {}).get("chunk_signature") != entry["signature"]
        ]
        reused_count = len(current_entries) - len(upsert_ids)

        if upsert_ids:
            texts = [current_entries[chunk_id]["text"] for chunk_id in upsert_ids]
            embeddings = self.client.embed_texts(texts)
            if len(embeddings) != len(upsert_ids):
                raise ValueError("embedding 返回数量与待写入向量数量不一致")
            normalized_embeddings = [_normalize_vector(embedding) for embedding in embeddings]

            for start in range(0, len(upsert_ids), self.sync_batch_size):
                batch_ids = upsert_ids[start : start + self.sync_batch_size]
                batch_embeddings = normalized_embeddings[start : start + self.sync_batch_size]
                self.collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=[current_entries[chunk_id]["text"] for chunk_id in batch_ids],
                    metadatas=[current_entries[chunk_id]["metadata"] for chunk_id in batch_ids],
                )

        self.sync_stats = {
            "total": len(current_entries),
            "reused": reused_count,
            "upserted": len(upsert_ids),
            "deleted": len(stale_ids),
        }
        logger.info(
            "[索引] Chroma 向量库同步完成，总计 %s，复用 %s，新写入 %s，删除 %s，collection=%s",
            self.sync_stats["total"],
            self.sync_stats["reused"],
            self.sync_stats["upserted"],
            self.sync_stats["deleted"],
            self.collection_name,
        )

    def _chunk_from_result(self, chunk_id: str, metadata: dict, document_text: str) -> Chunk:
        chunk = self.chunk_lookup.get(chunk_id)
        if chunk:
            return chunk

        metadata = metadata or {}
        chunk_metadata = {
            key: metadata[key]
            for key in ("section_heading", "page_heading", "page_number", "md5")
            if key in metadata and metadata[key] not in (None, "")
        }
        return Chunk(
            chunk_id=chunk_id,
            doc_id=str(metadata.get("doc_id") or chunk_id),
            title=str(metadata.get("title") or "Document"),
            source_path=str(metadata.get("source_path") or ""),
            text=document_text or "",
            order=int(metadata.get("order") or 0),
            metadata=chunk_metadata,
        )

    def search(self, query: str, top_k: int = 4, min_score: Optional[float] = None) -> list[RetrievalResult]:
        if not self.is_ready or not self.collection:
            return []
        if self.collection.count() <= 0:
            return []

        threshold = self.default_min_score if min_score is None else float(min_score)

        try:
            query_embedding = _normalize_vector(self.client.embed_texts([query])[0])
            payload = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=max(1, int(top_k)),
                include=["distances", "documents", "metadatas"],
            )
        except Exception as exc:
            logger.warning("[检索] Chroma 查询失败，跳过持久化向量检索: %s", exc)
            return []

        ids = (payload.get("ids") or [[]])[0]
        distances = (payload.get("distances") or [[]])[0]
        documents = (payload.get("documents") or [[]])[0]
        metadatas = (payload.get("metadatas") or [[]])[0]

        results: list[RetrievalResult] = []
        for index, chunk_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 1.0
            score = max(0.0, 1.0 - distance)
            if score < threshold:
                continue
            metadata = metadatas[index] if index < len(metadatas) else {}
            document_text = documents[index] if index < len(documents) else ""
            results.append(
                RetrievalResult(
                    chunk=self._chunk_from_result(str(chunk_id), metadata or {}, document_text),
                    score=score,
                    details={
                        "embedding_score": round(score, 4),
                        "vector_distance": round(distance, 4),
                        "vector_store": self.vector_store_backend,
                    },
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Retriever,
        embedding: Optional[object] = None,
        bm25_weight: float = 1.0,
        embedding_weight: float = 1.0,
        rrf_k: int = 60,
        candidate_top_k: int = 12,
    ):
        self.bm25 = bm25
        self.embedding = embedding
        self.bm25_weight = float(bm25_weight)
        self.embedding_weight = float(embedding_weight)
        self.rrf_k = max(1, int(rrf_k))
        self.candidate_top_k = max(4, int(candidate_top_k))
        self.backend_name = "hybrid_bm25_embedding" if embedding and embedding.is_ready else bm25.backend_name

    def search(self, query: str, top_k: int = 4, min_score: float = 0.1) -> list[RetrievalResult]:
        candidate_top_k = max(int(top_k) * 3, self.candidate_top_k)
        bm25_results = self.bm25.search(query, top_k=candidate_top_k, min_score=min_score)

        if not self.embedding or not self.embedding.is_ready:
            return bm25_results[:top_k]

        embedding_results = self.embedding.search(query, top_k=candidate_top_k)
        if not bm25_results and not embedding_results:
            return []
        if not embedding_results:
            return bm25_results[:top_k]

        fused: dict[str, dict] = {}
        result_groups = (
            (bm25_results, self.bm25_weight, "bm25"),
            (embedding_results, self.embedding_weight, "embedding"),
        )

        for results, weight, name in result_groups:
            for rank, result in enumerate(results, start=1):
                item = fused.setdefault(
                    result.chunk.chunk_id,
                    {
                        "chunk": result.chunk,
                        "score": 0.0,
                        "bm25_score": None,
                        "embedding_score": None,
                        "bm25_rank": None,
                        "embedding_rank": None,
                    },
                )
                item["score"] += weight / (self.rrf_k + rank)
                item[f"{name}_rank"] = rank
                component_score = result.details.get(f"{name}_score", result.score)
                item[f"{name}_score"] = component_score

            merged_results: list[RetrievalResult] = []
        for item in fused.values():
            details = {
                key: value
                for key, value in {
                    "bm25_score": item["bm25_score"],
                    "embedding_score": item["embedding_score"],
                    "bm25_rank": item["bm25_rank"],
                    "embedding_rank": item["embedding_rank"],
                }.items()
                if value is not None
            }
            merged_results.append(
                RetrievalResult(
                    chunk=item["chunk"],
                    score=item["score"],
                    details=details,
                )
            )

        merged_results.sort(
            key=lambda result: (
                result.score,
                result.details.get("bm25_score", -1),
                result.details.get("embedding_score", -1),
            ),
            reverse=True,
        )
        return merged_results[:top_k]
