FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

RUN pip install --no-cache-dir \
    "tabpfn==2.2.1" pandas pyarrow db-dtypes google-cloud-bigquery

# Bake the pretrained weights into the immutable image so the diagnostic does
# not depend on a runtime model download.
RUN python -c "from tabpfn import TabPFNRegressor; TabPFNRegressor(device='cpu').fit([[0.],[1.],[2.],[3.]],[0.,1.,2.,3.])" || true

COPY scripts/tabpfn_active_label/gen.py /app/gen.py
COPY scripts/tabpfn_gen/features.txt /app/features.txt

CMD ["python", "/app/gen.py"]
