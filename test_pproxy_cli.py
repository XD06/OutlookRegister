"""用 pproxy CLI (subprocess) 启动中继，测试 Chromium 连通性。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import subprocess, time, threading, socket
from patchright.sync_api import sync_playwright
import requests, hashlib

user = '202607171212542605'
passwd = '55184675'
akey = hashlib.md5(passwd.encode()).hexdigest()[8:24]

r = requests.get('http://www.zdopen.com/ShortS5Proxy/GetIP/',
                 params={'api': user, 'akey': akey, 'count': 1, 'timespan': 3, 'type': 3})
p = r.json()['data']['proxy_list'][0]
ip, port = p['ip'], p['port']
print(f'远端: {ip}:{port}')

LOCAL_PORT = 9191
cmd = [
    sys.executable, '-m', 'pproxy',
    '-l', f'socks5://:{LOCAL_PORT}',
    '-r', f'socks5://{user}#{passwd}@{ip}:{port}',
    '-v',
]

print(f'启动 pproxy: {" ".join(cmd)}')
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

# 等端口监听
for _ in range(30):
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', LOCAL_PORT))
        s.close()
        print(f'端口 {LOCAL_PORT} 已监听')
        break
    except Exception:
        time.sleep(0.3)
else:
    print('端口未监听')
    proc.terminate()
    sys.exit(1)

# 测试
def test(label, url, wait_until='load'):
    print(f'\n=== {label} ===')
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=[f'--proxy-server=socks5://127.0.0.1:{LOCAL_PORT}'])
        try:
            ctx = b.new_context(ignore_https_errors=True)
            page = ctx.new_page()
            page.goto(url, timeout=20000, wait_until=wait_until)
            print(f'OK: {page.title()}, url={page.url[:80]}')
        except Exception as e:
            print(f'FAIL: {str(e)[:300]}')
        b.close()

test('HTTP httpbin', 'http://httpbin.org/ip')
test('HTTPS baidu', 'https://www.baidu.com')
test('HTTPS outlook', 'https://outlook.live.com/mail/0/?prompt=create_account', 'commit')

proc.terminate()
