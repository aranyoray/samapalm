# SWHT-PP-003 analysis environment. CPU by default; pass --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu121
# on a GPU host. The lock file pins every Python package; the base image pins the OS.
FROM python:3.13-slim-bookworm AS base
ARG TORCH_INDEX=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MLFLOW_DISABLE_AGENT_HINT=1 OMP_NUM_THREADS=4
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg rsync libgl1 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv==0.9.5
WORKDIR /app
COPY environment.lock pyproject.toml ./
RUN uv pip install --system --no-cache -r environment.lock --extra-index-url ${TORCH_INDEX}
COPY . .
RUN uv pip install --system --no-deps -e .
ENTRYPOINT ["palmppg"]
CMD ["--help"]
