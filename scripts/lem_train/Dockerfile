FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
RUN pip install --no-cache-dir pandas pyarrow gcsfs google-cloud-storage scipy
COPY train_lem.py /app/train_lem.py
COPY rollout_eval.py /app/rollout_eval.py
CMD ["python", "/app/train_lem.py"]
