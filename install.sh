#!/usr/bin/env sh
set -eu

PREFIX="${PREFIX:-/opt/zonetrip}"
SERVICE_USER="${SERVICE_USER:-zonetrip}"

if [ "$(id -u)" -ne 0 ]; then
  echo "install.sh must be run as root" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to run the bundled static server" >&2
  exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$PREFIX" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$PREFIX"
cp -R index.html booth.html styles.css script.js scene.js booth.js booth-config.js favicon.svg CNAME charter.md model.md docs bin manifesto architecture review assets vendor services deploy scripts .nojekyll "$PREFIX"/
chown -R "$SERVICE_USER:$SERVICE_USER" "$PREFIX"
chmod 0755 "$PREFIX/bin/zonetrip-serve"

if command -v systemctl >/dev/null 2>&1; then
  cp deploy/systemd/zonetrip.service /etc/systemd/system/zonetrip.service
  systemctl daemon-reload
  systemctl enable zonetrip.service
  systemctl restart zonetrip.service
  echo "Zone Trip installed and running at http://127.0.0.1:8080/"
else
  echo "Zone Trip installed at $PREFIX"
  echo "Run: $PREFIX/bin/zonetrip-serve --host 127.0.0.1 --port 8080 --root $PREFIX"
fi
