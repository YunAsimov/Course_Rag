import os
from copy import deepcopy

import yaml

from utils.logger_handler import logger
from utils.path_tool import get_abs_path


def load_local_env_file(env_path: str = get_abs_path(".env.local"), encoding: str = "utf-8") -> dict:
    values = {}
    if not os.path.exists(env_path):
        return values

    with open(env_path, "r", encoding=encoding) as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value

    return values


LOCAL_ENV_VALUES = load_local_env_file()

DEFAULT_RAG_CONFIG = {
    "app_name": "COMP5575 Course RAG",
    "host": "127.0.0.1",
    "port": 7860,
    "debug": False,
    "data_dir": "data/course",
    "user_materials_root": "storage/materials",
    "bootstrap_owner": "lyy",
    "allowed_extensions": [".md"],
    "chat_model_name": "qwen3-max",
    "embedding_model_name": "text-embedding-v4",
}

DEFAULT_CHROMA_CONFIG = {
    "backend": "local_bm25",
    "chunk_size": 420,
    "chunk_overlap": 80,
    "top_k": 4,
    "max_context_chars": 2200,
    "min_score": 0.1,
    "title_boost": 0.45,
}

DEFAULT_PROMPTS_CONFIG = {
    "system_prompt": (
        "你是一个课程资料问答助手。"
        "回答必须优先依据给定资料，不能编造定义、步骤和结论。"
        "如果资料不足，要明确说出不确定，并给出下一步建议。"
    ),
    "user_prompt_template": (
        "问题：{question}\n\n"
        "可参考资料：\n{context}\n\n"
        "请先直接回答问题，再用简短语言说明依据、定义或步骤。"
    ),
    "suggested_questions": [
        "为什么文本数据通常使用余弦相似度？",
        "K-Means++ 的初始化步骤是什么？",
        "数据集成中的实体识别问题是什么意思？",
        "混合类型数据的相似度一般怎么计算？",
    ],
}

DEFAULT_AGENT_CONFIG = {
    "enabled": False,
    "provider": "openai_compatible",
    "api_key_env": "OPENAI_API_KEY",
    "base_url_env": "OPENAI_BASE_URL",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model_name": "qwen3-max",
    "temperature": 0.2,
    "max_tokens": 700,
    "timeout_seconds": 30,
}

DEFAULT_DATABASE_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "course_rag",
    "charset": "utf8mb4",
}


def _load_yaml_config(config_path: str, default_config: dict, encoding: str = "utf-8") -> dict:
    if not os.path.exists(config_path):
        logger.warning("[配置] 未找到配置文件 %s，使用默认配置", config_path)
        return deepcopy(default_config)

    with open(config_path, "r", encoding=encoding) as file:
        config = yaml.safe_load(file)

    if config is None:
        return deepcopy(default_config)
    if not isinstance(config, dict):
        raise ValueError(f"配置文件 {config_path} 必须是 YAML 对象")

    merged = deepcopy(default_config)
    merged.update(config)
    return merged


def load_rag_config(config_path: str = get_abs_path("config/rag.yml"), encoding: str = "utf-8") -> dict:
    return _load_yaml_config(config_path, DEFAULT_RAG_CONFIG, encoding)


def load_chroma_config(
    config_path: str = get_abs_path("config/chroma.yml"), encoding: str = "utf-8"
) -> dict:
    return _load_yaml_config(config_path, DEFAULT_CHROMA_CONFIG, encoding)


def load_prompts_config(
    config_path: str = get_abs_path("config/prompts.yml"), encoding: str = "utf-8"
) -> dict:
    return _load_yaml_config(config_path, DEFAULT_PROMPTS_CONFIG, encoding)


def load_agent_config(
    config_path: str = get_abs_path("config/agent.yml"), encoding: str = "utf-8"
) -> dict:
    merged = _load_yaml_config(config_path, DEFAULT_AGENT_CONFIG, encoding)

    api_key_name = merged.get("api_key_env")
    if api_key_name:
        merged["api_key"] = LOCAL_ENV_VALUES.get(api_key_name) or os.getenv(api_key_name)

    base_url_name = merged.get("base_url_env")
    if base_url_name:
        merged["base_url"] = LOCAL_ENV_VALUES.get(base_url_name) or os.getenv(base_url_name) or merged["base_url"]

    return merged


def load_database_config() -> dict:
    merged = deepcopy(DEFAULT_DATABASE_CONFIG)
    merged["host"] = LOCAL_ENV_VALUES.get("MYSQL_HOST") or os.getenv("MYSQL_HOST") or merged["host"]
    merged["port"] = int(LOCAL_ENV_VALUES.get("MYSQL_PORT") or os.getenv("MYSQL_PORT") or merged["port"])
    merged["user"] = LOCAL_ENV_VALUES.get("MYSQL_USER") or os.getenv("MYSQL_USER") or merged["user"]
    merged["password"] = LOCAL_ENV_VALUES.get("MYSQL_PASSWORD") or os.getenv("MYSQL_PASSWORD") or merged["password"]
    merged["database"] = LOCAL_ENV_VALUES.get("MYSQL_DATABASE") or os.getenv("MYSQL_DATABASE") or merged["database"]
    merged["charset"] = LOCAL_ENV_VALUES.get("MYSQL_CHARSET") or os.getenv("MYSQL_CHARSET") or merged["charset"]
    return merged


rag_conf = load_rag_config()
chroma_conf = load_chroma_config()
prompts_conf = load_prompts_config()
agent_conf = load_agent_config()
database_conf = load_database_config()


if __name__ == "__main__":
    print(rag_conf["chat_model_name"])
