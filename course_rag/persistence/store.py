import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from course_rag.core.config_handler import load_database_config, load_rag_config
from course_rag.core.file_handler import get_md5_file_hex, listdir_with_allowed_type
from course_rag.core.logger_handler import logger
from course_rag.core.path_tool import get_abs_path

USERNAME_RE = re.compile(r"^[\w.@+\-\u4e00-\u9fff]{2,32}$")
MAX_HISTORY_PER_USER = 50


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _coerce_iso_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return str(value or "").strip()


def _coerce_mysql_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.replace(microsecond=0)

    text = str(value or "").strip()
    if not text:
        return _utc_now().replace(tzinfo=None)

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.replace(microsecond=0)
    except ValueError:
        return _utc_now().replace(tzinfo=None)


class MySQLProjectStore:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_root = Path(get_abs_path(storage_dir))
        self.secret_path = self.storage_root / "app_secret.txt"
        self.legacy_users_path = self.storage_root / "users.json"
        self.legacy_history_path = self.storage_root / "history.json"
        self._lock = threading.RLock()

        self.database_conf = load_database_config()
        self.rag_conf = load_rag_config()
        self.materials_root = Path(get_abs_path(self.rag_conf["user_materials_root"]))
        self.bootstrap_data_root = Path(get_abs_path(self.rag_conf["data_dir"]))
        self.bootstrap_owner = self.rag_conf.get("bootstrap_owner", "lyy")
        self.allowed_extensions = tuple(self.rag_conf["allowed_extensions"])

        self._ensure_storage()
        self._ensure_database()
        self._ensure_schema()
        self._migrate_legacy_storage()

    def _ensure_storage(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.materials_root.mkdir(parents=True, exist_ok=True)
        if not self.secret_path.exists():
            self.secret_path.write_text(secrets.token_hex(32), encoding="utf-8")

    def _server_connection(self):
        return pymysql.connect(
            host=self.database_conf["host"],
            port=int(self.database_conf["port"]),
            user=self.database_conf["user"],
            password=self.database_conf["password"],
            charset=self.database_conf["charset"],
            autocommit=True,
            cursorclass=DictCursor,
        )

    def _db_connection(self):
        return pymysql.connect(
            host=self.database_conf["host"],
            port=int(self.database_conf["port"]),
            user=self.database_conf["user"],
            password=self.database_conf["password"],
            database=self.database_conf["database"],
            charset=self.database_conf["charset"],
            autocommit=True,
            cursorclass=DictCursor,
        )

    def _ensure_database(self) -> None:
        with self._server_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    (
                        f"CREATE DATABASE IF NOT EXISTS `{self.database_conf['database']}` "
                        f"CHARACTER SET {self.database_conf['charset']} "
                        f"COLLATE {self.database_conf['charset']}_unicode_ci"
                    )
                )

    def _ensure_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS history (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                record_id VARCHAR(64) NOT NULL UNIQUE,
                user_id BIGINT NOT NULL,
                question TEXT NOT NULL,
                answer MEDIUMTEXT NOT NULL,
                mode VARCHAR(64) NOT NULL,
                sources_json LONGTEXT NOT NULL,
                created_at DATETIME NOT NULL,
                INDEX idx_history_user_created (user_id, created_at),
                CONSTRAINT fk_history_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_materials (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                relative_path VARCHAR(512) NOT NULL,
                absolute_path VARCHAR(1024) NOT NULL,
                doc_type VARCHAR(32) NOT NULL,
                size_bytes BIGINT NOT NULL DEFAULT 0,
                md5 CHAR(32) NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE KEY uniq_user_relative (user_id, relative_path),
                INDEX idx_materials_user_updated (user_id, updated_at),
                CONSTRAINT fk_materials_user FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)

    def _read_legacy_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
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
            logger.warning("[MySQL迁移] 旧 JSON 文件损坏，跳过: %s", path)
        return default

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

    def _public_user(self, username: str, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "username": username,
            "created_at": _coerce_iso_datetime(record.get("created_at")),
        }

    def _fetch_user_row(self, username: str) -> Optional[dict[str, Any]]:
        normalized = self._normalize_username(username)
        if not normalized:
            return None
        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash, created_at FROM users WHERE username = %s",
                    (normalized,),
                )
                return cursor.fetchone()

    def _fetch_user_id(self, username: str) -> Optional[int]:
        row = self._fetch_user_row(username)
        if not row:
            return None
        return int(row["id"])

    def get_secret_key(self) -> str:
        self._ensure_storage()
        secret = self.secret_path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
        secret = secrets.token_hex(32)
        self.secret_path.write_text(secret, encoding="utf-8")
        return secret

    def get_user_material_dir(self, username: str) -> Path:
        normalized = self._normalize_username(username)
        if not normalized:
            raise ValueError("用户名不能为空。")
        material_dir = self.materials_root / normalized
        material_dir.mkdir(parents=True, exist_ok=True)
        return material_dir

    def user_exists(self, username: str) -> bool:
        return self._fetch_user_row(username) is not None

    def register_user(self, username: str, password: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        username_error = self._validate_username(username)
        if username_error:
            return False, username_error, None
        password_error = self._validate_password(password)
        if password_error:
            return False, password_error, None

        normalized = self._normalize_username(username)
        created_at = _utc_now()
        try:
            with self._db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, created_at)
                        VALUES (%s, %s, %s)
                        """,
                        (normalized, generate_password_hash(password), created_at),
                    )
            self.get_user_material_dir(normalized)
        except pymysql.err.IntegrityError:
            return False, "用户名已存在。", None

        return True, "注册成功，已自动登录。", self._public_user(
            normalized,
            {"created_at": created_at},
        )

    def authenticate_user(self, username: str, password: str) -> tuple[bool, str, Optional[dict[str, Any]]]:
        normalized = self._normalize_username(username)
        if not normalized or not password:
            return False, "请输入用户名和密码。", None

        record = self._fetch_user_row(normalized)
        if not record:
            return False, "用户不存在。", None
        if not check_password_hash(record.get("password_hash", ""), password):
            return False, "密码错误。", None

        self.get_user_material_dir(normalized)
        return True, "登录成功。", self._public_user(normalized, record)

    def append_history(
        self,
        username: str,
        question: str,
        answer: str,
        mode: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        normalized = self._normalize_username(username)
        user_id = self._fetch_user_id(normalized)
        if not user_id:
            raise ValueError("用户不存在。")

        created_at = _utc_now()
        record = {
            "id": f"{created_at.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}",
            "question": question,
            "answer": answer,
            "mode": mode,
            "sources": sources,
            "created_at": _coerce_iso_datetime(created_at),
        }

        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO history (record_id, user_id, question, answer, mode, sources_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record["id"],
                        user_id,
                        question,
                        answer,
                        mode,
                        json.dumps(sources, ensure_ascii=False),
                        created_at,
                    ),
                )
                cursor.execute(
                    """
                    SELECT record_id FROM history
                    WHERE user_id = %s
                    ORDER BY created_at DESC, id DESC
                    """,
                    (user_id,),
                )
                stale_rows = cursor.fetchall()[MAX_HISTORY_PER_USER:]
                if stale_rows:
                    stale_ids = [row["record_id"] for row in stale_rows]
                    placeholders = ", ".join(["%s"] * len(stale_ids))
                    cursor.execute(
                        f"DELETE FROM history WHERE user_id = %s AND record_id IN ({placeholders})",
                        [user_id] + stale_ids,
                    )

        return record

    def list_history(self, username: str, limit: int = 20) -> list[dict[str, Any]]:
        normalized = self._normalize_username(username)
        user_id = self._fetch_user_id(normalized)
        if not user_id:
            return []

        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT record_id, question, answer, mode, sources_json, created_at
                    FROM history
                    WHERE user_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (user_id, int(limit)),
                )
                rows = cursor.fetchall()

        records: list[dict[str, Any]] = []
        for row in rows:
            try:
                sources = json.loads(row.get("sources_json") or "[]")
            except json.JSONDecodeError:
                sources = []
            records.append(
                {
                    "id": row.get("record_id", ""),
                    "question": row.get("question", ""),
                    "answer": row.get("answer", ""),
                    "mode": row.get("mode", ""),
                    "sources": sources,
                    "created_at": _coerce_iso_datetime(row.get("created_at")),
                }
            )
        return records

    def delete_history(self, username: str, record_id: str) -> bool:
        normalized = self._normalize_username(username)
        target_id = (record_id or "").strip()
        user_id = self._fetch_user_id(normalized)
        if not user_id or not target_id:
            return False

        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM history WHERE user_id = %s AND record_id = %s",
                    (user_id, target_id),
                )
                return cursor.rowcount > 0

    def sync_materials(self, username: str, allowed_extensions: Optional[tuple[str, ...]] = None) -> list[dict[str, Any]]:
        normalized = self._normalize_username(username)
        user_id = self._fetch_user_id(normalized)
        if not user_id:
            return []

        material_dir = self.get_user_material_dir(normalized)
        allowed = tuple(allowed_extensions or self.allowed_extensions)
        file_paths = listdir_with_allowed_type(str(material_dir), allowed)
        project_root = Path(get_abs_path(".")).resolve()
        now = _utc_now()
        relative_paths: list[str] = []

        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                for file_path in file_paths:
                    stat = os.stat(file_path)
                    file_name = Path(file_path).name
                    relative_path = os.path.relpath(file_path, project_root)
                    relative_paths.append(relative_path)
                    cursor.execute(
                        """
                        INSERT INTO user_materials (
                            user_id, file_name, relative_path, absolute_path, doc_type,
                            size_bytes, md5, created_at, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            file_name = VALUES(file_name),
                            absolute_path = VALUES(absolute_path),
                            doc_type = VALUES(doc_type),
                            size_bytes = VALUES(size_bytes),
                            md5 = VALUES(md5),
                            updated_at = VALUES(updated_at)
                        """,
                        (
                            user_id,
                            file_name,
                            relative_path,
                            str(Path(file_path).resolve()),
                            Path(file_path).suffix.lower(),
                            int(stat.st_size),
                            get_md5_file_hex(file_path),
                            now.replace(tzinfo=None),
                            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0),
                        ),
                    )

                if relative_paths:
                    placeholders = ", ".join(["%s"] * len(relative_paths))
                    cursor.execute(
                        f"DELETE FROM user_materials WHERE user_id = %s AND relative_path NOT IN ({placeholders})",
                        [user_id] + relative_paths,
                    )
                else:
                    cursor.execute("DELETE FROM user_materials WHERE user_id = %s", (user_id,))

        return self.list_materials(normalized, sync=False)

    def list_materials(self, username: str, sync: bool = True) -> list[dict[str, Any]]:
        normalized = self._normalize_username(username)
        user_id = self._fetch_user_id(normalized)
        if not user_id:
            return []

        if sync:
            self.sync_materials(normalized, self.allowed_extensions)

        with self._db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT file_name, relative_path, doc_type, size_bytes, updated_at
                    FROM user_materials
                    WHERE user_id = %s
                    ORDER BY updated_at DESC, file_name ASC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()

        materials: list[dict[str, Any]] = []
        for row in rows:
            file_name = row.get("file_name", "")
            materials.append(
                {
                    "name": file_name,
                    "title": Path(file_name).stem,
                    "path": row.get("relative_path", ""),
                    "doc_type": row.get("doc_type", ""),
                    "size_bytes": int(row.get("size_bytes") or 0),
                    "updated_at": int((row.get("updated_at") or _utc_now()).timestamp()),
                }
            )
        return materials

    def seed_user_materials(self, username: str) -> int:
        normalized = self._normalize_username(username)
        if not normalized or not self.bootstrap_data_root.exists():
            return 0

        target_root = self.get_user_material_dir(normalized)
        existing_files = listdir_with_allowed_type(str(target_root), self.allowed_extensions)
        if existing_files:
            return 0

        copied_count = 0
        source_files = listdir_with_allowed_type(str(self.bootstrap_data_root), self.allowed_extensions)
        for source_file in source_files:
            source_path = Path(source_file)
            relative_path = source_path.relative_to(self.bootstrap_data_root)
            target_path = target_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            copied_count += 1

        if copied_count:
            self.sync_materials(normalized, self.allowed_extensions)
        return copied_count

    def _rewrite_legacy_sources(self, username: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = self._normalize_username(username)
        if not sources:
            return []

        project_root = Path(get_abs_path(".")).resolve()
        user_root = self.get_user_material_dir(normalized).resolve()
        rewritten: list[dict[str, Any]] = []
        for source in sources:
            current = dict(source)
            source_path_text = str(current.get("path", "")).strip()
            if source_path_text:
                source_path = (project_root / source_path_text).resolve()
                if (
                    self.bootstrap_data_root.exists()
                    and (source_path == self.bootstrap_data_root or self.bootstrap_data_root in source_path.parents)
                ):
                    try:
                        relative = source_path.relative_to(self.bootstrap_data_root)
                        candidate = user_root / relative
                        if candidate.exists():
                            current["path"] = os.path.relpath(candidate, project_root)
                    except ValueError:
                        pass
            rewritten.append(current)
        return rewritten

    def _migrate_legacy_storage(self) -> None:
        legacy_users = self._read_legacy_json(self.legacy_users_path, {"users": {}}).get("users", {})
        legacy_history = self._read_legacy_json(self.legacy_history_path, {"history": {}}).get("history", {})

        for username, record in legacy_users.items():
            normalized = self._normalize_username(username)
            if not normalized:
                continue
            with self._db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, created_at)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE username = username
                        """,
                        (
                            normalized,
                            record.get("password_hash", ""),
                            _coerce_mysql_datetime(record.get("created_at")),
                        ),
                    )
            self.get_user_material_dir(normalized)

        if self.user_exists(self.bootstrap_owner):
            copied = self.seed_user_materials(self.bootstrap_owner)
            if copied:
                logger.info("[MySQL迁移] 已将 %s 个默认资料文件复制到用户 %s 私有目录", copied, self.bootstrap_owner)

        for username, records in legacy_history.items():
            normalized = self._normalize_username(username)
            # Legacy bootstrap data belongs only to the configured default owner.
            # Other users should start with an empty history and build their own.
            if normalized != self.bootstrap_owner:
                continue
            user_id = self._fetch_user_id(normalized)
            if not user_id:
                continue
            for record in records:
                sources = self._rewrite_legacy_sources(normalized, record.get("sources", []))
                with self._db_connection() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO history (record_id, user_id, question, answer, mode, sources_json, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE record_id = record_id
                            """,
                            (
                                record.get("id"),
                                user_id,
                                record.get("question", ""),
                                record.get("answer", ""),
                                record.get("mode", ""),
                                json.dumps(sources, ensure_ascii=False),
                                _coerce_mysql_datetime(record.get("created_at")),
                            ),
                        )

        for username in list(legacy_users.keys()):
            normalized = self._normalize_username(username)
            if normalized:
                self.sync_materials(normalized, self.allowed_extensions)


