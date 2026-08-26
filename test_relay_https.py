"""测试 relay + Chromium + HTTPS (outlook)。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import threading, time, asyncio
import requests, hashlib
from patchright.sync_api import sync_playwright
import pproxy

user = '202607171212542605'
passwd = '55184675'
akey = hashlib.md5(passwd.encode()).hexdigest()[8:24]

r = requests.get('http://www.zdopen.com/ShortS5Proxy/GetIP/',
                 params={'api': user, 'akey': akey, 'count': 1, 'timespan': 3, 'type': 3},
                 timeout=10)
p = r.json()['data']['proxy_list'][0]
ip, port = p['ip'], p['port']
print(f'远端: {ip}:{port}')

LOCAL_PORT = 9090
server = pproxy.Server(f'socks5://127.0.0.1:{LOCAL_PORT}')
remote = pproxy.Connection(f'socks5://{user}#{passwd}@{ip}:{port}')

def run():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.start_server({'rserver': [remote], 'authtime': 0}))
    loop.run_forever()

t = threading.Thread(target=run, daemon=True)
t.start()
time.sleep(2)

print(f'中继 127.0.0.1:{LOCAL_PORT}')

# 测试1: HTTP
print('\n=== HTTP ===')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://127.0.0.1:{LOCAL_PORT}'])
    try:
        ctx = b.new_context()
        page = ctx.new_page()
        page.goto('http://httpbin.org/ip', timeout=15000)
        print(f'OK: {page.evaluate("() => document.body.innerText").strip()}')
    except Exception as e:
        print(f'FAIL: {str(e)[:200]}')
    b.close()

# 测试2: HTTPS baidu
print('\n=== HTTPS baidu ===')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://127.0.0.1:{LOCAL_PORT}'])
    try:
        ctx = b.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.goto('https://www.baidu.com', timeout=15000)
        print(f'OK: {page.title()}')
    except Exception as e:
        print(f'FAIL: {str(e)[:200]}')
    b.close()

# 测试3: HTTPS outlook
print('\n=== HTTPS outlook ===')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://127.0.0.1:{LOCAL_PORT}'])
    try:
        ctx = b.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.goto('https://outlook.live.com/mail/0/?prompt=create_account', timeout=20000, wait_until='commit')
        print(f'OK: {page.title()}, url={page.url[:80]}')
    except Exception as e:
        print(f'FAIL: {str(e)[:300]}')
    b.close()
