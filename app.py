from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for

from utils.local_store import LocalAuthHistoryStore
from utils.path_tool import get_abs_path
from utils.rag_service import RAGService

service = RAGService()
store = LocalAuthHistoryStore()


def create_app() -> Flask:
    app = Flask(__name__, template_folder=".", static_folder=None)
    app.secret_key = store.get_secret_key()
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_NAME="comp5575_rag_session",
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

    return app


app = create_app()


if __name__ == "__main__":
    rag_conf = service.rag_conf
    app.run(
        host=rag_conf["host"],
        port=rag_conf["port"],
        debug=rag_conf["debug"],
    )
