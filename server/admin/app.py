#!/usr/bin/env python3
"""SSfuckQOS server management UI."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import os
import re
import signal
import subprocess
import time
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

APP_START = time.time()
CONFIG_PATH = Path(os.environ.get("SS_CONFIG_PATH", "/etc/shadowsocks/config.json"))
RUNTIME_ENV_PATH = Path(os.environ.get("RUNTIME_ENV_PATH", "/data/runtime.env"))
PID_PATH = Path(os.environ.get("SS_PID_PATH", "/var/run/ss-server.pid"))
LOG_PATH = Path(os.environ.get("SS_LOG_PATH", "/var/log/ssserver.log"))
PLUGIN_BIN = "/usr/local/bin/v2ray-plugin"
DEFAULT_LAN_CIDRS = "10.0.0.0/16"

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET") or hashlib.sha256(
    (os.environ.get("ADMIN_PASSWORD") or "ssfuckqos").encode()
).hexdigest()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def load_runtime() -> dict[str, str]:
    # Docker/爱快 environment 优先，runtime.env 仅作补充
    data = {
        "SERVER_BIND": env("SERVER_BIND", "0.0.0.0"),
        "SERVER_PORT": env("SERVER_PORT", "80"),
        "SS_PASSWORD": env("SS_PASSWORD", ""),
        "SS_METHOD": env("SS_METHOD", "chacha20-ietf-poly1305"),
        "SS_TIMEOUT": env("SS_TIMEOUT", "300"),
        "V2RAY_PATH": env("V2RAY_PATH", "/nas-sync"),
        "PUBLIC_HOST": env("PUBLIC_HOST", ""),
        "LAN_CIDRS": env("LAN_CIDRS", DEFAULT_LAN_CIDRS),
        "ADMIN_PORT": env("ADMIN_PORT", "8080"),
    }
    if RUNTIME_ENV_PATH.exists():
        file_data: dict[str, str] = {}
        for line in RUNTIME_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            file_data[key.strip()] = value.strip()
        for key, value in file_data.items():
            # 仅当进程环境未显式提供时，才用文件值
            if key not in os.environ or os.environ.get(key, "") == "":
                data[key] = value
    if not data["V2RAY_PATH"].startswith("/"):
        data["V2RAY_PATH"] = "/" + data["V2RAY_PATH"]
    return data


def save_runtime(data: dict[str, str]) -> None:
    RUNTIME_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    order = [
        "SERVER_BIND",
        "SERVER_PORT",
        "SS_PASSWORD",
        "SS_METHOD",
        "SS_TIMEOUT",
        "V2RAY_PATH",
        "PUBLIC_HOST",
        "LAN_CIDRS",
        "ADMIN_PORT",
    ]
    lines = [f"{k}={data.get(k, '')}" for k in order]
    RUNTIME_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key in order:
        os.environ[key] = data.get(key, "")


def write_ss_config(data: dict[str, str]) -> None:
    # 最兼容的 v2ray-plugin 选项（websocket 默认，不强制 mux）
    plugin_opts = f"server;path={data['V2RAY_PATH']}"
    plugin = PLUGIN_BIN if Path(PLUGIN_BIN).exists() else "v2ray-plugin"
    config = {
        "server": data["SERVER_BIND"],
        "server_port": int(data["SERVER_PORT"]),
        "password": data["SS_PASSWORD"],
        "timeout": int(data["SS_TIMEOUT"]),
        "method": data["SS_METHOD"],
        "mode": "tcp_only",
        "fast_open": False,
        "plugin": plugin,
        "plugin_opts": plugin_opts,
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def read_log_tail(lines: int = 80) -> str:
    if not LOG_PATH.exists():
        return "(暂无日志)"
    try:
        content = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(读日志失败: {exc})"
    return "\n".join(content[-lines:]) or "(日志为空)"


def ss_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def stop_ss() -> None:
    old = ss_pid()
    if not old:
        # 兜底杀掉残留
        subprocess.run(["pkill", "-f", "ssserver"], check=False)
        subprocess.run(["pkill", "-f", "v2ray-plugin"], check=False)
        return
    try:
        os.kill(old, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(10):
        time.sleep(0.2)
        if ss_pid() is None:
            break
    else:
        try:
            os.kill(old, signal.SIGKILL)
        except OSError:
            pass
    subprocess.run(["pkill", "-f", "v2ray-plugin"], check=False)


def restart_ss() -> tuple[bool, str]:
    data = load_runtime()
    if not data["SS_PASSWORD"]:
        return False, "SS_PASSWORD 不能为空"

    # 容器内必须听 SERVER_PORT（爱快 5280:80 时这里应是 80，不是 5280）
    try:
        port = int(data["SERVER_PORT"])
    except ValueError:
        return False, "SERVER_PORT 无效"
    if port == 5280:
        return (
            False,
            "SERVER_PORT 填错了：容器内应是 80。爱快映射是 5280→80，请把服务端口改回 80 后保存。",
        )

    write_ss_config(data)
    stop_ss()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as log_f:
        log_f.write(f"\n==== restart {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
        log_f.write(f"config: {CONFIG_PATH.read_text(encoding='utf-8')}\n")
        log_f.flush()
        proc = subprocess.Popen(
            ["ssserver", "-c", str(CONFIG_PATH)],
            stdout=log_f,
            stderr=log_f,
            start_new_session=True,
        )

    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(proc.pid), encoding="utf-8")

    # 等插件起来
    for _ in range(15):
        time.sleep(0.2)
        if ss_pid() is None:
            return False, "ssserver 启动失败：\n" + read_log_tail(40)
        # 进程还在即可
        if proc.poll() is not None:
            return False, "ssserver 立即退出：\n" + read_log_tail(40)

    if ss_pid() is None:
        return False, "ssserver 启动失败：\n" + read_log_tail(40)
    return True, f"ssserver 已运行 (pid={proc.pid})，容器内监听 {data['SERVER_BIND']}:{data['SERVER_PORT']}"


def parse_lan_cidrs(raw: str) -> list[str]:
    items = []
    for part in re.split(r"[\s,;]+", raw.strip()):
        if not part:
            continue
        try:
            net = ipaddress.ip_network(part, strict=False)
            items.append(str(net))
        except ValueError as exc:
            raise ValueError(f"无效网段: {part}") from exc
    return items or [DEFAULT_LAN_CIDRS]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authed"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "unauthorized"}), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def build_client_bundle(data: dict[str, str]) -> dict[str, Any]:
    host = data.get("PUBLIC_HOST") or "YOUR_PUBLIC_IP"
    # 导出给客户端的端口：若用户配了常见映射，提示用 5280；默认仍用 SERVER_PORT
    # 客户端应填「爱快本地端口」，不是容器端口
    port = env("PUBLIC_PORT", "") or data["SERVER_PORT"]
    path = data["V2RAY_PATH"]
    password = data["SS_PASSWORD"]
    method = data["SS_METHOD"]
    lan = parse_lan_cidrs(data.get("LAN_CIDRS", DEFAULT_LAN_CIDRS))
    plugin_opts = f"mode=websocket;path={path};host={host};mux=0"

    ss_json = {
        "server": host,
        "server_port": int(port),
        "password": password,
        "method": method,
        "plugin": "v2ray-plugin",
        "plugin_opts": plugin_opts,
        "remarks": "SSfuckQOS-Home",
    }

    userinfo = base64.urlsafe_b64encode(f"{method}:{password}".encode()).decode().rstrip("=")
    plugin = quote(f"v2ray-plugin;{plugin_opts}")
    ss_uri = f"ss://{userinfo}@{host}:{port}/?plugin={plugin}#SSfuckQOS"

    clash_rules = "\n".join([f"  - IP-CIDR,{cidr},HOME-LAN,no-resolve" for cidr in lan])
    clash = f"""# SSfuckQOS — Clash Meta / Mihomo
