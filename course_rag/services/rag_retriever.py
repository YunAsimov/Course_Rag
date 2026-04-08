import math
import re
from collections import Counter, defaultdict
from typing import Optional

import requests

from course_rag.core.logger_handler import logger
from course_rag.services.rag_models import Chunk, RetrievalResult

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

    def __init__(self, chunks: list[Chunk], title_boost: float = 0.45):
        self.chunks = chunks
        self.title_boost = title_boost
        self.doc_freq: dict[str, int] = defaultdict(int)
        self.term_freqs: list[Counter] = []
        self.heading_token_sets: list[set[str]] = []
        self.doc_lengths: list[int] = []
        self.avg_doc_length = 0.0

        for chunk in chunks:
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
            logger.info("[索引] 开始构建 embedding 向量索引，共 %s 个切片", len(self.chunks))
            texts = [self._serialize_chunk(chunk) for chunk in self.chunks]
            embeddings = self.client.embed_texts(texts)
            if len(embeddings) != len(self.chunks):
                raise ValueError("embedding 返回数量与切片数量不一致")
            self.chunk_embeddings = [_normalize_vector(embedding) for embedding in embeddings]
            self.is_ready = True
            logger.info("[索引] embedding 向量索引构建完成")
        except Exception as exc:
            self.failure_reason = str(exc)
            logger.warning("[索引] embedding 向量索引构建失败，回退到 BM25: %s", exc)

    def _serialize_chunk(self, chunk: Chunk) -> str:
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
                        details={"embedding_score": round(score, 4)},
                    )
                )

        scored_results.sort(key=lambda item: item.score, reverse=True)
        return scored_results[:top_k]


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Retriever,
        embedding: Optional[EmbeddingRetriever] = None,
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


