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
: "${V2RAY_HOST:=${REMOTE_SERVER}}"
: "${LOCAL_SOCKS_PORT:=1080}"
: "${LOCAL_HTTP_PORT:=8118}"
: "${LAN_CIDRS:=10.0.0.0/16}"

case "${V2RAY_PATH}" in
  /*) ;;
  *) V2RAY_PATH="/${V2RAY_PATH}" ;;
esac

PLUGIN_OPTS="path=${V2RAY_PATH};host=${V2RAY_HOST}"

mkdir -p /etc/shadowsocks /data

cat > /etc/shadowsocks/config.json <<EOF
{
  "server": "${REMOTE_SERVER}",
  "server_port": ${REMOTE_PORT},
  "local_address": "0.0.0.0",
  "local_port": ${LOCAL_SOCKS_PORT},
  "password": "${SS_PASSWORD}",
  "timeout": ${SS_TIMEOUT},
  "method": "${SS_METHOD}",
  "mode": "tcp_and_udp",
  "fast_open": false,
  "plugin": "v2ray-plugin",
  "plugin_opts": "${PLUGIN_OPTS}"
}
EOF

# Keep privoxy listen port in sync with env
sed -i "s/^listen-address.*/listen-address  0.0.0.0:${LOCAL_HTTP_PORT}/" /etc/privoxy/config
sed -i "s|forward-socks5t / 127.0.0.1:.*|forward-socks5t / 127.0.0.1:${LOCAL_SOCKS_PORT} .|" /etc/privoxy/config

# Write helper notes for LAN interconnectivity
cat > /data/LAN_ROUTING.txt <<EOF
SSfuckQOS client is up.

Local proxies:
  SOCKS5 = 127.0.0.1:${LOCAL_SOCKS_PORT}
  HTTP   = 127.0.0.1:${LOCAL_HTTP_PORT}

Home LAN CIDRs (must go THROUGH proxy, do NOT bypass):
  ${LAN_CIDRS}

Test from host:
  curl -x socks5h://127.0.0.1:${LOCAL_SOCKS_PORT} http://10.0.0.1
  curl -x http://127.0.0.1:${LOCAL_HTTP_PORT} http://10.0.0.1

IMPORTANT:
  Many GUI clients bypass 10.0.0.0/8 by default.
  Disable "Bypass LAN / 绕过局域网" or force-proxy ${LAN_CIDRS}.
EOF

# Optional Clash snippet for host-side clients
IFS=','
RULES=""
for cidr in ${LAN_CIDRS}; do
  cidr=$(echo "$cidr" | tr -d ' ')
  [ -n "$cidr" ] || continue
  RULES="${RULES}  - IP-CIDR,${cidr},HOME-LAN,no-resolve\n"
done
unset IFS

cat > /data/clash-home-lan.snippet.yaml <<EOF
# Paste into Clash Meta rules / proxy-groups
proxy-groups:
  - name: HOME-LAN
    type: select
    proxies: [SSfuckQOS]

rules:
$(printf "%b" "$RULES")
EOF

echo "==> SSfuckQOS client"
echo "    remote : ${REMOTE_SERVER}:${REMOTE_PORT}"
echo "    path   : ${V2RAY_PATH}"
echo "    host   : ${V2RAY_HOST}"
echo "    lan    : ${LAN_CIDRS}"
echo "    socks5 : 0.0.0.0:${LOCAL_SOCKS_PORT}"
echo "    http   : 0.0.0.0:${LOCAL_HTTP_PORT}"

sslocal -c /etc/shadowsocks/config.json -u &
SS_PID=$!

privoxy --no-daemon /etc/privoxy/config &
PRIVOXY_PID=$!

cleanup() {
  kill "${SS_PID}" "${PRIVOXY_PID}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

while kill -0 "${SS_PID}" 2>/dev/null && kill -0 "${PRIVOXY_PID}" 2>/dev/null; do
  sleep 2
done

echo "ERROR: sslocal or privoxy exited unexpectedly" >&2
exit 1
