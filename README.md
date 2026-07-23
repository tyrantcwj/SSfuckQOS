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

爱快限制（已按此写好）：

- **禁止** `network_mode: host` → 用桥接 + `ports`
- **禁止** 命名卷 / 多数路径挂载校验很严 → **爱快编排里不写 `volumes`**（配置全靠下面 `environment`，够用）

> 镜像若 pull 失败：先把 GHCR 包设为 Public，或在爱快里对 `ghcr.io` 登录 GitHub Token。

### 服务端（家里爱快）

管理页：`http://爱快IP:8080`  
通道端口：下面用 **5080**（避开爱快常用的 80）  
家庭网段：`10.0.0.0/16`

**端口必须三处一致：** `SERVER_PORT` = `ports` 左边/右边 = 客户端 `REMOTE_PORT`（若上级路由做了端口转换另说）

```yaml
services:
  ssfuckqos-server:
    image: ghcr.io/tyrantcwj/ssfuckqos-server:latest
    container_name: ssfuckqos-server
    restart: unless-stopped
    environment:
      TZ: Asia/Shanghai
      SERVER_BIND: "0.0.0.0"
      SERVER_PORT: "5080"
      SS_PASSWORD: "改成你的强密码"
      SS_METHOD: "chacha20-ietf-poly1305"
      SS_TIMEOUT: "300"
      V2RAY_PATH: "/nas-sync"
      LAN_CIDRS: "10.0.0.0/16"
      PUBLIC_HOST: "你的公网IP或DDNS"
      ADMIN_PORT: "8080"
      ADMIN_PASSWORD: "改成管理页密码"
    ports:
      - "5080:5080"
      - "8080:8080"
```

说明：

1. 上级路由 / 光猫要把公网 `5080` 转到这台爱快的 `5080`
2. 桥接下访问家里 `10.0.x.x` 一般仍可；管理页可点「局域网探测」
3. 不挂载卷时，以编排里的 `environment` 为准

### 客户端（外面爱快 / 另一台 Docker 机）

本机代理：`SOCKS5 1080` / `HTTP 8118`  
`SS_PASSWORD`、`V2RAY_PATH`、`REMOTE_PORT` 必须与服务端对外端口一致。

```yaml
services:
  ssfuckqos-client:
    image: ghcr.io/tyrantcwj/ssfuckqos-client:latest
    container_name: ssfuckqos-client
    restart: unless-stopped
    environment:
      TZ: Asia/Shanghai
      REMOTE_SERVER: "家里公网IP或DDNS"
      REMOTE_PORT: "5080"
      SS_PASSWORD: "与服务端相同的密码"
      SS_METHOD: "chacha20-ietf-poly1305"
      SS_TIMEOUT: "300"
      V2RAY_PATH: "/nas-sync"
      LAN_CIDRS: "10.0.0.0/16"
      LOCAL_SOCKS_PORT: "1080"
      LOCAL_HTTP_PORT: "8118"
    ports:
      - "1080:1080"
      - "8118:8118"
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
| `REMOTE_SERVER` | 客户端连回家的地址（DDNS/公网 IP）；`Host` 头默认跟它走 |

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
| 客户端连不上服务端 | 看客户端日志有无 `TCP FAIL`；核对 `REMOTE_PORT`=`SERVER_PORT`=`ports`；密码/path 两端一致；光猫/上级是否转发 |
| 能连代理但打不开 `10.0.x.x` | 关闭客户端「绕过局域网」；服务端确认能访问内网 |
| 管理页打不开 | 看 `8080` 端口映射；访问 `http://爱快IP:8080` |
| 爱快提示卷/host 不合法 | 用 README 爱快编排：只保留 `ports` + `environment`，不要写 `volumes` / host |
| GHCR pull 拒绝 | `docker login ghcr.io` 或把 Package 设为 Public |
| 容器秒退 | `docker logs` 看 sslocal/ssserver 报错；是否缺 `SS_PASSWORD` |
