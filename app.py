import re
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from utils.local_store import LocalAuthHistoryStore
from utils.path_tool import get_abs_path
from utils.rag_service import RAGService

service = RAGService()
store = LocalAuthHistoryStore()
UPLOAD_FILENAME_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._()\-\s]+")


def _sanitize_upload_filename(raw_name: str) -> str:
    candidate = Path((raw_name or "").strip()).name.replace("\x00", "")
    suffix = Path(candidate).suffix.lower()
    stem = Path(candidate).stem.strip()
    safe_stem = UPLOAD_FILENAME_RE.sub("_", stem).strip(" ._")
    if not safe_stem:
        safe_stem = "course_material"
    return f"{safe_stem}{suffix}"


def _resolve_upload_target(directory: Path, file_name: str) -> Path:
    base_name = _sanitize_upload_filename(file_name)
    stem = Path(base_name).stem
    suffix = Path(base_name).suffix
    target = directory / base_name
    counter = 1
    while target.exists():
        target = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return target


def create_app() -> Flask:
    app = Flask(__name__, template_folder=".", static_folder=None)
    app.secret_key = store.get_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="comp5575_rag_session",
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,
    )
    data_root = Path(service.data_dir).resolve()

    def current_username() -> str:
        username = (session.get("username") or "").strip()
        if not username:
            return ""
        if not store.user_exists(username):
            session.pop("username", None)
            return ""
        return username

    @app.get("/")
    def index():
        username = current_username()
        if not username:
            return redirect(url_for("login_page"))
        context = service.get_ui_context()
        context["current_user"] = username
        return render_template("dashboard.html", **context)

    @app.get("/login")
    def login_page():
        if current_username():
            return redirect(url_for("index"))
        context = service.get_ui_context()
        return render_template("auth.html", **context)

    @app.post("/api/ask")
    def ask():
        username = current_username()
        if not username:
            return jsonify(
                {
                    "answer": "请先登录后再提问。",
                    "mode": "auth_required",
                    "sources": [],
                    "history_saved": False,
                }
            ), 401
        payload = request.get_json(silent=True) or {}
        question = payload.get("question", "")
        result = service.ask(question)
        if username and question.strip():
            record = store.append_history(
                username=username,
                question=result.get("question", question.strip()),
                answer=result.get("answer", ""),
                mode=result.get("mode", ""),
                sources=result.get("sources", []),
            )
            result["history_saved"] = True
            result["history_id"] = record["id"]
        else:
            result["history_saved"] = False
        return jsonify(result)

    @app.get("/api/auth/me")
    def auth_me():
        username = current_username()
        return jsonify(
            {
                "authenticated": bool(username),
                "username": username,
            }
        )

    @app.post("/api/auth/register")
    def register():
        payload = request.get_json(silent=True) or {}
        ok, message, user = store.register_user(
            payload.get("username", ""),
            payload.get("password", ""),
        )
        if not ok:
            status_code = 409 if "已存在" in message else 400
            return jsonify({"authenticated": False, "message": message}), status_code

        session["username"] = user["username"]
        return jsonify(
            {
                "authenticated": True,
                "username": user["username"],
                "message": message,
            }
        )

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True) or {}
        ok, message, user = store.authenticate_user(
            payload.get("username", ""),
            payload.get("password", ""),
        )
        if not ok:
            return jsonify({"authenticated": False, "message": message}), 401

        session["username"] = user["username"]
        return jsonify(
            {
                "authenticated": True,
                "username": user["username"],
                "message": message,
            }
        )

    @app.post("/api/auth/logout")
    def logout():
        session.pop("username", None)
        return jsonify({"authenticated": False, "message": "已退出登录。"})

    @app.get("/api/history")
    def history():
        username = current_username()
        if not username:
            return jsonify(
                {
                    "authenticated": False,
                    "username": "",
                    "history": [],
                }
            ), 401

        return jsonify(
            {
                "authenticated": True,
                "username": username,
                "history": store.list_history(username),
            }
        )

    @app.route("/api/history/<record_id>", methods=["DELETE"])
    def delete_history(record_id: str):
        username = current_username()
        if not username:
            return jsonify({"authenticated": False, "message": "请先登录。"}), 401
        if not store.delete_history(username, record_id):
            return jsonify({"authenticated": True, "deleted": False, "message": "历史记录不存在。"}), 404
        return jsonify({"authenticated": True, "deleted": True, "record_id": record_id})

    @app.post("/api/history/delete")
    def delete_history_post():
        payload = request.get_json(silent=True) or {}
        return delete_history(str(payload.get("record_id", "")))

    @app.post("/api/upload")
    def upload_materials():
        username = current_username()
        if not username:
            return jsonify({"authenticated": False, "message": "请先登录。"}), 401

        uploaded_files = request.files.getlist("files")
        if not uploaded_files:
            return jsonify({"uploaded": False, "message": "请选择至少一个文件。"}), 400

        saved_paths: list[Path] = []
        saved_names: list[str] = []
        allowed_extensions = {extension.lower() for extension in service.allowed_extensions}
        data_root.mkdir(parents=True, exist_ok=True)

        try:
            for uploaded in uploaded_files:
                raw_name = (uploaded.filename or "").strip()
                if not raw_name:
                    continue

                safe_name = _sanitize_upload_filename(raw_name)
                suffix = Path(safe_name).suffix.lower()
                if suffix not in allowed_extensions:
                    return jsonify(
                        {
                            "uploaded": False,
                            "message": f"暂不支持 {suffix or '该类型'} 文件。当前仅允许：{', '.join(sorted(allowed_extensions))}",
                            "allowed_extensions": sorted(allowed_extensions),
                        }
                    ), 400

                target_path = _resolve_upload_target(data_root, safe_name)
                uploaded.save(target_path)
                saved_paths.append(target_path)
                saved_names.append(target_path.name)

            if not saved_paths:
                return jsonify({"uploaded": False, "message": "没有检测到可上传的有效文件。"}), 400

            stats = service.reload_index()
        except Exception:
            for saved_path in saved_paths:
                if saved_path.exists():
                    saved_path.unlink()
            service.reload_index()
            raise

        return jsonify(
            {
                "uploaded": True,
                "message": f"已上传 {len(saved_names)} 个文件，并完成知识库刷新。",
                "files": saved_names,
                "stats": stats,
            }
        )

    @app.get("/api/files")
    def list_files():
        username = current_username()
        if not username:
            return jsonify({"authenticated": False, "message": "请先登录。", "files": []}), 401
        return jsonify(
            {
                "authenticated": True,
                "files": service.list_material_files(),
            }
        )

    @app.delete("/api/files")
    def delete_file():
        username = current_username()
        if not username:
            return jsonify({"authenticated": False, "message": "请先登录。"}), 401

        payload = request.get_json(silent=True) or {}
        relative_path = str(payload.get("path", "")).strip()
        if not relative_path:
            return jsonify({"authenticated": True, "deleted": False, "message": "缺少待删除的文件路径。"}), 400

        try:
            result = service.delete_material_file(relative_path)
        except FileNotFoundError:
            return jsonify({"authenticated": True, "deleted": False, "message": "目标文件不存在或已被删除。"}), 404
        except PermissionError:
            return jsonify({"authenticated": True, "deleted": False, "message": "不允许删除该文件。"}), 403
        except ValueError as exc:
            return jsonify({"authenticated": True, "deleted": False, "message": str(exc)}), 400

        return jsonify(
            {
                "authenticated": True,
                "deleted": True,
                "message": f"已删除 {result['name']}，并刷新知识库。",
                "file": {
                    "name": result["name"],
                    "path": result["path"],
                },
                "stats": result["stats"],
            }
        )

    @app.get("/api/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "documents": service.index_summary.get("documents", 0),
                "chunks": service.index_summary.get("chunks", 0),
                "backend": service.index_summary.get("backend"),
            }
        )

    @app.get("/api/source")
    def source():
        relative_path = (request.args.get("path") or "").strip()
        if not relative_path:
            abort(400)

        source_path = Path(get_abs_path(relative_path)).resolve()
        if source_path != data_root and data_root not in source_path.parents:
            abort(403)
        if not source_path.is_file():
            abort(404)
        return send_file(source_path, conditional=True)

    @app.get("/assets/styles.css")
    def styles():
        return send_file(get_abs_path("styles.css"))

    @app.get("/assets/app.js")
    def script():
        return send_file(get_abs_path("app.js"))

    @app.get("/assets/auth.js")
    def auth_script():
        return send_file(get_abs_path("auth.js"))

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_: RequestEntityTooLarge):
        if request.path.startswith("/api/"):
            return jsonify({"uploaded": False, "message": "文件过大，请控制在 20MB 以内。"}), 413
        return "文件过大，请控制在 20MB 以内。", 413

    return app


app = create_app()


if __name__ == "__main__":
    rag_conf = service.rag_conf
    app.run(
        host=rag_conf["host"],
        port=rag_conf["port"],
        debug=rag_conf["debug"],
    )
