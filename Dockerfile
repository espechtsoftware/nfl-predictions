FROM python:3.11-slim

WORKDIR /app

# libgomp is needed by LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md CLAUDE.md ./
COPY reports/model-primer.md ./reports/model-primer.md
COPY src ./src
COPY sql ./sql
COPY scripts/harvest_accept.py ./scripts/harvest_accept.py
COPY scripts/compare_adoption_panel.py ./scripts/compare_adoption_panel.py
COPY scripts/compare_k1_ce_panel.py ./scripts/compare_k1_ce_panel.py
COPY scripts/compare_k1_role_belief_panel.py ./scripts/compare_k1_role_belief_panel.py
COPY scripts/compare_k1_milly_ownership_panel.py ./scripts/compare_k1_milly_ownership_panel.py
COPY scripts/compare_exact_replay.py ./scripts/compare_exact_replay.py
COPY scripts/compare_role_belief_panel.py ./scripts/compare_role_belief_panel.py
COPY scripts/evaluate_milly_ownership.py ./scripts/evaluate_milly_ownership.py
COPY scripts/evaluate_k1_ce_reranker.py ./scripts/evaluate_k1_ce_reranker.py
COPY scripts/run_conditional_schaake_smoke.py ./scripts/run_conditional_schaake_smoke.py

RUN pip install --no-cache-dir ".[gcp,app]"

# Cloud Run Jobs override the command per job; the default serves the UI.
CMD ["uvicorn", "nfl_dfs.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
