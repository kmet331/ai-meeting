import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with socket.socket() as _sock:
    _sock.bind(('127.0.0.1', 0))
    PORT = _sock.getsockname()[1]

env = os.environ.copy()
env['AI_MEETING_ENGINE'] = str(ROOT / 'tests' / 'mock_meeting.py')
env['AI_MEETING_PORT'] = str(PORT)
env['AI_MEETING_NO_BROWSER'] = '1'
proc = subprocess.Popen([sys.executable, str(ROOT/'app.py')], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def wait_port():
    deadline=time.time()+5
    while time.time()<deadline:
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=.2): return
        except OSError: time.sleep(.05)
    raise RuntimeError('server did not start')

try:
    wait_port()
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/health') as r:
        health=json.loads(r.read().decode())
        assert health['ok'] is True

    payload=json.dumps({'topic':'테스트 안건','participants':['CEO','디자이너'],'duration':3}, ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/start', data=payload, headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req) as r:
        mid=json.loads(r.read().decode())['id']

    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/events?id={mid}', timeout=5) as r:
        text=r.read().decode('utf-8')

    assert 'event: setup' in text
    assert text.count('event: speech') >= 3
    assert '사진은 크게 갑니다.' in text
    assert 'event: secretary' in text
    assert 'event: summary' in text
    assert '대표 사진은 넣되 회사 메시지가 먼저 보이게 제한한다.' in text
    assert 'event: done' in text

    # A second meeting must get a fresh session and complete independently.
    payload2=json.dumps({'topic':'두 번째 안건','participants':['CEO','마케팅팀장','디자이너'],'duration':3}, ensure_ascii=False).encode('utf-8')
    req2=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/start', data=payload2, headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req2) as r:
        mid2=json.loads(r.read().decode())['id']
    assert mid2 != mid
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/events?id={mid2}', timeout=5) as r:
        text2=r.read().decode('utf-8')
    assert 'event: setup' in text2 and 'event: summary' in text2 and 'event: done' in text2

    # Explicit cancel endpoint exists so leaving a live meeting can stop its subprocess.
    payload3=json.dumps({'topic':'취소 테스트','participants':['CEO','디자이너'],'duration':5}, ensure_ascii=False).encode('utf-8')
    req3=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/start', data=payload3, headers={'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req3) as r:
        mid3=json.loads(r.read().decode())['id']
    cancel_req=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/cancel?id={mid3}', data=b'', method='POST')
    with urllib.request.urlopen(cancel_req) as r:
        assert json.loads(r.read().decode())['ok'] is True

    # Invalid participant count must fail before running engine.
    bad=json.dumps({'topic':'x','participants':['CEO'],'duration':3}, ensure_ascii=False).encode('utf-8')
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/api/start', data=bad, headers={'Content-Type':'application/json'}, method='POST')
    try:
        urllib.request.urlopen(req)
        raise AssertionError('single-participant request unexpectedly succeeded')
    except urllib.error.HTTPError as e:
        assert e.code == 400

    print('INTEGRATION PASS: health, validation, independent sessions, cancellation, subprocess stdin, SSE speech/timer/secretary/summary/done')
finally:
    proc.terminate()
    try: proc.wait(timeout=3)
    except subprocess.TimeoutExpired: proc.kill()
