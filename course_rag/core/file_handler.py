import csv
import hashlib
import json
import logging
import os
import re
import zipfile
from html import unescape
from html.parser import HTMLParser
from typing import Iterable
from xml.etree import ElementTree

from pypdf import PdfReader

from course_rag.core.logger_handler import logger

DEFAULT_ALLOWED_TYPES = (
    ".md",
    ".markdown",
    ".txt",
    ".pdf",
    ".docx",
    ".csv",
    ".tsv",
    ".json",
    ".html",
    ".htm",
    ".pptx",
)
MARKDOWN_TYPES = {".md", ".markdown"}
PDF_INLINE_SPACES_RE = re.compile(r"\b([A-Za-z])\s+([a-z]{2,})\b")
PDF_SHORT_TOKEN_RE = re.compile(r"^(?:\d+|[ivxlcdm]+)$", re.IGNORECASE)
PDF_BULLET_RE = re.compile(r"^(?:[-*•▪◦]|(?:\d+|[A-Za-z])[\.\)])\s+")
PDF_URL_RE = re.compile(r"^(?:\[\d+\]\s*)?https?://", re.IGNORECASE)
PDF_COURSE_HEADER_MARKERS = (
    "comp5575",
    "high-dimensionaldatamanagementandanalytics",
    "departmentofcomputing",
    "thehongkongpolytechnicuniversity",
    "permissionfromdr",
    "slidescanbefreelyused",
    "sl idescontributorforlecture".replace(" ", ""),
)
PPTX_SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")

logging.getLogger("pypdf").setLevel(logging.ERROR)


