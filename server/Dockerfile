FROM alpine:3.20

ARG V2RAY_PLUGIN_VERSION=v1.3.2
ARG TARGETARCH

RUN apk add --no-cache \
        ca-certificates \
        curl \
        iputils \
        py3-flask \
        py3-pip \
        python3 \
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
    && mkdir -p /etc/shadowsocks /data /opt/admin

COPY admin/ /opt/admin/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && find /opt/admin -type f -name '*.py' -exec sed -i 's/\r$//' {} \; \
    && sed -i 's/\r$//' /entrypoint.sh

ENV SERVER_BIND=0.0.0.0 \
    SERVER_PORT=80 \
    SS_PASSWORD= \
    SS_METHOD=chacha20-ietf-poly1305 \
    SS_TIMEOUT=300 \
    V2RAY_PATH=/nas-sync \
    LAN_CIDRS=10.0.0.0/16 \
    PUBLIC_HOST= \
    ADMIN_BIND=0.0.0.0 \
    ADMIN_PORT=8080 \
    ADMIN_PASSWORD=admin \
    TZ=Asia/Shanghai

EXPOSE 80/tcp 8080/tcp
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
