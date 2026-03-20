FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /workspace/requirements.txt
COPY pyproject.toml /workspace/pyproject.toml
COPY README.md /workspace/README.md
COPY app /workspace/app
COPY alembic.ini /workspace/alembic.ini
RUN pip install --no-cache-dir -r /workspace/requirements.txt \
    && pip install --no-cache-dir --no-deps -e /workspace

ENTRYPOINT ["shellbrain"]
CMD ["--help"]
