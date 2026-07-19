# SSfuckQOS

Shadowsocks + v2ray-plugin（HTTP/WebSocket）回家通道，专门对付运营商对「未知协议」的 QoS 限速。

- **服务端**：Docker 镜像 + Web 管理界面
- **客户端**：Docker 本地 SOCKS5 / HTTP 代理
- **互联互通**：默认把家庭网段 `10.0.0.0/16`（覆盖 `10.0.0.0`–`10.0.254.x`）强制走隧道
- **镜像**：GitHub Actions 自动构建并推送到 GHCR

| 镜像 | 地址 |
|------|------|
| 服务端 | `ghcr.io/tyrantcwj/ssfuckqos-server:latest` |
| 客户端 | `ghcr.io/tyrantcwj/ssfuckqos-client:latest` |

> 仅供连接自有内网使用。请遵守当地法律法规。

---

## 架构

```
外网设备
  → SOCKS5 :1080 / HTTP :8118
  → ss-client (v2ray-plugin / WS over HTTP)
  → 运营商网络（看起来像普通网页）
  → ss-server :80 + Admin UI :8080
  → 家庭局域网 10.0.0.0/16（NAS / 电影库 …）
```

---

## 爱快 Docker 一键编排（复制即用）

爱快：`扩展功能` → `Docker` → `编排` → 粘贴下面 YAML → 改密码/域名 → 部署。

> 镜像若 pull 失败：先把 GHCR 包设为 Public，或在爱快里对 `ghcr.io` 登录 GitHub Token。

### 服务端（家里爱快）

管理页：`http://爱快IP:8080`  
通道端口：`80`（WebSocket/HTTP 伪装）  
家庭网段：`10.0.0.0/16`

```yaml
services:
  ssfuckqos-server:
    image: ghcr.io/tyrantcwj/ssfuckqos-server:latest
    container_name: ssfuckqos-server
    restart: unless-stopped
    network_mode: host
    environment:
      TZ: Asia/Shanghai
      SERVER_BIND: "0.0.0.0"
      SERVER_PORT: "80"
      SS_PASSWORD: "改成你的强密码"
      SS_METHOD: "chacha20-ietf-poly1305"
      SS_TIMEOUT: "300"
      V2RAY_PATH: "/nas-sync"
      LAN_CIDRS: "10.0.0.0/16"
      PUBLIC_HOST: "你的DDNS或公网IP"
      ADMIN_PORT: "8080"
      ADMIN_PASSWORD: "改成管理页密码"
    volumes:
      - ssfuckqos-server-data:/data

volumes:
  ssfuckqos-server-data:
```

说明：

1. `network_mode: host` 才能顺畅访问家里 `10.0.x.x`（互联互通关键）
2. 爱快若占用了 `80`，把 `SERVER_PORT` 改成如 `8088`，并做端口映射/转发
3. 路由器需把公网 `SERVER_PORT` 转到这台爱快

若爱快不支持 host 网络，用桥接版：

```yaml
services:
  ssfuckqos-server:
    image: ghcr.io/tyrantcwj/ssfuckqos-server:latest
    container_name: ssfuckqos-server
    restart: unless-stopped
    environment:
      TZ: Asia/Shanghai
      SERVER_BIND: "0.0.0.0"
      SERVER_PORT: "80"
      SS_PASSWORD: "改成你的强密码"
      SS_METHOD: "chacha20-ietf-poly1305"
      SS_TIMEOUT: "300"
      V2RAY_PATH: "/nas-sync"
      LAN_CIDRS: "10.0.0.0/16"
      PUBLIC_HOST: "你的DDNS或公网IP"
      ADMIN_PORT: "8080"
      ADMIN_PASSWORD: "改成管理页密码"
    ports:
      - "80:80/tcp"
      - "8080:8080/tcp"
    volumes:
      - ssfuckqos-server-data:/data

volumes:
  ssfuckqos-server-data:
```

### 客户端（外面爱快 / 另一台 Docker 机）

本机代理：`SOCKS5 1080` / `HTTP 8118`  
`SS_PASSWORD`、`V2RAY_PATH`、`REMOTE_PORT` 必须与服务端一致。

