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
            print(f"凭证解析/注入失败: {e}")
            send_tg_notification(f"❌ <b>IceHost 运行异常</b>\n凭证解析注入失败: {e}")
            browser.close()
            return

        page = context.new_page()

        # 全局网络流量拦截与指纹清洗
        def handle_route(route):
            headers = {**route.request.headers}
            headers["sec-ch-ua"] = '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = '"Windows"'
            headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            route.continue_(headers=headers)

        page.route("**/*", handle_route)

        print(f"正在访问 IceHost 面板: {SERVER_URL}")
        page.goto(SERVER_URL)
        
        # 初始等待页面加载
        page.wait_for_timeout(4000)

        # ⚔️ 终极融合：Cloudflare Turnstile 自动物理破盾逻辑
        cf_iframe = page.locator("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile']").first
        if cf_iframe.is_visible():
            print("🛡️ 检测到 Cloudflare 人机验证盾，准备模拟真实物理点击...")
            try:
                # 获取验证框的绝对物理坐标
                box = cf_iframe.bounding_box()
                if box:
                    # 计算中心点坐标
                    target_x = box["x"] + box["width"] / 2
                    target_y = box["y"] + box["height"] / 2
                    
                    # 模拟真实鼠标移动并点击（避开自动化检测）
                    page.mouse.move(target_x, target_y, steps=10)
                    page.wait_for_timeout(500)
                    page.mouse.click(target_x, target_y)
                    print("🖱️ 已物理点击验证框，等待验证通过...")
                    
                    # 给 Cloudflare 一点时间转圈和验证
                    page.wait_for_timeout(8000)
            except Exception as e:
                print(f"⚠️ 点击验证框时出现异常: {e}")
        else:
            # 如果没有盾，补足剩余的常规等待时间
            page.wait_for_timeout(6000)

        # 首次截图
        page.screenshot(path="icehost_debug_screenshot.png")

        # 判断登录状态
        if "login" in page.url or page.locator("input[type='email']").first.is_visible():
            msg = "❌ <b>IceHost 登录失效！</b>\n请在浏览器重新提取并更新 ICEHOST_COOKIES。"
            print(msg)
            send_tg_notification(msg, "icehost_debug_screenshot.png")
            browser.close()
            return

        # 3. 核心探测：终极融合英/波双语拦截关键词
        keywords = [
            "Nie możesz przedłużyć", "niedawno to zrobiłeś", "kolejne 6 godziny",
            "cannot extend", "recently", "another 6 hours", "wait"
        ]
        is_limited = False
        
        for kw in keywords:
            if page.locator(f"text={kw}").first.is_visible():
                is_limited = True
                break
        
        if is_limited:
            # 页面一加载就已经是限制状态：说明未到可续期时间，直接安静退出
            print("检测到红框限制提示：说明未到可续期时间。结束本次运行（不发送 Telegram 提醒）。")
            browser.close()
            return

        # 4. 终极融合：安全寻找并点击英/波双语续期按钮
        renew_btn = page.locator("a:has-text('DODAJ 6 GODZIN'), a:has-text('ADD 6 HOURS VALIDITY'), button:has-text('DODAJ 6 GODZIN'), button:has-text('ADD 6 HOURS VALIDITY'), [class*='blue']:has-text('DODAJ 6 GODZIN'), [class*='blue']:has-text('ADD 6 HOURS VALIDITY')").first
        
        if renew_btn.is_visible() and renew_btn.is_enabled():
            print("未检测到限制提示，找到续期按钮，正在点击...")
            renew_btn.click()
            page.wait_for_timeout(10000) # 等待 10 秒
            
            # 重新截图
            page.screenshot(path="icehost_debug_screenshot.png")
            
            # 二次检测结果
            is_now_limited = False
            for kw in keywords:
                if page.locator(f"text={kw}").first.is_visible():
                    is_now_limited = True
                    break
                    
            if is_now_limited:
                print("点击后弹出了红框提示：说明未到可续期时间（续期未成功）。结束本次运行（不发送 Telegram 提醒）。")
            else:
                msg = "⚡ <b>IceHost 服务器续期成功！</b>\n服务器已真正成功延长 6 小时有效期。"
                print(msg)
                send_tg_notification(msg, "icehost_debug_screenshot.png")
        else:
            print("未在页面中找到可用的蓝色续期按钮。")

        browser.close()

if __name__ == "__main__":
    run()
