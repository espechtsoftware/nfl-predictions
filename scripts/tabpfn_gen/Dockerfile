FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
RUN pip install --no-cache-dir "tabpfn==2.2.1" pandas pyarrow db-dtypes google-cloud-bigquery
COPY gen.py /app/gen.py
COPY features.txt /app/features.txt
CMD ["python", "/app/gen.py"]
