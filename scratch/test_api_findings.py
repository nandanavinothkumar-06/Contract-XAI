import requests

s = requests.Session()
r0 = s.get('http://127.0.0.1:5000/')
csrf_token = s.cookies.get('contractrisk_csrf')
headers = {'X-CSRF-Token': csrf_token}

r1 = s.post('http://127.0.0.1:5000/api/auth/login', json={'email': 'advocate@legal.in', 'password': 'LegalTech2026!'}, headers=headers)
print('Login status:', r1.status_code, r1.json().get('user', {}).get('email'))

csrf_token = s.cookies.get('contractrisk_csrf') or csrf_token
headers['X-CSRF-Token'] = csrf_token

r2 = s.get('http://127.0.0.1:5000/api/review/queue', headers=headers)
print('Queue status:', r2.status_code, 'Count:', r2.json().get('count'))

r3 = s.get('http://127.0.0.1:5000/api/review/28976229-2dff-434a-9c9e-6449399f4a78', headers=headers)
print('Review status:', r3.status_code)
data = r3.json()
findings = data.get('findings', [])
print(f'Findings count: {len(findings)}')
for f in findings:
    f_id = f.get('id')
    label = f.get('risk_label')
    score = f.get('ai_confidence_score')
    attr = bool(f.get('model_attribution'))
    obs = f.get('ai_observation', '')[:70]
    print(f'  Finding {f_id}: label={label}, score={score}, attribution={attr}, obs={repr(obs)}')
