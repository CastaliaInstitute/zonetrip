#!/usr/bin/env sh
set -eu

PREFIX="${PREFIX:-/opt/zonetrip}"
SERVICE_USER="${SERVICE_USER:-zonetrip}"
OLLAMA_MODEL="${ZONETRIP_OLLAMA_MODEL:-gemma3:12b}"
STATE_DIR="${ZONETRIP_STATE_DIR:-/var/lib/zonetrip}"
DEV_TEXT_INPUT="${ZONETRIP_ENABLE_DEV_TEXT:-0}"
DAILY_BATCH_MODE="${ZONETRIP_DAILY_BATCH_MODE:-0}"

if [ "$(id -u)" -ne 0 ]; then
  echo "install-local-ai.sh must be run as root" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required" >&2
  exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y curl ffmpeg python3-venv
fi

if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$PREFIX" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$STATE_DIR"
if [ ! -f "$STATE_DIR/model.md" ]; then
  cp "$PREFIX/model.md" "$STATE_DIR/model.md"
fi

python3 -m venv "$PREFIX/.venv"
"$PREFIX/.venv/bin/python" -m pip install --upgrade pip
"$PREFIX/.venv/bin/python" -m pip install -r "$PREFIX/services/processor/requirements.txt"

if [ "$DEV_TEXT_INPUT" = "1" ]; then
  TEXT_MODEL_ENDPOINT="http://127.0.0.1:8090/process-stt"
  DEV_TEXT_INPUT_JS="true"
else
  TEXT_MODEL_ENDPOINT=""
  DEV_TEXT_INPUT_JS="false"
fi

cat > "$PREFIX/booth-config.js" <<EOF
window.ZoneTripBoothConfig = {
  worldModelEndpoint: "http://127.0.0.1:8090/process-audio",
  textModelEndpoint: "$TEXT_MODEL_ENDPOINT",
  reviewEndpoint: "http://127.0.0.1:8090/review-day",
  devTextInput: $DEV_TEXT_INPUT_JS,
  idlePowerdownMs: 60000,
  vadRmsThreshold: 0.018,
};
EOF

if command -v systemctl >/dev/null 2>&1; then
  systemctl enable --now ollama.service || true
fi

ollama pull "$OLLAMA_MODEL"

chown -R "$SERVICE_USER:$SERVICE_USER" "$PREFIX" "$STATE_DIR"

if command -v systemctl >/dev/null 2>&1; then
  cp "$PREFIX/deploy/systemd/zonetrip-processor.service" /etc/systemd/system/zonetrip-processor.service
  if [ -d /etc/default ]; then
    {
      printf 'ZONETRIP_ENABLE_DEV_STT=%s\n' "$DEV_TEXT_INPUT"
      printf 'ZONETRIP_DAILY_BATCH_MODE=%s\n' "$DAILY_BATCH_MODE"
    } > /etc/default/zonetrip-processor
  fi
  systemctl daemon-reload
  systemctl enable zonetrip-processor.service
  systemctl restart zonetrip-processor.service
  echo "Zone Trip processor installed at http://127.0.0.1:8090/"
else
  echo "Run: cd $PREFIX/services/processor && ZONETRIP_ENABLE_DEV_STT=$DEV_TEXT_INPUT ZONETRIP_DAILY_BATCH_MODE=$DAILY_BATCH_MODE $PREFIX/.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8090"
fi
