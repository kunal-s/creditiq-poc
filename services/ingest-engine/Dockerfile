# syntax=docker/dockerfile:1.7
# The CreditIQ document-processing sidecar. Build from this directory:
#   docker build -t creditiq-ingest .
# Run with the data root mounted and an API key (a non-loopback bind needs one):
#   docker run -e INGEST_API_KEY=... -e CREDITIQ_DATA_ROOT=/data -v <root>:/data -p 3102:3102 creditiq-ingest
ARG NODE_VERSION=22
FROM node:${NODE_VERSION}-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm install --no-save tsx@^4.19.2

FROM node:${NODE_VERSION}-bookworm-slim
ENV NODE_ENV=production INGEST_PORT=3102 INGEST_HOST=0.0.0.0
WORKDIR /app
# Runtime hardening: current Debian security fixes, and no package manager in the image.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx /opt/yarn* /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY --from=deps /app/node_modules ./node_modules
COPY package.json tsconfig.json ./
COPY src ./src
RUN chown -R node:node /app
USER node
EXPOSE 3102
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3102/v1/health',{headers:{'x-api-key':process.env.INGEST_API_KEY||''}}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "node_modules/.bin/tsx", "src/main.ts"]
