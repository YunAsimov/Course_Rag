import sys
from dataclasses import dataclass, field


if sys.version_info >= (3, 10):
    model_dataclass = dataclass(slots=True)
else:
    model_dataclass = dataclass


@model_dataclass
class Document:
    doc_id: str
    title: str
    source_path: str
    doc_type: str
    text: str
    metadata: dict = field(default_factory=dict)


@model_dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    source_path: str
    text: str
    order: int
    metadata: dict = field(default_factory=dict)


@model_dataclass
class RetrievalResult:
    chunk: Chunk
    score: float
    details: dict = field(default_factory=dict)
