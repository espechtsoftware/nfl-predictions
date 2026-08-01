FROM python:3.11-slim

WORKDIR /app

# libgomp is needed by LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md CLAUDE.md ./
COPY reports/model-primer.md ./reports/model-primer.md
COPY src ./src
COPY sql ./sql

RUN pip install --no-cache-dir ".[gcp,app]"

# Cloud Run Jobs override the command per job; the default serves the UI.
CMD ["uvicorn", "nfl_dfs.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
