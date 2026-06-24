import os
import time
import json
import urllib.parse
import requests
from playwright.sync_api import sync_playwright

SERVER_URL = os.getenv("ICEHOST_SERVER_URL")
ICEHOST_COOKIES = os.getenv("ICEHOST_COOKIES")
ICEHOST_PROXY = os.getenv("ICEHOST_PROXY")  # 👈 新增：读取代理环境变量

def send_tg_notification(message, photo_path=None):
    """发送结果和截图至 Telegram"""
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("未配置 TG 机器人变量，跳过发送 TG 推送。")
        return

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload)
        print("TG 状态通知发送成功。")
    except Exception as e:
        print(f"发送 TG 消息异常: {e}")

    if photo_path and os.path.exists(photo_path):
        try:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": "IceHost 实时画面"}
                requests.post(url, data=data, files=files)
            print("TG 截图发送成功。")
        except Exception as e:
            print(f"发送 TG 截图异常: {e}")

def run():
    if not SERVER_URL or not ICEHOST_COOKIES:
        print("错误: 缺少 ICEHOST_SERVER_URL 或 ICEHOST_COOKIES")
        return

    with sync_playwright() as p:
        
        # 👈 核心修改：动态组装浏览器启动参数（兼容代理设置 + 有头模式破盾）
        launch_options = {
            "headless": False,  # 👈 关键点：关闭无头模式，必须配合 Github Actions 的 xvfb 使用
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        }
        
        # 如果检测到代理变量，则注入代理配置
        if ICEHOST_PROXY:
            print(f"🔗 检测到代理配置，正在挂载代理节点: {ICEHOST_PROXY}")
            launch_options["proxy"] = {"server": ICEHOST_PROXY}
        else:
            print("🌐 未配置代理，将使用默认网络直连访问。")

        # 使用动态参数启动浏览器
        browser = p.chromium.launch(**launch_options)
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )

        # 隐藏自动化控制指纹
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            raw_data = json.loads(ICEHOST_COOKIES)
            cookies_to_add = []

            # 提取 Cookie 并准备注入
            if isinstance(raw_data, list):
                cookies_to_add = raw_data
            elif isinstance(raw_data, dict):
                cookies_to_add = raw_data.get("cookies", [])
            else:
                raise ValueError("未知的数据格式")

            # 1. 注入并进行高精度统一 URL 编码
            formatted_cookies = []
            for c in cookies_to_add:
                raw_value = c["value"]
                
                # 第一步：先解码，还原为未编码的原始字符
                clean_value = urllib.parse.unquote(raw_value)
                
                # 第二步：将原始字符进行全局统一的 URL 编码，避免 PHP 引擎加号漏洞
                encoded_value = urllib.parse.quote(clean_value)
                
                fc = {
                    "name": c["name"],
                    "value": encoded_value,
                    "domain": c["domain"],
                    "path": c.get("path", "/")
                }
                if "expirationDate" in c:
                    fc["expires"] = int(c["expirationDate"])
                if "secure" in c:
                    fc["secure"] = c["secure"]
                if "httpOnly" in c:
                    fc["httpOnly"] = c["httpOnly"]
                if "sameSite" in c:
                    ss = str(c["sameSite"]).lower()
                    if ss in ["no_restriction", "none"]:
                        fc["sameSite"] = "None"
                    elif ss == "lax":
                        fc["sameSite"] = "Lax"
                    elif ss == "strict":
                        fc["sameSite"] = "Strict"
                formatted_cookies.append(fc)
            
            context.add_cookies(formatted_cookies)
            print("Cookie 成功执行双重高精度 URL 编码并注入！已完美规避 PHP '+' 转换漏洞。")

        except Exception as e:
            print(f"凭证
