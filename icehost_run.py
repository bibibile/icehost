import os
import requests
import json

def send_tg_notification(message):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})

def run():
    cookies_raw = os.getenv("ICEHOST_COOKIES")
    cf_clearance = os.getenv("CF_CLEARANCE")
    api_url = "https://dash.icehost.pl/server/77b0cb78" # 换回页面地址用于检测状态
    renew_url = "https://dash.icehost.pl/api/client/freeservers/77b0cb78-52fb-4806-adf8-091416270a09/renew"

    session = requests.Session()
    
    # 注入 Cookies
    cookies_list = json.loads(cookies_raw)
    for c in cookies_list:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', 'dash.icehost.pl'))
    if cf_clearance:
        session.cookies.set("cf_clearance", cf_clearance, domain=".dash.icehost.pl")

    # 执行续期请求
    headers = {"X-XSRF-TOKEN": session.cookies.get("XSRF-TOKEN"), "Referer": "https://dash.icehost.pl/server/77b0cb78"}
    response = session.post(renew_url, headers=headers, json={})
    
    # 根据结果发送 TG 通知
    if response.status_code == 200:
        msg = "⚡ <b>IceHost 续期成功！</b>\nAPI 响应: " + response.text
        send_tg_notification(msg)
    else:
        msg = f"❌ <b>IceHost 续期失败</b>\n状态码: {response.status_code}\n内容: {response.text}"
        send_tg_notification(msg)

if __name__ == "__main__":
    run()
