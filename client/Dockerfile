FROM alpine:3.20

ARG V2RAY_PLUGIN_VERSION=v1.3.2
ARG TARGETARCH

RUN apk add --no-cache \
        ca-certificates \
        curl \
        privoxy \
        shadowsocks-libev \
        tzdata \
    && case "${TARGETARCH}" in \
         amd64|"") PLUGIN_ARCH=amd64 ;; \
         arm64)    PLUGIN_ARCH=arm64 ;; \
         arm)      PLUGIN_ARCH=arm   ;; \
         *)        echo "unsupported arch: ${TARGETARCH}" && exit 1 ;; \
       esac \
    && curl -fsSL \
         "https://github.com/shadowsocks/v2ray-plugin/releases/download/${V2RAY_PLUGIN_VERSION}/v2ray-plugin-linux-${PLUGIN_ARCH}-${V2RAY_PLUGIN_VERSION}.tar.gz" \
         -o /tmp/v2ray-plugin.tar.gz \
    && tar -xzf /tmp/v2ray-plugin.tar.gz -C /tmp \
    && mv "/tmp/v2ray-plugin_linux_${PLUGIN_ARCH}" /usr/local/bin/v2ray-plugin \
    && chmod +x /usr/local/bin/v2ray-plugin \
    && rm -rf /tmp/* \
    && mkdir -p /etc/shadowsocks /etc/privoxy /data

COPY entrypoint.sh /entrypoint.sh
COPY privoxy.conf /etc/privoxy/config
RUN chmod +x /entrypoint.sh && sed -i 's/\r$//' /entrypoint.sh

ENV REMOTE_SERVER= \
    REMOTE_PORT=80 \
    SS_PASSWORD= \
    SS_METHOD=chacha20-ietf-poly1305 \
    SS_TIMEOUT=300 \
    V2RAY_PATH=/nas-sync \
    V2RAY_HOST= \
    LAN_CIDRS=10.0.0.0/16 \
    LOCAL_SOCKS_PORT=1080 \
    LOCAL_HTTP_PORT=8118 \
    TZ=Asia/Shanghai

EXPOSE 1080/tcp 8118/tcp
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
