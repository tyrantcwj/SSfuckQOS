#!/bin/sh
set -eu

mkdir -p /data /etc/shadowsocks /var/run

: "${SERVER_BIND:=0.0.0.0}"
: "${SERVER_PORT:=80}"
: "${SS_METHOD:=chacha20-ietf-poly1305}"
: "${SS_TIMEOUT:=300}"
: "${V2RAY_PATH:=/nas-sync}"
: "${LAN_CIDRS:=10.0.0.0/16}"
: "${ADMIN_PORT:=8080}"
: "${ADMIN_BIND:=0.0.0.0}"
: "${ADMIN_PASSWORD:=admin}"
: "${PUBLIC_HOST:=}"

if [ -z "${SS_PASSWORD:-}" ]; then
  echo "ERROR: SS_PASSWORD is required" >&2
  exit 1
fi

case "${V2RAY_PATH}" in
  /*) ;;
  *) V2RAY_PATH="/${V2RAY_PATH}" ;;
esac

export SERVER_BIND SERVER_PORT SS_PASSWORD SS_METHOD SS_TIMEOUT
export V2RAY_PATH LAN_CIDRS ADMIN_PORT ADMIN_BIND ADMIN_PASSWORD PUBLIC_HOST
export SS_CONFIG_PATH=/etc/shadowsocks/config.json
export RUNTIME_ENV_PATH=/data/runtime.env
export SS_PID_PATH=/var/run/ss-server.pid

# Seed runtime env for admin UI (admin may overwrite later)
if [ ! -f /data/runtime.env ]; then
  cat > /data/runtime.env <<EOF
SERVER_BIND=${SERVER_BIND}
SERVER_PORT=${SERVER_PORT}
SS_PASSWORD=${SS_PASSWORD}
SS_METHOD=${SS_METHOD}
SS_TIMEOUT=${SS_TIMEOUT}
V2RAY_PATH=${V2RAY_PATH}
PUBLIC_HOST=${PUBLIC_HOST}
LAN_CIDRS=${LAN_CIDRS}
ADMIN_PORT=${ADMIN_PORT}
EOF
fi

PLUGIN_OPTS="server;path=${V2RAY_PATH}"
cat > /etc/shadowsocks/config.json <<EOF
{
  "server": "${SERVER_BIND}",
  "server_port": ${SERVER_PORT},
  "password": "${SS_PASSWORD}",
  "timeout": ${SS_TIMEOUT},
  "method": "${SS_METHOD}",
  "mode": "tcp_and_udp",
  "fast_open": false,
  "plugin": "v2ray-plugin",
  "plugin_opts": "${PLUGIN_OPTS}"
}
EOF

echo "==> SSfuckQOS server"
echo "    ss       : ${SERVER_BIND}:${SERVER_PORT}"
echo "    path     : ${V2RAY_PATH}"
echo "    lan      : ${LAN_CIDRS}"
echo "    admin UI : http://0.0.0.0:${ADMIN_PORT}"

ssserver -c /etc/shadowsocks/config.json -u &
echo $! > /var/run/ss-server.pid

python3 /opt/admin/app.py &
ADMIN_PID=$!

cleanup() {
  kill "$(cat /var/run/ss-server.pid 2>/dev/null || true)" "${ADMIN_PID}" 2>/dev/null || true
}
trap cleanup INT TERM

wait "${ADMIN_PID}"
