FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r /workspace/requirements.txt

COPY app /workspace/app
COPY alembic /workspace/alembic
COPY alembic.ini /workspace/alembic.ini

ENTRYPOINT ["python", "-m", "app.periphery.cli.main"]
CMD ["--help"]
