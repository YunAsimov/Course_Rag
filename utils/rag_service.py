import os
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

        self._build_index()

    def _build_index(self) -> None:
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

        self.documents = documents
        self.chunks = chunks
        self.retriever = BM25Retriever(chunks, title_boost=self.retrieval_conf["title_boost"])
        self.index_summary = {
            "documents": doc_count,
            "chunks": chunk_count,
            "data_dir": self.data_dir,
            "backend": self.retrieval_conf["backend"],
            "remote_llm_enabled": bool(self.agent_conf.get("enabled")),
        }
        logger.info("[索引] 构建完成，文档 %s 份，切片 %s 个", doc_count, chunk_count)

    def ask(self, question: str) -> dict:
        clean_question = question.strip()
        if not clean_question:
            return {
                "answer": "请输入一个具体问题，例如“为什么文本数据通常使用余弦相似度？”",
                "mode": "validation",
                "sources": [],
            }

        if not self.retriever:
            return {
                "answer": "检索器尚未初始化，无法回答问题。",
                "mode": "error",
                "sources": [],
            }

        results = self.retriever.search(
            clean_question,
            top_k=self.retrieval_conf["top_k"],
            min_score=self.retrieval_conf["min_score"],
        )
        answer, mode = self.generator.generate(
            clean_question,
            results,
            max_context_chars=self.retrieval_conf["max_context_chars"],
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
        return {
            "app_name": self.rag_conf["app_name"],
            "suggested_questions": self.prompts_conf["suggested_questions"],
            "stats": self.index_summary,
        }
