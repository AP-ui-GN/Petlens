# Analysis API plus the Python gait pipeline.
# Node 24 LTS. Python 3.11 from Debian bookworm. The pins also support 3.10 and 3.12.
# CPU torch. Detector and pose weights download while the image builds.

FROM node:24-bookworm-slim AS build

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates python3 \
  && rm -rf /var/lib/apt/lists/*

RUN corepack enable && corepack prepare pnpm@10.33.4 --activate

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY artifacts ./artifacts
COPY lib ./lib
COPY scripts ./scripts
COPY gait_engine ./gait_engine

RUN pnpm install --frozen-lockfile --filter @workspace/api-server...
RUN pnpm --filter @workspace/api-server run build

FROM node:24-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-venv \
    python3-pip \
    libglib2.0-0 \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /app/artifacts/api-server/dist ./artifacts/api-server/dist
COPY gait_engine ./gait_engine
COPY scripts/analyze_clip.py scripts/cache_models.py scripts/check_setup.py ./scripts/
COPY requirements-docker.txt ./

RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r requirements-docker.txt \
  && HF_HOME=/app/models/hf /opt/venv/bin/python scripts/cache_models.py

ENV NODE_ENV=production \
    PORT=8080 \
    SILVERPAWS_PYTHON=/opt/venv/bin/python \
    SILVERPAWS_REPO_ROOT=/app \
    HF_HOME=/app/models/hf \
    MAX_UPLOAD_MB=60 \
    ANALYSIS_TIMEOUT_MS=600000 \
    SHUTDOWN_TIMEOUT_MS=15000 \
    ANALYZE_MAX_CONCURRENT=1 \
    ANALYZE_RATE_LIMIT_PER_MINUTE=10

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||8080)+'/api/healthz').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "--enable-source-maps", "artifacts/api-server/dist/index.mjs"]