class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "main",
        "aside",
        "header",
        "footer",
        "nav",
        "ul",
        "ol",
        "li",
        "table",
        "tr",
        "br",
        "hr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "pre",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        if lowered in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and lowered in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and lowered in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        cleaned = unescape(data.replace("\xa0", " "))
        if cleaned.strip():
            self._parts.append(cleaned)

    def get_text(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        return text.strip()


def get_md5_file_hex(file_path: str) -> str:
    if not os.path.exists(file_path):
        logger.error("[md5计算] 文件 %s 不存在", file_path)
        return ""
    if not os.path.isfile(file_path):
        logger.error("[md5计算] 路径 %s 不是文件", file_path)
        return ""

    md5_obj = hashlib.md5()
    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            md5_obj.update(chunk)
    return md5_obj.hexdigest()


def listdir_with_allowed_type(
    directory: str, allowed_types: Iterable[str] = DEFAULT_ALLOWED_TYPES
) -> list[str]:
    if not os.path.exists(directory):
        logger.warning("[文件扫描] 目录 %s 不存在", directory)
        return []

    allowed = {suffix.lower() for suffix in allowed_types}
    collected: list[str] = []
    for root, _, files in os.walk(directory):
        for file_name in files:
            if file_name.startswith("~$"):
                continue
            ext = os.path.splitext(file_name)[1].lower()
            if ext in allowed:
                collected.append(os.path.join(root, file_name))
    return sorted(collected)


def _normalize_inline_pdf_text(text: str) -> str:
    compacted = " ".join(text.replace("\u00a0", " ").split())
    previous = None
    current = compacted
    while previous != current:
        previous = current
        current = PDF_INLINE_SPACES_RE.sub(r"\1\2", current)

    current = re.sub(r"\b([A-Za-z]{1,4})\s+\.", r"\1.", current)
    current = re.sub(r"\s+([,.;:!?])", r"\1", current)
    return current.strip()


def _is_pdf_noise_line(line: str, page_number: int) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped == str(page_number):
        return True
    if PDF_SHORT_TOKEN_RE.fullmatch(stripped) and len(stripped) <= 3:
        return True
    if PDF_URL_RE.match(stripped):
        return True

    compact = re.sub(r"\s+", "", stripped.lower())
    if any(marker in compact for marker in PDF_COURSE_HEADER_MARKERS):
        return True

    alpha_count = sum(char.isalpha() for char in stripped)
    digit_count = sum(char.isdigit() for char in stripped)
    if len(stripped) <= 4 and digit_count:
        return True
    if alpha_count == 0 and digit_count > 0:
        return True
    return False


def _looks_like_heading(line: str) -> bool:
    if len(line) > 90:
        return False
    if PDF_BULLET_RE.match(line):
        return False
    if line.endswith(("。", "？", "！", ".", "?", "!", ";", "；", ":")):
        return False
    if line.startswith(("<", "[")):
        return False
    return True


def _extract_pdf_heading(blocks: list[str]) -> str:
    for block in blocks[:4]:
        candidate = block.strip()
        if not candidate:
            continue
        if PDF_BULLET_RE.match(candidate):
            continue
        if not _looks_like_heading(candidate):
            continue
        return candidate
    return ""


def _group_pdf_lines(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    current_kind = ""

    def flush() -> None:
        nonlocal current, current_kind
        if not current:
            return
        blocks.append(" ".join(current).strip())
        current = []
        current_kind = ""

    for line in lines:
        if _looks_like_heading(line):
            flush()
            blocks.append(line)
            continue

        if PDF_BULLET_RE.match(line):
            flush()
            current = [line]
            current_kind = "bullet"
            continue

        if not current:
            current = [line]
            current_kind = "paragraph"
            continue

        current.append(line)

    flush()
    return [block for block in blocks if block]


def pdf_loader(file_path: str) -> list[dict]:
    reader = PdfReader(file_path)
    page_records: list[dict] = []
    file_stem = os.path.splitext(os.path.basename(file_path))[0]

    for page_number, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        raw_lines = [_normalize_inline_pdf_text(line) for line in raw_text.splitlines()]
        cleaned_lines = []
        for line in raw_lines:
            if _is_pdf_noise_line(line, page_number=page_number):
                continue
            cleaned_lines.append(line)

        blocks = _group_pdf_lines(cleaned_lines)
        page_text = "\n\n".join(blocks).strip()
        if not page_text or len(page_text) < 40:
            continue

        page_records.append(
            {
                "title": f"{file_stem} p.{page_number}",
                "text": page_text,
                "metadata": {
                    "page_number": page_number,
                    "page_heading": _extract_pdf_heading(blocks),
                    "source_type": "pdf_page",
                },
            }
        )

    return page_records


def txt_loader(file_path: str, encoding: str = "utf-8") -> str:
    with open(file_path, "r", encoding=encoding) as file:
        return file.read().strip()


def html_loader(file_path: str, encoding: str = "utf-8") -> str:
    with open(file_path, "r", encoding=encoding, errors="ignore") as file:
        raw_html = file.read()

    parser = _HTMLTextExtractor()
    parser.feed(raw_html)
    parser.close()
    return parser.get_text()


def docx_loader(file_path: str) -> str:
    with zipfile.ZipFile(file_path) as archive:
        xml_bytes = archive.read("word/document.xml")

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    root = ElementTree.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        joined = "".join(texts).strip()
        if joined:
            paragraphs.append(joined)
    return "\n\n".join(paragraphs)


def _json_to_lines(value, prefix: str = "") -> list[str]:
    lines: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_json_to_lines(child, child_prefix))
        return lines

    if isinstance(value, list):
        if not value:
            if prefix:
                lines.append(f"{prefix}: []")
            return lines
        if all(not isinstance(item, (dict, list)) for item in value):
            rendered = ", ".join(str(item) for item in value)
            lines.append(f"{prefix}: {rendered}" if prefix else rendered)
            return lines
        for index, child in enumerate(value, start=1):
            child_prefix = f"{prefix}[{index}]" if prefix else f"item[{index}]"
            lines.extend(_json_to_lines(child, child_prefix))
        return lines

    if value is None:
        return lines

    rendered = str(value).strip()
    if not rendered:
        return lines
    lines.append(f"{prefix}: {rendered}" if prefix else rendered)
    return lines


def json_loader(file_path: str, encoding: str = "utf-8") -> list[dict]:
    with open(file_path, "r", encoding=encoding) as file:
        data = json.load(file)

    if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
        records: list[dict] = []
        base_name = os.path.basename(file_path)
        for row_number, item in enumerate(data, start=1):
            lines = _json_to_lines(item)
            text = "\n".join(lines).strip()
            if not text:
                continue
            records.append(
                {
                    "title": f"{base_name} 第 {row_number} 项",
                    "text": text,
                    "metadata": {
                        "row_number": row_number,
                        "source_type": "json_item",
                    },
                }
            )
        if records:
            return records

    lines = _json_to_lines(data)
    return [
        {
            "title": os.path.splitext(os.path.basename(file_path))[0],
            "text": "\n".join(lines).strip(),
            "metadata": {
                "source_type": "json_document",
            },
        }
    ]


def _extract_pptx_slide_text(xml_bytes: bytes) -> list[str]:
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    root = ElementTree.fromstring(xml_bytes)
    texts = []
    for node in root.findall(".//a:t", namespace):
        value = (node.text or "").strip()
        if value:
            texts.append(value)
    return texts


def pptx_loader(file_path: str) -> list[dict]:
    slide_records: list[dict] = []
    file_stem = os.path.splitext(os.path.basename(file_path))[0]

    with zipfile.ZipFile(file_path) as archive:
        slide_names = []
        for name in archive.namelist():
            match = PPTX_SLIDE_RE.match(name)
            if match:
                slide_names.append((int(match.group(1)), name))

        for slide_number, slide_name in sorted(slide_names):
            slide_texts = _extract_pptx_slide_text(archive.read(slide_name))
            if not slide_texts:
                continue
            title = slide_texts[0]
            body = "\n\n".join(slide_texts).strip()
            if not body:
                continue
            slide_records.append(
                {
                    "title": f"{file_stem} Slide {slide_number}",
                    "text": body,
                    "metadata": {
                        "slide_number": slide_number,
                        "slide_heading": title,
                        "source_type": "pptx_slide",
                    },
                }
            )

    return slide_records


def csv_loader(file_path: str, encoding: str = "utf-8-sig", delimiter: str = ",") -> list[dict]:
    rows: list[dict] = []
    with open(file_path, "r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        for row_number, row in enumerate(reader, start=1):
            lines = []
            for key, value in row.items():
                cell = (value or "").strip()
                if cell:
                    lines.append(f"{key}: {cell}")

            rows.append(
                {
                    "title": f"{os.path.basename(file_path)} 第 {row_number} 行",
                    "text": "\n".join(lines).strip(),
                    "metadata": {
                        "row_number": row_number,
                        "source_type": "csv_row" if delimiter == "," else "tsv_row",
                    },
                }
            )
    return rows


def load_file_records(file_path: str) -> list[dict]:
    extension = os.path.splitext(file_path)[1].lower()
    base_name = os.path.basename(file_path)

    try:
        if extension in MARKDOWN_TYPES | {".txt"}:
            text = txt_loader(file_path)
            return [{"title": os.path.splitext(base_name)[0], "text": text, "metadata": {}}]
        if extension in {".html", ".htm"}:
            text = html_loader(file_path)
            return [
                {
                    "title": os.path.splitext(base_name)[0],
                    "text": text,
                    "metadata": {"source_type": "html_document"},
                }
            ]
        if extension == ".pdf":
            return pdf_loader(file_path)
        if extension == ".docx":
            text = docx_loader(file_path)
            return [
                {
                    "title": os.path.splitext(base_name)[0],
                    "text": text,
                    "metadata": {"source_type": "docx_document"},
                }
            ]
        if extension == ".pptx":
            return pptx_loader(file_path)
        if extension == ".csv":
            return csv_loader(file_path)
        if extension == ".tsv":
            return csv_loader(file_path, delimiter="\t")
        if extension == ".json":
            return json_loader(file_path)
    except Exception as exc:
        logger.exception("[文件加载] 读取 %s 失败: %s", file_path, exc)
        return []

    logger.warning("[文件加载] 暂不支持的文件类型: %s", file_path)
    return []
