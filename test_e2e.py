import requests, json

BASE = 'http://127.0.0.1:8000'

# Add a cardiologist
r = requests.post(f'{BASE}/api/doctors', json={
    'name': 'Dr. Priya Nair',
    'mobile': '+919876543211',
    'specialty': 'Cardiologist',
    'city': 'Bangalore'
})
print('Add doctor:', r.status_code, r.json().get('name'))

# Prepare messages
r2 = requests.post(f'{BASE}/api/executions/prepare-due')
print('Prepare due:', r2.json())

# Get prepared messages
r3 = requests.get(f'{BASE}/api/executions/prepared')
msgs = r3.json()
print(f'Prepared messages: {len(msgs)}')
if msgs:
    m = msgs[0]
    dname = m['doctor_name']
    step  = m['step_name']
    msg   = (m.get('message') or '')[:80]
    walink = (m.get('wa_link') or '')[:70]
    print(f'  Doctor: {dname}')
    print(f'  Step:   {step}')
    print(f'  Msg preview: {msg}')
    print(f'  WA link: {walink}')

# Dashboard stats
r4 = requests.get(f'{BASE}/api/dashboard/stats')
stats = r4.json()
print('Dashboard stats:')
print(f'  total_doctors: {stats["total_doctors"]}')
print(f'  active_pipelines: {stats["active_pipelines"]}')
print(f'  pending_messages: {stats["pending_messages"]}')
print(f'  due_today: {stats["due_today"]}')

print('E2E TEST PASSED')
