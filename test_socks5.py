"""测试 Chromium 对 SOCKS5 代理的各种支持方式。"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests, hashlib, time
from patchright.sync_api import sync_playwright

user = '202607171212542605'
passwd = '55184675'
akey = hashlib.md5(passwd.encode()).hexdigest()[8:24]


def get_proxy():
    url = 'http://www.zdopen.com/ShortS5Proxy/GetIP/'
    r = requests.get(url, params={'api': user, 'akey': akey, 'count': 1, 'timespan': 3, 'type': 3}, timeout=10)
    data = r.json()
    if data.get('code') != '10001':
        print(f'  API fail: {data}')
        return None
    p = data['data']['proxy_list'][0]
    return p['ip'], p['port']


# 方式1: launch --proxy-server=socks5://user:pass@host:port
p = get_proxy()
print(f'\n=== 1. launch --proxy-server=socks5://user:pass@host:port ===\n  proxy: {p[0]}:{p[1]}')
with sync_playwright() as pw:
    try:
        b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://{user}:{passwd}@{p[0]}:{p[1]}'])
        ctx = b.new_context()
        page = ctx.new_page()
        page.goto('http://httpbin.org/ip', timeout=15000)
        print(f'  OK: {page.evaluate("() => document.body.innerText").strip()}')
    except Exception as e:
        print(f'  FAIL: {str(e)[:200]}')
    finally:
        try: b.close()
        except: pass

time.sleep(12)

# 方式3: context proxy embedded creds in URL
p = get_proxy()
print(f'\n=== 3. context proxy embedded creds in URL ===\n  proxy: {p[0]}:{p[1]}')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    try:
        ctx = b.new_context(proxy={'server': f'socks5://{user}:{passwd}@{p[0]}:{p[1]}'})
        page = ctx.new_page()
        page.goto('http://httpbin.org/ip', timeout=15000)
        print(f'  OK: {page.evaluate("() => document.body.innerText").strip()}')
    except Exception as e:
        print(f'  FAIL: {str(e)[:200]}')
    finally:
        try: b.close()
        except: pass

time.sleep(12)

# 方式4: launch --proxy-server=socks5://host:port (no auth, 看错误类型)
p = get_proxy()
print(f'\n=== 4. launch --proxy-server=socks5://host:port (no auth) ===\n  proxy: {p[0]}:{p[1]}')
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://{p[0]}:{p[1]}'])
    try:
        ctx = b.new_context()
        page = ctx.new_page()
        page.goto('http://httpbin.org/ip', timeout=15000)
        print(f'  OK: {page.evaluate("() => document.body.innerText").strip()}')
    except Exception as e:
        print(f'  FAIL: {str(e)[:200]}')
    finally:
        try: b.close()
        except: pass
