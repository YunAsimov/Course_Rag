from course_rag import app, service_manager, store


if __name__ == "__main__":
    rag_conf = service_manager.rag_conf
    app.run(
        host=rag_conf["host"],
        port=rag_conf["port"],
        debug=rag_conf["debug"],
    )
