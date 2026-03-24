from app import app, service


if __name__ == "__main__":
    rag_conf = service.rag_conf
    print(app.url_map, flush=True)
    app.run(
        host=rag_conf["host"],
        port=rag_conf["port"],
        debug=rag_conf["debug"],
    )
