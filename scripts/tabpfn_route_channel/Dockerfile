FROM us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-active-label@sha256:d0830d9fb79643fd77faa0d8c80f4863c1769adb56d6d1782999d5aa0f40139b

COPY scripts/tabpfn_route_channel/gen.py /app/gen.py

CMD ["python", "/app/gen.py"]
