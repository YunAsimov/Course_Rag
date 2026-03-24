import re

from utils.rag_models import Chunk, Document

PARAGRAPH_SEPARATOR = re.compile(r"\n\s*\n+")
MULTISPACE_RE = re.compile(r"[ \t]{2,}")
SENTENCE_SEPARATOR = re.compile(r"(?<=[。！？.!?;；:])\s+")
BULLET_RE = re.compile(r"^(?:[-*•▪◦]|(?:\d+|[A-Za-z])[\.\)])\s+")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s*")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_whitespace(text: str) -> str:
    normalized_lines: list[str] = []
    previous_blank = False
    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = MULTISPACE_RE.sub(" ", raw_line.strip())
        if not line:
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
            continue

        normalized_lines.append(line)
        previous_blank = False

    return "\n".join(normalized_lines).strip()


def _looks_like_heading(line: str) -> bool:
    if MARKDOWN_HEADING_RE.match(line):
        return True
    if len(line) > 90:
        return False
    if BULLET_RE.match(line):
        return False
    if line.endswith(("。", "？", "！", ".", "?", "!", ";", "；", ":")):
        return False
    return True


def _clean_heading_text(text: str) -> str:
    cleaned = MARKDOWN_HEADING_RE.sub("", text.strip())
    cleaned = HTML_TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = MULTISPACE_RE.sub(" ", cleaned)
    return cleaned.strip(" -–:：")


def _extract_section_heading(text: str, fallback: str = "") -> str:
    markdown_headings: list[str] = []
    heading_candidates: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = _clean_heading_text(stripped)
        if not cleaned:
            continue
        if BULLET_RE.match(cleaned):
            continue
        if MARKDOWN_HEADING_RE.match(stripped):
            markdown_headings.append(cleaned)
            continue
        if _looks_like_heading(cleaned):
            heading_candidates.append(cleaned)

    if markdown_headings:
        return markdown_headings[-1]
    if heading_candidates:
        return heading_candidates[-1]
    return _clean_heading_text(fallback) if fallback else ""


def _split_into_segments(text: str) -> list[str]:
    normalized = _normalize_whitespace(text)
    if not normalized:
        return []

    segments: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            segments.append(" ".join(current).strip())
            current = []

    for block in PARAGRAPH_SEPARATOR.split(normalized):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            flush()
            continue

        for line in lines:
            if _looks_like_heading(line):
                flush()
                segments.append(line)
                continue

            if BULLET_RE.match(line):
                flush()
                segments.append(line)
                continue

            current.append(line)

        flush()

    return [segment for segment in segments if segment]


def _split_long_segment(segment: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    sentences = [part.strip() for part in SENTENCE_SEPARATOR.split(segment) if part.strip()]
    if len(sentences) <= 1:
        step = max(chunk_size - chunk_overlap, 1)
        return [segment[start : start + chunk_size].strip() for start in range(0, len(segment), step) if segment[start : start + chunk_size].strip()]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = sentence
        else:
            step = max(chunk_size - chunk_overlap, 1)
            for start in range(0, len(sentence), step):
                piece = sentence[start : start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
            current = ""

    if current:
        chunks.append(current)
    return chunks


def _meaningful_chunk(text: str) -> bool:
    compact = text.strip()
    if len(compact) < 40:
        return False

    alnum_or_cjk = sum(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in compact)
    return alnum_or_cjk >= max(18, len(compact) // 3)


def _build_overlap_seed(segments: list[str], chunk_overlap: int) -> list[str]:
    if not chunk_overlap or not segments:
        return []

    collected: list[str] = []
    total_length = 0
    for segment in reversed(segments):
        segment_length = len(segment) + 2
        if collected and total_length + segment_length > chunk_overlap:
            break
        collected.append(segment)
        total_length += segment_length
    return list(reversed(collected))


def split_text_into_chunks(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    segments = _split_into_segments(text)
    if not segments:
        return []

    chunks: list[str] = []
    current_segments: list[str] = []
    current_text = ""

    for segment in segments:
        if len(segment) > chunk_size:
            if current_text and _meaningful_chunk(current_text):
                chunks.append(current_text)
            current_segments = []
            current_text = ""

            for piece in _split_long_segment(segment, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
                if _meaningful_chunk(piece):
                    chunks.append(piece)
            continue

        candidate = f"{current_text}\n\n{segment}".strip() if current_text else segment
        if len(candidate) <= chunk_size:
            current_segments.append(segment)
            current_text = candidate
            continue

        if _meaningful_chunk(current_text):
            chunks.append(current_text)
        overlap_segments = _build_overlap_seed(current_segments, chunk_overlap=chunk_overlap)
        current_segments = overlap_segments + [segment]
        current_text = "\n\n".join(current_segments).strip()

    if current_text and _meaningful_chunk(current_text):
        chunks.append(current_text)

    return chunks


def chunk_document(document: Document, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    parts = split_text_into_chunks(document.text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return [
        Chunk(
            chunk_id=f"{document.doc_id}-chunk-{index}",
            doc_id=document.doc_id,
            title=document.title,
            source_path=document.source_path,
            text=part,
            order=index,
            metadata={
                **document.metadata.copy(),
                "section_heading": (
                    document.metadata.get("page_heading", "")
                    if document.doc_type == ".pdf"
                    else _extract_section_heading(
                        part,
                        fallback=document.metadata.get("page_heading", ""),
                    )
                ),
            },
        )
        for index, part in enumerate(parts, start=1)
    ]
