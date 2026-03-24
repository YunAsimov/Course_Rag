import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from werkzeug.security import check_password_hash, generate_password_hash

from utils.logger_handler import logger
from utils.path_tool import get_abs_path

USERNAME_RE = re.compile(r"^[\w.@+\-\u4e00-\u9fff]{2,32}$")
MAX_HISTORY_PER_USER = 50


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class LocalAuthHistoryStore:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_root = Path(get_abs_path(storage_dir))
        self.users_path = self.storage_root / "users.json"
        self.history_path = self.storage_root / "history.json"
        self.secret_path = self.storage_root / "app_secret.txt"
        self._lock = threading.Lock()
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        if not self.users_path.exists():
            self._write_json(self.users_path, {"users": {}})
        if not self.history_path.exists():
            self._write_json(self.history_path, {"history": {}})
        if not self.secret_path.exists():
            self.secret_path.write_text(secrets.token_hex(32), encoding="utf-8")

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            if not path.exists():
                return default
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return default
            payload = json.loads(raw)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            logger.warning("[本地存储] JSON 文件损坏，使用默认值: %s", path)
        return default

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _normalize_username(self, username: str) -> str:
        return (username or "").strip()

    def _validate_username(self, username: str) -> str:
        normalized = self._normalize_username(username)
        if not normalized:
            return "用户名不能为空。"
        if not USERNAME_RE.fullmatch(normalized):
            return "用户名需为 2 到 32 个字符，只允许字母、数字、中文和 . _ @ + -。"
        return ""

    def _validate_password(self, password: str) -> str:
        if len(password or "") < 6:
            return "密码至少需要 6 个字符。"
        return ""

    def get_secret_key(self) -> str:
        self._ensure_storage()
        secret = self.secret_path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
        secret = secrets.token_hex(32)
        self.secret_path.write_text(secret, encoding="utf-8")
        return secret

    def _public_user(self, username: str, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "username": username,
            "created_at": record.get("created_at", ""),
        }

    def user_exists(self, username: str) -> bool:
        normalized = self._normalize_username(username)
        with self._lock:
            users = self._read_json(self.users_path, {"users": {}}).get("users", {})
        return normalized in users

    def register_user(self, username: str, password: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        username_error = self._validate_username(username)
        if username_error:
            return False, username_error, None
        password_error = self._validate_password(password)
        if password_error:
            return False, password_error, None

        normalized = self._normalize_username(username)
        with self._lock:
            payload = self._read_json(self.users_path, {"users": {}})
            users = payload.setdefault("users", {})
            if normalized in users:
                return False, "用户名已存在。", None

            users[normalized] = {
                "password_hash": generate_password_hash(password),
                "created_at": _utc_now_iso(),
            }
            self._write_json(self.users_path, payload)
            user = self._public_user(normalized, users[normalized])
        return True, "注册成功，已自动登录。", user

    def authenticate_user(self, username: str, password: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        normalized = self._normalize_username(username)
        if not normalized or not password:
            return False, "请输入用户名和密码。", None

        with self._lock:
            payload = self._read_json(self.users_path, {"users": {}})
            users = payload.get("users", {})
            record = users.get(normalized)
            if not record:
                return False, "用户不存在。", None
            if not check_password_hash(record.get("password_hash", ""), password):
                return False, "密码错误。", None
            user = self._public_user(normalized, record)
        return True, "登录成功。", user

    def append_history(
        self,
        username: str,
        question: str,
        answer: str,
        mode: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized = self._normalize_username(username)
        record = {
            "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}",
            "question": question,
            "answer": answer,
            "mode": mode,
            "sources": sources,
            "created_at": _utc_now_iso(),
        }
        with self._lock:
            payload = self._read_json(self.history_path, {"history": {}})
            history = payload.setdefault("history", {})
            user_history = history.setdefault(normalized, [])
            user_history.append(record)
            history[normalized] = user_history[-MAX_HISTORY_PER_USER:]
            self._write_json(self.history_path, payload)
        return record

    def list_history(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = self._normalize_username(username)
        with self._lock:
            payload = self._read_json(self.history_path, {"history": {}})
            history = payload.get("history", {})
            records = history.get(normalized, [])
        return list(reversed(records[-limit:]))

    def delete_history(self, username: str, record_id: str) -> bool:
        normalized = self._normalize_username(username)
        target_id = (record_id or "").strip()
        if not normalized or not target_id:
            return False

        with self._lock:
            payload = self._read_json(self.history_path, {"history": {}})
            history = payload.get("history", {})
            records = history.get(normalized, [])
            next_records = [record for record in records if record.get("id") != target_id]
            if len(next_records) == len(records):
                return False
            history[normalized] = next_records
            self._write_json(self.history_path, payload)
        return True
