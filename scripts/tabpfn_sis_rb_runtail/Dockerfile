FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

RUN pip install --no-cache-dir \
    "tabpfn==2.2.1" pandas pyarrow db-dtypes google-cloud-bigquery

RUN python -c "from tabpfn import TabPFNRegressor; TabPFNRegressor(device='cpu').fit([[0.],[1.],[2.],[3.]],[0.,1.,2.,3.])" || true

COPY scripts/tabpfn_sis_qb_line/gen.py /app/gen.py
COPY scripts/tabpfn_gen/features.txt /app/features_control.txt
COPY src/nfl_dfs/research/tabpfn_sis_rb_runtail.py /app/sis_rb_runtail.py

CMD ["python", "/app/gen.py"]
