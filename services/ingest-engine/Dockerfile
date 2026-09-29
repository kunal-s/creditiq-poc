# syntax=docker/dockerfile:1.7
# The ingestion engine, alone. PKG is the package's path inside the build context:
#   from the monorepo root:   docker build -f packages/ingest-engine/Dockerfile -t ingest-engine .
#   from this directory:      docker build --build-arg PKG=. -t ingest-engine .
# (start.sh works this out for you.)
ARG NODE_VERSION=22
ARG PKG=packages/ingest-engine
FROM node:${NODE_VERSION}-bookworm-slim AS deps
ARG PKG
WORKDIR /app
COPY ${PKG}/package.json ./package.json
RUN npm install --omit=dev --no-audit --no-fund && npm install --no-save tsx@^4.19.2

FROM node:${NODE_VERSION}-bookworm-slim
ARG PKG
ENV NODE_ENV=production INGEST_PORT=3002 INGEST_CACHE_DIR=/app/.cache INGEST_TESSDATA_DIR=/app/.tessdata INGEST_TYPES_DIR=/app/types INGEST_FEEDBACK_DIR=/app/feedback
WORKDIR /app
# Runtime hardening: current Debian security fixes, and no package manager in the image — the
# runtime runs `node` only, and the npm bundled with the base image carries its own advisories.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/* \
 && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx /opt/yarn* /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY --from=deps /app/node_modules ./node_modules
COPY ${PKG}/package.json ${PKG}/tsconfig.json ./
COPY ${PKG}/src ./src
COPY ${PKG}/types ./types
COPY ${PKG}/docs ./docs
RUN mkdir -p /app/.cache /app/.tessdata /app/feedback && chown -R node:node /app
USER node
EXPOSE 3002
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3002/v1/health',{headers:{'x-api-key':process.env.INGEST_API_KEY||''}}).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "node_modules/.bin/tsx", "src/main.ts"]
