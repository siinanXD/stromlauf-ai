# Stromlauf-Backend fuer Railway (oder jeden Container-Host). Build-Kontext ist backend/.
# CPU-Torch vor Docling, sonst zieht pip die CUDA-Variante (mehrere GB).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    HF_HOME=/data/hf

# opencv (Docling-Layoutmodelle) braucht libGL/libglib
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./

# Abhaengigkeiten vor dem Code: Dieser Layer (Torch, Docling, rund 640 MB) bleibt im Build-Cache, solange sich
# pyproject.toml nicht aendert. Fuer das editable Install genuegen leere Paketordner, der Code kommt danach.
# torch UND torchvision aus dem CPU-Index: ein torchvision von PyPI passt nicht zum CPU-torch
# ("operator torchvision::nms does not exist" beim ersten Embedding)
RUN mkdir -p app stromlauf_mcp \
    && touch app/__init__.py stromlauf_mcp/__init__.py \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -e ".[trace]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY stromlauf_mcp ./stromlauf_mcp

# Uploads, Bilder, Plan-Cache und HF-Modelle liegen unter /data (Railway-Volume mounten)
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8010
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}"]
