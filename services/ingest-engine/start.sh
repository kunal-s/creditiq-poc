#!/usr/bin/env bash
# Ingestion engine — one command from a fresh checkout to a running, tested container.
#
# SETUP AFTER CLONING (what this script does for you; the manual equivalent is in README.md → "Setting up after cloning")
#   The repository ships .env.example only; the real .env is git-ignored and is created here from it.
#     .env  ← .env.example   AI_API_KEY (yours — the ONE value you supply) · INGEST_API_KEY (generated if empty) ·
#                            everything else preset for Docker: INGEST_PORT=3002, INGEST_TYPES_DIR=./types,
#                            INGEST_FEEDBACK_DIR=./feedback, INGEST_AUTO_THRESHOLD=0.7, AI_MODEL=gpt-4.1-mini
#   Not OpenAI? Set AI_BASE_URL and AI_MODEL in .env too. Callers must send INGEST_API_KEY as x-api-key.
#
#   ./start.sh            stop a previous engine (container or local) → create .env → ask for AI_API_KEY →
#                         install dependencies → run the tests → build the image → start the container →
#                         wait for it → print how to test it
#   AI_API_KEY=… ./start.sh --yes   the same with no questions (CI / scripts)
#   ./start.sh --setup    only create .env and install (nothing built or started) — then run things yourself
#   ./start.sh --no-test  skip the test suite
#   ./start.sh --local    run with node instead of docker (npm run dev), same checks
#   ./start.sh --stop     stop and remove the container
#   ./start.sh --help     this text
#
# REQUIREMENTS  Node.js 20+ · Docker (Docker Desktop, OrbStack or Colima) unless --local · network for npm and the model
# Works from inside the OneGRC monorepo (packages/ingest-engine) or from this directory alone.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
IMAGE="${IMAGE:-ingest-engine:latest}"
NAME="${CONTAINER:-ingest-engine}"
YES=0; RUN_TESTS=1; LOCAL=0; SETUP_ONLY=0
for a in "$@"; do case "$a" in --yes|-y) YES=1;; --no-test) RUN_TESTS=0;; --local) LOCAL=1;; --setup) SETUP_ONLY=1;; --stop) docker rm -f "$NAME" >/dev/null 2>&1 && echo "stopped $NAME" || echo "$NAME was not running"; exit 0;; -h|--help) sed -n 2,21p "$0" | sed 's/^# \{0,1\}//'; exit 0;; *) echo "unknown option $a (try --help)"; exit 2;; esac; done

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✘\033[0m %s\n' "$*"; exit 1; }
ask()  { # ask "question" → 0 for yes; --yes answers yes
  if [ "$YES" = 1 ]; then return 0; fi
  read -r -p "$1 [y/N] " r; [[ "$r" =~ ^[Yy]$ ]]
}
envval() { { grep -E "^$1=" .env 2>/dev/null || true; } | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"; }  # never fails (set -e + pipefail)

printf '\033[1mIngestion engine — setup and start\033[0m\n'
cat <<'EOT'
  Steps: 1 .env + your AI_API_KEY · 2 dependencies and tests · 3 image and container (or node with --local) · 4 how to test
  The .env file is git-ignored; it is created from .env.example with everything preset for Docker.
EOT
# ── 1 · Environment variables ─────────────────────────────────────────────────
# A fresh clone needs exactly one thing from the developer: the model provider key.
# .env is created from .env.example (preset for Docker); INGEST_API_KEY is generated.
bold "1 · Environment (.env in $HERE)"
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env from .env.example (preset for Docker)"
fi
if [ -z "$(envval AI_API_KEY)" ]; then
  if [ -n "${AI_API_KEY:-}" ]; then
    KEYIN="$AI_API_KEY"                         # AI_API_KEY=sk-… ./start.sh --yes  (CI / scripts)
  elif [ "$YES" = 1 ]; then
    die "AI_API_KEY is not set. Put it in $HERE/.env, or run: AI_API_KEY=<key> ./start.sh --yes"
  else
    echo "  AI_API_KEY is the only value you need to supply (an OpenAI key, or any OpenAI-compatible endpoint's key)."
    read -r -s -p "  Paste your AI_API_KEY (input hidden): " KEYIN; echo
    [ -n "$KEYIN" ] || die "no key entered — put AI_API_KEY in $HERE/.env and run ./start.sh again"
  fi
  sed -i.bak "s#^AI_API_KEY=.*#AI_API_KEY=${KEYIN}#" .env && rm -f .env.bak
  ok "AI_API_KEY written to .env (never committed — .env is git-ignored)"
fi
if [ -z "$(envval INGEST_API_KEY)" ]; then
  GEN="$(openssl rand -hex 24 2>/dev/null || head -c 48 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  sed -i.bak "s#^INGEST_API_KEY=.*#INGEST_API_KEY=${GEN}#" .env && rm -f .env.bak
  ok "INGEST_API_KEY generated and written to .env (callers send it as x-api-key)"
fi
if [ "$YES" != 1 ] && ! ask "Anything else to change in .env (model, port, tuning)? Press N to continue with the Docker presets, or Y to stop and edit."; then :; else [ "$YES" = 1 ] || die "Edit $HERE/.env, then run ./start.sh again."; fi
PORT="$(envval INGEST_PORT)"; PORT="${PORT:-3002}"
KEY="$(envval INGEST_API_KEY)"
ok "AI_MODEL=$(envval AI_MODEL) · AI_BASE_URL=$(envval AI_BASE_URL) · port $PORT · API key set"

# ── 2 · Dependencies ──────────────────────────────────────────────────────────
bold "2 · Dependencies"
command -v node >/dev/null || die "node is not installed (need Node 20+): https://nodejs.org"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"; [ "$NODE_MAJOR" -ge 20 ] || die "Node $NODE_MAJOR found; need 20 or newer."
ok "node $(node -v) · npm $(npm -v)"
if [ -f ../../package.json ] && grep -q '"packages/\*"' ../../package.json 2>/dev/null; then
  CONTEXT="$(cd ../.. && pwd)"; PKG="packages/ingest-engine"
  echo "  Monorepo detected — installing from $CONTEXT (workspaces)"
  (cd "$CONTEXT" && npm install --no-audit --no-fund --loglevel=error >/dev/null)
else
  CONTEXT="$HERE"; PKG="."
  echo "  Standalone package — installing here"
  npm install --no-audit --no-fund --loglevel=error >/dev/null
fi
ok "npm dependencies installed"
if [ "$RUN_TESTS" = 1 ]; then
  echo "  Running the contract tests (no model needed)…"
  if npm test >/tmp/ingest-engine-test.log 2>&1; then ok "tests: $(grep -E '^# pass' /tmp/ingest-engine-test.log | tr -d '#')"; else cat /tmp/ingest-engine-test.log | tail -30; die "tests failed"; fi
fi

if [ "$SETUP_ONLY" = 1 ]; then
  bold "Setup complete — nothing built or started (--setup)"
  cat <<EOT
  .env written in $HERE (git-ignored; the keys stay on this machine).
  Run it yourself:
    npm run dev                      with node, watch mode, on :$PORT
    npm start                        with node
    docker build --build-arg PKG=$PKG -f Dockerfile -t $IMAGE $CONTEXT && docker run -d --name $NAME -p $PORT:3002 --env-file .env -e INGEST_PORT=3002 -v ingest_cache:/app/.cache -v ingest_tessdata:/app/.tessdata -v ingest_feedback:/app/feedback $IMAGE
  Or simply:  ./start.sh
EOT
  exit 0
fi

# ── 3 · Run: local node, or docker ────────────────────────────────────────────
if [ "$LOCAL" = 1 ]; then
  bold "3 · Starting with node (npm run dev) on :$PORT — Ctrl-C stops it"
  URL="http://localhost:$PORT"
  print_tests() { :; }  # printed below before exec
else
  bold "3 · Docker"
  command -v docker >/dev/null || die "docker is not installed. Install Docker Desktop, OrbStack or Colima (brew install colima docker)."
  if ! docker info >/dev/null 2>&1; then
    warn "the docker daemon is not running"
    if command -v colima >/dev/null && ask "Start it with colima now?"; then colima start >/dev/null 2>&1 || die "colima could not start"; else die "start Docker (Docker Desktop / OrbStack / colima start) and run ./start.sh again"; fi
  fi
  ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) is running"
  echo "  Building $IMAGE (first build pulls node:22 and compiles natives — a few minutes; later builds are seconds)…"
  docker build -q --build-arg "PKG=$PKG" -f "$HERE/Dockerfile" -t "$IMAGE" "$CONTEXT" >/dev/null || die "image build failed — run without -q to see why: docker build --build-arg PKG=$PKG -f Dockerfile -t $IMAGE $CONTEXT"
  ok "image $IMAGE built ($(docker images "$IMAGE" --format '{{.Size}}'))"
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  # A busy host port makes the published port silently unreachable (the runtime cannot bind it):
  # stop an engine of ours that is on it (npm run dev), refuse anything else.
  for pid in $(lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n -t 2>/dev/null || true); do
    if ps -o comm= -p "$pid" 2>/dev/null | grep -qE '^\(?(node|npm)'; then kill "$pid" 2>/dev/null || true; ok "stopped the local engine (pid $pid) that held :$PORT"
    else die "port $PORT is held by $(ps -o comm= -p "$pid") (pid $pid) — stop it or set INGEST_PORT in .env to another port"; fi
  done
  for _ in 1 2 3 4 5 6 7 8 9 10; do lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n >/dev/null 2>&1 || break; sleep 1; done
  docker run -d --name "$NAME" --restart unless-stopped -p "$PORT:3002" --env-file .env -e INGEST_PORT=3002 \
    -v ingest_cache:/app/.cache -v ingest_tessdata:/app/.tessdata -v ingest_feedback:/app/feedback "$IMAGE" >/dev/null
  URL="http://localhost:$PORT"
  for i in $(seq 1 40); do
    if curl -s -o /dev/null -w '%{http_code}' -H "x-api-key: $KEY" "$URL/v1/health" 2>/dev/null | grep -q 200; then ok "container $NAME is up on $URL (after ${i}s)"; break; fi
    if [ "$i" = 40 ]; then docker logs "$NAME" 2>&1 | tail -20; die "the engine did not answer on $URL/v1/health within 40 s"; fi
    sleep 1
  done
fi

# ── 4 · How to test ───────────────────────────────────────────────────────────
H="-H \"x-api-key: $KEY\""; [ -n "$KEY" ] || H=""
bold "4 · Test it"
cat <<EOT

  Health (should say ok:true and list the model):
    curl -s $H $URL/v1/health

  Parse only — text and OCR, no model call:
    curl -s $H -F file=@some.pdf $URL/v1/parse

  Extract from a file with a profile file (examples/profiles has invoice and bank-statement):
    curl -s $H -F file=@invoice.pdf -F profile=@examples/profiles/invoice.json $URL/v1/extract

  Extract from a URL with an inline profile and your own rules:
    curl -s $H -H "content-type: application/json" $URL/v1/extract -d '{
      "url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=10435",
      "profile": { "instructions": "Summarise what the notice requires of a bank.",
                   "fields": [ { "name": "title", "type": "string", "required": true },
                               { "name": "actionsRequired", "type": "string[]" },
                               { "name": "deadline", "type": "date" } ] },
      "rules": "Ignore page navigation and footers."
    }'

  An e-mail (.eml) — its attachments become separate documents:
    curl -s $H -F file=@message.eml -F emailScope=attachments -F profile=@examples/profiles/invoice.json $URL/v1/extract

  Stream progress instead of waiting (Server-Sent Events):
    curl -sN $H -F file=@long.pdf -F profile=@examples/profiles/invoice.json $URL/v1/extract/stream

  Profiles the engine knows (built-in generic + files under its profiles volume):
    curl -s $H $URL/v1/profiles

  Logs / stop:  docker logs -f $NAME   ·   ./start.sh --stop
  Docs:         docs/GUIDE.md (how to use it, unknown types, adding types) · README.md (the reference)
EOT
if [ "$LOCAL" = 1 ]; then exec npm run dev; fi
