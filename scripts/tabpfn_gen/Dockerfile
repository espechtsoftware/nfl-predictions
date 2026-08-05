FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
RUN pip install --no-cache-dir "tabpfn==2.2.1" pandas pyarrow db-dtypes google-cloud-bigquery
# Bake model weights into the image (2026-08-04 pre-mortem): runtime
# HuggingFace downloads were an external dependency on every Sunday run.
RUN python -c "from tabpfn import TabPFNRegressor; TabPFNRegressor(device='cpu').fit([[0.],[1.],[2.],[3.]],[0.,1.,2.,3.])" || true
COPY gen.py /app/gen.py
COPY features.txt /app/features.txt
CMD ["python", "/app/gen.py"]
