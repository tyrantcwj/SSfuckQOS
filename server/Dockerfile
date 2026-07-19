FROM alpine:3.20

ARG V2RAY_PLUGIN_VERSION=v1.3.2
ARG SS_RUST_VERSION=v1.24.0
ARG TARGETARCH

RUN apk add --no-cache \
        ca-certificates \
        curl \
        iputils \
        py3-flask \
        python3 \
        tzdata \
        xz \
    && case "${TARGETARCH}" in \
         amd64|"") PLUGIN_ARCH=amd64; SS_ARCH=x86_64-unknown-linux-musl ;; \
         arm64)    PLUGIN_ARCH=arm64; SS_ARCH=aarch64-unknown-linux-musl ;; \
         *)        echo "unsupported arch: ${TARGETARCH}" && exit 1 ;; \
       esac \
    && curl -fsSL \
         "https://github.com/shadowsocks/shadowsocks-rust/releases/download/${SS_RUST_VERSION}/shadowsocks-${SS_RUST_VERSION}.${SS_ARCH}.tar.xz" \
         -o /tmp/ss-rust.tar.xz \
    && tar -xJf /tmp/ss-rust.tar.xz -C /usr/local/bin ssserver \
    && curl -fsSL \
         "https://github.com/shadowsocks/v2ray-plugin/releases/download/${V2RAY_PLUGIN_VERSION}/v2ray-plugin-linux-${PLUGIN_ARCH}-${V2RAY_PLUGIN_VERSION}.tar.gz" \
         -o /tmp/v2ray-plugin.tar.gz \
    && tar -xzf /tmp/v2ray-plugin.tar.gz -C /tmp \
    && mv "/tmp/v2ray-plugin_linux_${PLUGIN_ARCH}" /usr/local/bin/v2ray-plugin \
    && chmod +x /usr/local/bin/ssserver /usr/local/bin/v2ray-plugin \
    && rm -rf /tmp/* \
    && mkdir -p /etc/shadowsocks /data /opt/admin

COPY admin/ /opt/admin/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
    && find /opt/admin -type f \( -name '*.py' -o -name '*.sh' \) -exec sed -i 's/\r$//' {} \; \
    && sed -i 's/\r$//' /entrypoint.sh

ENV SERVER_BIND=0.0.0.0 \
    SERVER_PORT=80 \
    SS_METHOD=chacha20-ietf-poly1305 \
    SS_TIMEOUT=300 \
    V2RAY_PATH=/nas-sync \
    LAN_CIDRS=10.0.0.0/16 \
    PUBLIC_HOST= \
    ADMIN_BIND=0.0.0.0 \
    ADMIN_PORT=8080 \
    TZ=Asia/Shanghai

EXPOSE 80/tcp 8080/tcp
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
