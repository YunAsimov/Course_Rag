import math
import re
from collections import Counter, defaultdict

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


class BM25Retriever:
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
                scored_items.append((RetrievalResult(chunk=chunk, score=score), heading_hits))

        scored_items.sort(key=lambda item: (item[1], item[0].score), reverse=True)
        return [item[0] for item in scored_items[:top_k]]