# 客户端 REMOTE_PORT / port 填爱快「本地端口」(如 5280)，不是容器内 80

mixed-port: 7890
allow-lan: false
mode: rule
log-level: info

proxies:
  - name: SSfuckQOS
    type: ss
    server: {host}
    port: {port}
    cipher: {method}
    password: "{password}"
    plugin: v2ray-plugin
    plugin-opts:
      mode: websocket
      host: {host}
      path: {path}
      tls: false
      mux: false

proxy-groups:
  - name: HOME-LAN
    type: select
    proxies:
      - SSfuckQOS
  - name: PROXY
    type: select
    proxies:
      - SSfuckQOS
      - DIRECT

rules:
{clash_rules}
  - MATCH,DIRECT
"""

    docker_env = f"""SS_PASSWORD={password}
SS_METHOD={method}
V2RAY_PATH={path}
REMOTE_SERVER={host}
REMOTE_PORT={port}
LAN_CIDRS={",".join(lan)}
LOCAL_SOCKS_PORT=1080
LOCAL_HTTP_PORT=8118
"""

    return {
        "ss_json": ss_json,
        "ss_uri": ss_uri,
        "clash_yaml": clash,
        "docker_env": docker_env,
        "lan_cidrs": lan,
        "plugin_opts": plugin_opts,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        expected = env("ADMIN_PASSWORD", "admin")
        if hmac.compare_digest(password, expected):
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("密码错误", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    data = load_runtime()
    # 打开页面时若已停止则自动拉起
    if ss_pid() is None and data["SS_PASSWORD"]:
        ok, msg = restart_ss()
        if not ok:
            flash(msg, "error")
    running = ss_pid() is not None
    bundle = build_client_bundle(data) if data["SS_PASSWORD"] else None
    return render_template(
        "dashboard.html",
        data=data,
        running=running,
        uptime=int(time.time() - APP_START),
        pid=ss_pid(),
        bundle=bundle,
        log_tail=read_log_tail(60),
        methods=[
            "chacha20-ietf-poly1305",
            "aes-256-gcm",
            "aes-128-gcm",
            "xchacha20-ietf-poly1305",
        ],
    )


@app.route("/api/status")
@login_required
def api_status():
    data = load_runtime()
    return jsonify(
        {
            "ok": True,
            "running": ss_pid() is not None,
            "pid": ss_pid(),
            "uptime": int(time.time() - APP_START),
            "config": {
                "server_port": data["SERVER_PORT"],
                "method": data["SS_METHOD"],
                "v2ray_path": data["V2RAY_PATH"],
                "public_host": data["PUBLIC_HOST"],
                "lan_cidrs": data["LAN_CIDRS"],
            },
            "log_tail": read_log_tail(40),
        }
    )


@app.route("/api/lan-check")
@login_required
def api_lan_check():
    data = load_runtime()
    try:
        cidrs = parse_lan_cidrs(data.get("LAN_CIDRS", DEFAULT_LAN_CIDRS))
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    targets: list[str] = []
    for cidr in cidrs:
        net = ipaddress.ip_network(cidr, strict=False)
        hosts = list(net.hosts())
        if hosts:
            targets.append(str(hosts[0]))
        if len(targets) >= 5:
            break

    results = []
    for ip in targets:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True,
            text=True,
        )
        results.append({"ip": ip, "reachable": proc.returncode == 0})

    return jsonify({"ok": True, "lan_cidrs": cidrs, "probes": results})


@app.post("/save")
@login_required
def save():
    data = load_runtime()
    data["SERVER_PORT"] = request.form.get("SERVER_PORT", data["SERVER_PORT"]).strip()
    data["SS_PASSWORD"] = request.form.get("SS_PASSWORD", data["SS_PASSWORD"]).strip()
    data["SS_METHOD"] = request.form.get("SS_METHOD", data["SS_METHOD"]).strip()
    data["SS_TIMEOUT"] = request.form.get("SS_TIMEOUT", data["SS_TIMEOUT"]).strip()
    data["V2RAY_PATH"] = request.form.get("V2RAY_PATH", data["V2RAY_PATH"]).strip() or "/nas-sync"
    data["PUBLIC_HOST"] = request.form.get("PUBLIC_HOST", data["PUBLIC_HOST"]).strip()
    data["LAN_CIDRS"] = request.form.get("LAN_CIDRS", data["LAN_CIDRS"]).strip() or DEFAULT_LAN_CIDRS

    try:
        int(data["SERVER_PORT"])
        int(data["SS_TIMEOUT"])
        parse_lan_cidrs(data["LAN_CIDRS"])
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("dashboard"))

    if not data["V2RAY_PATH"].startswith("/"):
        data["V2RAY_PATH"] = "/" + data["V2RAY_PATH"]

    if data["SERVER_PORT"] == "5280":
        flash(
            "服务端口请填容器内端口 80（不是爱快本地端口 5280）。已拒绝保存。",
            "error",
        )
        return redirect(url_for("dashboard"))

    save_runtime(data)
    ok, msg = restart_ss()
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("dashboard"))


@app.post("/restart")
@login_required
def restart():
    ok, msg = restart_ss()
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("dashboard"))


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "running": ss_pid() is not None})


def main() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_runtime()
    if data["SS_PASSWORD"]:
        ok, msg = restart_ss()
        print(msg, flush=True)
        if not ok:
            print(read_log_tail(80), flush=True)
    host = env("ADMIN_BIND", "0.0.0.0")
    port = int(env("ADMIN_PORT", "8080"))
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
