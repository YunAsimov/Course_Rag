__all__ = ["app", "create_app", "service_manager", "store"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module 'course_rag' has no attribute {name!r}")

    from course_rag.web import app, create_app, service_manager, store

    exports = {
        "app": app,
        "create_app": create_app,
        "service_manager": service_manager,
        "store": store,
    }
    return exports[name]
