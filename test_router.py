import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
try:
    r = s.post('http://192.168.1.26/login', json={'username':'admin','password':'pro234'}, timeout=2)
    print('Status:', r.status_code)
    print(r.text[:200])
except Exception as e:
    print('Exception:', type(e).__name__, str(e)[:200])
