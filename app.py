from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file

from utils.path_tool import get_abs_path
from utils.rag_service import RAGService

service = RAGService()


def create_app() -> Flask:
    app = Flask(__name__, template_folder=".", static_folder=None)
    data_root = Path(service.data_dir).resolve()

    @app.get("/")
    def index():
        context = service.get_ui_context()
        return render_template("index.html", **context)

    @app.post("/api/ask")
    def ask():
        payload = request.get_json(silent=True) or {}
        question = payload.get("question", "")
        return jsonify(service.ask(question))

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

    return app


app = create_app()


if __name__ == "__main__":
    rag_conf = service.rag_conf
    app.run(
        host=rag_conf["host"],
        port=rag_conf["port"],
        debug=rag_conf["debug"],
    )
