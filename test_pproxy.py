"""测试 pproxy 中继方案：本地无认证 SOCKS5 → 远端带认证 SOCKS5 → Chromium。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import threading, time, asyncio
import requests, hashlib
from patchright.sync_api import sync_playwright
import pproxy

user = '202607171212542605'
passwd = '55184675'
akey = hashlib.md5(passwd.encode()).hexdigest()[8:24]

def get_proxy():
    r = requests.get('http://www.zdopen.com/ShortS5Proxy/GetIP/',
                     params={'api': user, 'akey': akey, 'count': 1, 'timespan': 3, 'type': 3},
                     timeout=10)
    p = r.json()['data']['proxy_list'][0]
    return p['ip'], p['port']

ip, port = get_proxy()
print(f'远端代理: {ip}:{port}')

LOCAL_PORT = 18080
print(f'启动本地中继 127.0.0.1:{LOCAL_PORT} -> socks5://{user}:***@{ip}:{port}')

server = pproxy.Server(f'socks5://127.0.0.1:{LOCAL_PORT}')
# pproxy 用 # 分隔 user 和 password
remote = pproxy.Connection(f'socks5://{user}#{passwd}@{ip}:{port}')

def run_relay():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.start({}, {'rserver': [remote]}))
    loop.run_forever()

t = threading.Thread(target=run_relay, daemon=True)
t.start()
time.sleep(2)

# 先用 requests 测本地中继是否通
print('\n--- 测试本地中继 (requests) ---')
try:
    r = requests.get('http://httpbin.org/ip',
                     proxies={'http': f'socks5h://127.0.0.1:{LOCAL_PORT}',
                              'https': f'socks5h://127.0.0.1:{LOCAL_PORT}'},
                     timeout=15)
    print(f'  requests OK: {r.text.strip()}')
except Exception as e:
    print(f'  requests FAIL: {e}')

# 再用 Chromium 连本地中继
print('\n--- 测试 Chromium 连本地中继 ---')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://127.0.0.1:{LOCAL_PORT}'])
    try:
        ctx = b.new_context()
        page = ctx.new_page()
        page.goto('http://httpbin.org/ip', timeout=15000)
        print(f'  Chromium OK: {page.evaluate("() => document.body.innerText").strip()}')
    except Exception as e:
        print(f'  Chromium FAIL: {str(e)[:200]}')
    b.close()
