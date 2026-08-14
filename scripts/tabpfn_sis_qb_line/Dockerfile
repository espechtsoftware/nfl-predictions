FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

RUN pip install --no-cache-dir \
    "tabpfn==2.2.1" pandas pyarrow db-dtypes google-cloud-bigquery

# Bake weights into the immutable image; do not download at execution time.
RUN python -c "from tabpfn import TabPFNRegressor; TabPFNRegressor(device='cpu').fit([[0.],[1.],[2.],[3.]],[0.,1.,2.,3.])" || true

COPY scripts/tabpfn_sis_qb_line/gen.py /app/gen.py
COPY scripts/tabpfn_gen/features.txt /app/features_control.txt
COPY src/nfl_dfs/research/tabpfn_sis_qb_line.py /app/sis_qb_line.py
COPY src/nfl_dfs/research/tabpfn_sis_pass_tail.py /app/sis_pass_tail.py

CMD ["python", "/app/gen.py"]
