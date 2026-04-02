FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG APP_BUILD_VERSION=20260403-1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt \
    && python -m pip install "cryptography>=42.0"

COPY . /app

RUN mkdir -p /app/logs /app/storage/materials

EXPOSE 7860

CMD ["gunicorn", "--config", "gunicorn.conf.py", "course_rag:app"]
