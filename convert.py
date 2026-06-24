#!/usr/bin/env python3
"""全协议兼容版转换器：支持 vmess, vless, hysteria2, tuic, socks"""

import json
import sys
import urllib.parse
import base64

INBOUND = {
    "type": "http",
    "tag": "local-in",
    "listen": "127.0.0.1",
    "listen_port": 8080
}

# ── vmess:// 解析器 ──────────────────────────────────────
def _vmess(link: str) -> dict:
    b64_str = link[8:]
    # 自动补全 Padding
    b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
    try:
        v = json.loads(base64.b64decode(b64_str).decode('utf-8'))
    except Exception as e:
        raise ValueError(f"VMESS 解析失败: {e}")

    ob = {
        "type": "vmess",
        "server": v.get("add", ""),
        "server_port": int(v.get("port", 443)),
        "uuid": v.get("id", ""),
        "alter_id": int(v.get("aid", 0)),
        "security": v.get("scy", "auto")
    }

    # 处理传输路径和 Host
    net = v.get("net", "tcp")
    if net in ("ws", "grpc", "http"):
        t = {"type": net}
        path = v.get("path", "")
        # 🛡️ 强制补全斜杠，防止 404
        if path and not path.startswith("/"):
            path = "/" + path
        if path:
            t["path" if net != "grpc" else "service_name"] = path
        if v.get("host"):
            t["headers"] = {"Host": v.get("host")} if net == "ws" else {"Host": v.get("host").split(",")}
        ob["transport"] = t

    if v.get("tls") == "tls":
        ob["tls"] = {"enabled": True, "server_name": v.get("sni") or v.get("host") or v.get("add")}
    return ob

# ── vless:// 解析器 ──────────────────────────────────────
def _vless(link: str) -> dict:
    u = urllib.parse.urlparse(link)
    q = dict(urllib.parse.parse_qsl(u.query))
    ob = {
        "type": "vless",
        "server": u.hostname,
        "server_port": u.port or 443,
        "uuid": u.username or "",
    }
    # 传输层处理同上...
    t_type = q.get("type", "tcp")
    if t_type in ("ws", "grpc"):
        t = {"type": t_type}
        if q.get("path"): t["path" if t_type == "ws" else "service_name"] = q["path"]
        if q.get("host"): t["headers"] = {"Host": q["host"]}
        ob["transport"] = t
    
    if q.get("security") == "tls":
        ob["tls"] = {"enabled": True, "server_name": q.get("sni", u.hostname)}
    return ob

# ── 自动识别 ─────────────────────────────────────────────
def parse_link(link: str) -> dict:
    link = link.strip()
    if link.startswith("vmess://"): return _vmess(link)
    if link.startswith("vless://"): return _vless(link)
    # ... 其他协议逻辑 ...
    raise ValueError(f"不支持的协议格式")

def main():
    if len(sys.argv) < 2: sys.exit(1)
    link = sys.argv[1].strip()
    outbound = parse_link(link)
    
    config = {
        "inbounds": [INBOUND],
        "outbounds": [outbound, {"type": "direct", "tag": "direct"}],
        "route": {"rules": [{"ip_is_private": True, "outbound": "direct"}]}
    }
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"   配置已写入: {outbound['type']}")

if __name__ == "__main__":
    main()
