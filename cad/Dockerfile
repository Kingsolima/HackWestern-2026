FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglu1-mesa libxrender1 libxext6 libsm6 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir "cadquery>=2.5" numpy "trimesh>=4" fastapi "uvicorn[standard]"
COPY cad_worker ./cad_worker
COPY assets ./assets
ENV CAD_OUT_DIR=/app/out
EXPOSE 8001
CMD ["uvicorn", "cad_worker.server:app", "--host", "0.0.0.0", "--port", "8001"]
