#!/bin/sh
set -eu

mkdir -p /data /etc/shadowsocks /var/run /var/log

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
export SS_LOG_PATH=/var/log/ssserver.log

# 每次启动都以编排 environment 为准（爱快无 volume 时也能对齐）
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

echo "==> SSfuckQOS server"
echo "    listen   : ${SERVER_BIND}:${SERVER_PORT}  (容器内；爱快映射 5280:80 时这里仍是 80)"
echo "    path     : ${V2RAY_PATH}"
echo "    lan      : ${LAN_CIDRS}"
echo "    admin UI : http://0.0.0.0:${ADMIN_PORT}  (爱快映射 5281:8080)"
echo "    note     : ssserver 由管理面板进程拉起"

# 只启动管理面板；ssserver 由 admin 负责拉起/守护
exec python3 /opt/admin/app.py
