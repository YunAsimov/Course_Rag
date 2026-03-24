import csv
import hashlib
import logging
import os
import re
import zipfile
from typing import Iterable
from xml.etree import ElementTree

from pypdf import PdfReader

from utils.logger_handler import logger

DEFAULT_ALLOWED_TYPES = (".md", ".txt", ".pdf", ".docx", ".csv")
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

logging.getLogger("pypdf").setLevel(logging.ERROR)


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
        if current_kind == "bullet":
            blocks.append(" ".join(current).strip())
        else:
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


def csv_loader(file_path: str, encoding: str = "utf-8-sig") -> list[dict]:
    rows: list[dict] = []
    with open(file_path, "r", encoding=encoding, newline="") as file:
        reader = csv.DictReader(file)
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
                        "source_type": "csv_row",
                    },
                }
            )
    return rows


def load_file_records(file_path: str) -> list[dict]:
    extension = os.path.splitext(file_path)[1].lower()
    base_name = os.path.basename(file_path)

    try:
        if extension in {".txt", ".md"}:
            text = txt_loader(file_path)
            return [{"title": os.path.splitext(base_name)[0], "text": text, "metadata": {}}]
        if extension == ".pdf":
            return pdf_loader(file_path)
        if extension == ".docx":
            text = docx_loader(file_path)
            return [{"title": os.path.splitext(base_name)[0], "text": text, "metadata": {}}]
        if extension == ".csv":
            return csv_loader(file_path)
    except Exception as exc:
        logger.exception("[文件加载] 读取 %s 失败: %s", file_path, exc)
        return []

    logger.warning("[文件加载] 暂不支持的文件类型: %s", file_path)
    return []
