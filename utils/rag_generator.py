import os
import re
from collections import OrderedDict
from typing import Optional

import requests

from utils.logger_handler import logger
from utils.rag_models import RetrievalResult
from utils.rag_retriever import tokenize

SENTENCE_SPLITTER = re.compile(r"(?<=[。！？；\n])")
GENERIC_SENTENCE_HINTS = (
    "我直接给你整理",
    "可以当说明书",
    "超全",
    "全覆盖",
)


class AnswerGenerator:
    def __init__(self, agent_conf: dict, prompts_conf: dict):
        self.agent_conf = agent_conf
        self.prompts_conf = prompts_conf

    def generate(self, question: str, results: list[RetrievalResult], max_context_chars: int) -> tuple[str, str]:
        if not results:
            return (
                "知识库里暂时没有足够相关的课程资料。你可以换一种问法，或者补充 lecture、章节、公式名或方法名。",
                "no_context",
            )

        if self.agent_conf.get("enabled"):
            remote_answer = self._generate_with_remote_llm(question, results, max_context_chars)
            if remote_answer:
                return remote_answer, "remote_llm"

        return self._generate_locally(question, results), "local_summary"

    def _build_context(self, results: list[RetrievalResult], max_context_chars: int) -> str:
        blocks: list[str] = []
        current_length = 0
        for result in results:
            block = (
                f"[来源] {result.chunk.title}\n"
                f"[路径] {result.chunk.source_path}\n"
                f"[内容] {result.chunk.text.strip()}\n"
            )
            if current_length + len(block) > max_context_chars:
                break
            blocks.append(block)
            current_length += len(block)
        return "\n".join(blocks)

    def _generate_with_remote_llm(
        self, question: str, results: list[RetrievalResult], max_context_chars: int
    ) -> Optional[str]:
        api_key = self.agent_conf.get("api_key") or os.getenv(self.agent_conf.get("api_key_env", ""))
        if not api_key:
            logger.warning("[LLM] 已启用远程模型，但未读取到本地 environment 文件或环境变量中的 %s", self.agent_conf.get("api_key_env"))
            return None

        base_url = (
            self.agent_conf.get("base_url")
            or os.getenv(self.agent_conf.get("base_url_env", ""), self.agent_conf["base_url"])
        ).rstrip("/")
        model_name = self.agent_conf.get("model_name")
        system_prompt = self.prompts_conf["system_prompt"]
        user_prompt = self.prompts_conf["user_prompt_template"].format(
            question=question,
            context=self._build_context(results, max_context_chars=max_context_chars),
        )

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.agent_conf.get("temperature", 0.2),
            "max_tokens": self.agent_conf.get("max_tokens", 700),
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.agent_conf.get("timeout_seconds", 30),
            )
            response.raise_for_status()
            payload = response.json()
            return payload["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("[LLM] 远程生成失败，回退到本地摘要: %s", exc)
            return None

    def _generate_locally(self, question: str, results: list[RetrievalResult]) -> str:
        scored_sentences = self._rank_sentences(question, results)
        if not scored_sentences:
            primary = results[0].chunk.text[:280].strip()
            return f"根据已检索资料，最相关的信息是：\n{primary}"

        selected = list(OrderedDict.fromkeys(sentence for sentence, _ in scored_sentences[:4]))
        answer = "根据知识库里的资料，先给你一个简要结论：\n"
        answer += "\n".join(selected[:2])

        if len(selected) > 2:
            answer += "\n\n补充依据：\n"
            answer += "\n".join(f"- {sentence}" for sentence in selected[2:])

        answer += "\n\n如果你想要更聚焦的解释，可以继续补充 lecture 编号、章节标题、公式、算法名或关键词。"
        return answer.strip()

    def _rank_sentences(self, question: str, results: list[RetrievalResult]) -> list[tuple[str, float]]:
        query_tokens = set(tokenize(question))
        ranked: list[tuple[str, float]] = []

        for result in results:
            sentences = [part.strip() for part in SENTENCE_SPLITTER.split(result.chunk.text) if part.strip()]
            merged_sentences: list[str] = []
            index = 0
            while index < len(sentences):
                current = sentences[index]
                if (
                    index + 1 < len(sentences)
                    and current.endswith(("？", "?"))
                    and len(current) <= 36
                ):
                    merged_sentences.append(f"{current} {sentences[index + 1]}".strip())
                    index += 2
                    continue

                merged_sentences.append(current)
                index += 1

            for sentence in merged_sentences:
                sentence_tokens = set(tokenize(sentence))
                if not sentence_tokens:
                    continue

                overlap = len(query_tokens & sentence_tokens)
                if overlap == 0:
                    continue
                density = overlap / max(len(sentence_tokens), 1)
                score = overlap * 1.6 + density + result.score * 0.15
                if score <= 0:
                    continue

                cleaned = sentence.replace("\n", " ").strip()
                if len(cleaned) < 12:
                    continue
                if any(hint in cleaned for hint in GENERIC_SENTENCE_HINTS):
                    continue
                ranked.append((cleaned, score))

        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked
