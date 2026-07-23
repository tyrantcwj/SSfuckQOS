#!/bin/sh
set -eu

if [ -z "${REMOTE_SERVER:-}" ]; then
  echo "ERROR: REMOTE_SERVER is required (public IP or DDNS)" >&2
  exit 1
fi
if [ -z "${SS_PASSWORD:-}" ]; then
  echo "ERROR: SS_PASSWORD is required" >&2
  exit 1
fi

: "${REMOTE_PORT:=80}"
: "${SS_METHOD:=chacha20-ietf-poly1305}"
: "${SS_TIMEOUT:=300}"
: "${V2RAY_PATH:=/nas-sync}"
if [ -z "${V2RAY_HOST:-}" ]; then
  V2RAY_HOST="${REMOTE_SERVER}"
fi
: "${LOCAL_SOCKS_PORT:=1080}"
: "${LOCAL_HTTP_PORT:=8118}"
: "${LAN_CIDRS:=10.0.0.0/16}"

case "${V2RAY_PATH}" in
  /*) ;;
  *) V2RAY_PATH="/${V2RAY_PATH}" ;;
esac

# websocket + mux=0 更稳；v2ray-plugin 不走 UDP
PLUGIN_OPTS="mode=websocket;path=${V2RAY_PATH};host=${V2RAY_HOST};mux=0"

mkdir -p /etc/shadowsocks /data /var/log

cat > /etc/shadowsocks/config.json <<EOF
{
  "server": "${REMOTE_SERVER}",
  "server_port": ${REMOTE_PORT},
  "password": "${SS_PASSWORD}",
  "timeout": ${SS_TIMEOUT},
  "method": "${SS_METHOD}",
  "mode": "tcp_only",
  "plugin": "v2ray-plugin",
  "plugin_opts": "${PLUGIN_OPTS}",
  "plugin_mode": "tcp_only"
}
EOF

sed -i "s/^listen-address.*/listen-address  0.0.0.0:${LOCAL_HTTP_PORT}/" /etc/privoxy/config
sed -i "s|forward-socks5t / 127.0.0.1:.*|forward-socks5t / 127.0.0.1:${LOCAL_SOCKS_PORT} .|" /etc/privoxy/config

echo "==> SSfuckQOS client"
echo "    remote : ${REMOTE_SERVER}:${REMOTE_PORT}"
echo "    path   : ${V2RAY_PATH}"
echo "    host   : ${V2RAY_HOST}"
echo "    lan    : ${LAN_CIDRS}"
echo "    socks5 : 0.0.0.0:${LOCAL_SOCKS_PORT}"
echo "    http   : 0.0.0.0:${LOCAL_HTTP_PORT}"
echo "    plugin : ${PLUGIN_OPTS}"

echo "==> probe TCP ${REMOTE_SERVER}:${REMOTE_PORT}"
if command -v nc >/dev/null 2>&1; then
  if nc -z -w 5 "${REMOTE_SERVER}" "${REMOTE_PORT}"; then
    echo "    TCP OK"
  else
    echo "    TCP FAIL — 公网端口不通。检查：爱快端口映射、SERVER_PORT 与 REMOTE_PORT 是否一致、上级路由转发"
  fi
else
  # busybox wget/curl fallback: any HTTP response (even 400) means port is open
  code=$(curl -sS -o /dev/null -m 5 -w "%{http_code}" "http://${REMOTE_SERVER}:${REMOTE_PORT}/" || true)
  if [ -n "${code}" ] && [ "${code}" != "000" ]; then
    echo "    HTTP probe got ${code} (port reachable)"
  else
    echo "    HTTP probe FAIL — 公网端口不通。检查端口映射 / REMOTE_PORT"
  fi
fi

# shadowsocks-rust requires --local-addr
sslocal \
  -c /etc/shadowsocks/config.json \
  --local-addr "0.0.0.0:${LOCAL_SOCKS_PORT}" \
  -v \
  > /var/log/sslocal.log 2>&1 &
SS_PID=$!
echo $! > /tmp/sslocal.pid

# tail logs to docker stdout
tail -F /var/log/sslocal.log &
TAIL_PID=$!

privoxy --no-daemon /etc/privoxy/config &
PRIVOXY_PID=$!

sleep 1
if ! kill -0 "${SS_PID}" 2>/dev/null; then
  echo "ERROR: sslocal failed to start. Last log:" >&2
  cat /var/log/sslocal.log >&2 || true
  exit 1
fi

echo "==> sslocal running (pid=${SS_PID})"

cleanup() {
  kill "${SS_PID}" "${PRIVOXY_PID}" "${TAIL_PID}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

while kill -0 "${SS_PID}" 2>/dev/null && kill -0 "${PRIVOXY_PID}" 2>/dev/null; do
  sleep 2
done

echo "ERROR: sslocal or privoxy exited unexpectedly" >&2
tail -n 50 /var/log/sslocal.log >&2 || true
exit 1