```yaml
services:
  ssfuckqos-client:
    image: ghcr.io/tyrantcwj/ssfuckqos-client:latest
    container_name: ssfuckqos-client
    restart: unless-stopped
    environment:
      TZ: Asia/Shanghai
      REMOTE_SERVER: "你的DDNS或公网IP"
      REMOTE_PORT: "80"
      SS_PASSWORD: "与服务端相同的密码"
      SS_METHOD: "chacha20-ietf-poly1305"
      SS_TIMEOUT: "300"
      V2RAY_PATH: "/nas-sync"
      V2RAY_HOST: "你的DDNS或公网IP"
      LAN_CIDRS: "10.0.0.0/16"
      LOCAL_SOCKS_PORT: "1080"
      LOCAL_HTTP_PORT: "8118"
    ports:
      - "1080:1080/tcp"
      - "8118:8118/tcp"
    volumes:
      - ssfuckqos-client-data:/data

volumes:
  ssfuckqos-client-data:
```

部署后自测：

```bash
curl -x socks5h://127.0.0.1:1080 http://10.0.0.1
curl -x http://127.0.0.1:8118 http://10.0.0.1
```

---

## 命令行部署（可选）

首次若 GHCR 包是私有的，需要登录：

```bash
echo YOUR_GITHUB_TOKEN | docker login ghcr.io -u tyrantcwj --password-stdin
```

```bash
git clone https://github.com/tyrantcwj/SSfuckQOS.git
cd SSfuckQOS
cp .env.example .env
# 编辑 .env 后：
docker compose -f docker-compose.server.yml up -d   # 家里
docker compose -f docker-compose.client.yml up -d   # 外面
```

---

## 互联互通（重要）

你家局域网是 `10.0.0.0`–`10.0.254.0` 一段，配置里用：

```env
LAN_CIDRS=10.0.0.0/16
```

容易踩坑：很多客户端默认 **绕过局域网 / bypass 10.0.0.0/8**，在外面时会直连失败。

正确做法：

1. 关掉「绕过局域网」
2. 或用管理界面导出的 **Clash 配置**（已把 `10.0.0.0/16` 强制进 `HOME-LAN` 代理组）
3. Docker 客户端本身不绕过私网；只要软件走 `1080/8118`，访问 `10.0.x.x` 就会进隧道

服务端管理页还有「探测局域网互通」按钮，可检查容器能否 ping 到网段内网关。

---

## 管理界面能做什么

- 查看 Shadowsocks 运行状态
- 修改端口 / 密码 / 加密 / WebSocket 路径 / 家庭网段
- 保存后自动重启服务
- 导出 Clash YAML、SS JSON、Docker `.env`、`ss://` URI
- 探测 `LAN_CIDRS` 连通性

---

## 环境变量

见 [`.env.example`](.env.example)。核心项：

| 变量 | 说明 |
|------|------|
| `SS_PASSWORD` | 两端一致 |
| `V2RAY_PATH` | 如 `/nas-sync` |
| `LAN_CIDRS` | 默认 `10.0.0.0/16` |
| `PUBLIC_HOST` | DDNS/公网 IP，用于导出客户端 |
| `ADMIN_PASSWORD` | 管理界面密码 |
| `REMOTE_SERVER` / `V2RAY_HOST` | 客户端连回家的地址 |

---

## GitHub Actions 镜像

推送到 `main` / `master` 或打 `v*` tag 后自动构建：

- `linux/amd64`
- `linux/arm64`（群晖 / 多数 ARM NAS）

Workflow：[`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml)

首次推送后，到 GitHub → Packages 把两个包设为 **Public**（否则别人 pull 需要 token）。

---

## 本地构建

```bash
docker compose -f docker-compose.server.yml build
docker compose -f docker-compose.client.yml build
```

---

## 故障排查

| 现象 | 处理 |
|------|------|
| 能连代理但打不开 `10.0.x.x` | 关闭客户端「绕过局域网」；确认服务端 `network_mode: host` |
| 管理页打不开 | 看 `ADMIN_PORT`；host 网络下直接访问宿主机 IP:8080 |
| GHCR pull 拒绝 | `docker login ghcr.io` 或把 Package 设为 Public |
| 容器秒退 | `docker logs ssfuckqos-server` 是否缺 `SS_PASSWORD` |
