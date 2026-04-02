import multiprocessing
import os


bind = os.getenv("GUNICORN_BIND", "0.0.0.0:7860")
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
workers = int(os.getenv("GUNICORN_WORKERS", max(2, min(4, multiprocessing.cpu_count()))))
threads = int(os.getenv("GUNICORN_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "10"))

accesslog = "-"
errorlog = "-"
capture_output = True

