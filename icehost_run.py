import os
import requests
import json
import traceback

# 强制将标准输出缓冲关闭，确保 print 能实时显示在 GitHub 日志中
import sys
sys.stdout.reconfigure(line_buffering=True)

def run():
    print("🚀 [DEBUG] 脚本已启动...")
    
    try:
        cookies_raw = os.getenv("ICEHOST_COOKIES")
        cf_clearance = os.getenv("CF_CLEARANCE")
        proxy = os.getenv("ICEHOST_PROXY") # 获取代理
        renew_url = "https://dash.icehost.pl/api/client/freeservers/77b0cb78-52fb-4806-adf8-091416270a09/renew"
        
        print(f"🚀 [DEBUG] 正在初始化会话，代理: {proxy}")
        session = requests.Session()
        
        # 强制配置代理
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
            
        # 注入 Cookies
        cookies_list = json.loads(cookies_raw)
        for c in cookies_list:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain', 'dash.icehost.pl'))
        if cf_clearance:
            session.cookies.set("cf_clearance", cf_clearance, domain=".dash.icehost.pl")
        
        print("🚀 [DEBUG] Cookie 注入完成，正在发起 POST 请求...")
        
        # 增加超时限制，防止被阻塞
        headers = {"X-XSRF-TOKEN": session.cookies.get("XSRF-TOKEN", ""), "Referer": "https://dash.icehost.pl/server/77b0cb78"}
        response = session.post(renew_url, headers=headers, json={}, timeout=10)
        
        print(f"✅ [DEBUG] 请求完成，状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
    except Exception:
        print("❌ [DEBUG] 脚本运行出现异常:")
        traceback.print_exc()

if __name__ == "__main__":
    run()
