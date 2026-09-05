"""Auditable real-server regression. Only deletes its own synthetic resources."""
import json
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
import httpx
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    run = ROOT / 'reports/runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_consent-delete-ocr')
    run.mkdir(parents=True)
    result = {'checks': [], 'cleanup': [], 'limitations': ['No physical microphone or WebRTC audio test.', 'OCR can confuse I/l; handwriting and table structure not validated.']}
    tests = subprocess.run([sys.executable, 'run_tests.py'], cwd=ROOT, capture_output=True, text=True,
                           env={**os.environ, 'PYTEST_ADDOPTS': f'--basetemp="{run / "pytest-tmp"}"'})
    (run / 'tests.txt').write_text(tests.stdout + tests.stderr, encoding='utf-8')
    result['tests_exit_code'] = tests.returncode
    ids, doc_id = [], None
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=180) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        def compact(data):
            return {k: v for k, v in data.items() if k not in ('audio_base64', 'response_instructions')}
        try:
            assert tests.returncode == 0
            docs = request('GET', '/api/documents')['documents']
            book = next(d for d in docs if d['name'] == 'AI Agent Book.pdf')
            treasury = next(d for d in docs if d['name'].startswith('HM_Treasury'))
            for mode, phrase in [('ask', 'Yes, please do that.'), ('intent', "Yes, please select it. I'll send you my question based on that.")]:
                cid = request('POST', '/api/conversations', json={'title': 'Temporary consent OCR regression'})['conversation_id']
                ids.append(cid)
                request('POST', f'/api/conversations/{cid}/documents/{treasury["document_id"]}')
                key = 'question' if mode == 'ask' else 'text'
                proposal = request('POST', '/api/' + mode, json={key: 'What part of AI Agent Book.pdf covers reinforcement learning?', 'conversation_id': cid})
                assert proposal['document_access']['status'] == 'pending'
                accepted = request('POST', '/api/' + mode, json={key: phrase, 'conversation_id': cid})
                assert accepted['document_access']['status'] == 'attached'
                attached = request('GET', '/api/conversations/' + cid)['document_ids']
                assert set(attached) == {book['document_id'], treasury['document_id']}
                followup = request('POST', '/api/ask', json={'question': 'What part of this book covers reinforcement learning?', 'conversation_id': cid})
                assert any(s.get('document_id') == book['document_id'] or s.get('document_name') == book['name'] for s in followup['sources']), followup
                result['checks'].append({'mode': mode, 'consent': phrase, 'accepted': compact(accepted), 'followup': compact(followup), 'document_ids': attached})
            image = Image.new('RGB', (1600, 900), 'white')
            ImageDraw.Draw(image).text((90, 120), 'Project ORION budget is 4729 dollars.', font=ImageFont.truetype('arial.ttf', 48), fill='black')
            pdf = run / 'synthetic-scan.pdf'
            image.save(pdf, 'PDF', resolution=150)
            with pdf.open('rb') as handle:
                uploaded = request('POST', '/api/documents', data={'conversation_id': ids[-1]}, files={'file': ('synthetic-scan.pdf', handle, 'application/pdf')})
            doc_id = uploaded['document_id']
            answer = request('POST', '/api/ask', json={'question': 'What budget is stated in synthetic-scan.pdf?', 'conversation_id': ids[-1]})
            assert '4729' in answer['answer'].replace(',', ''), answer
            assert any(s['pdf_page'] == 1 for s in answer['sources'])
            result['checks'].append({'mode': 'real-scanned-upload-rag', 'upload': uploaded, 'answer': compact(answer)})
            removed = request('DELETE', '/api/documents/' + doc_id)
            assert all(d['document_id'] != doc_id for d in request('GET', '/api/documents')['documents'])
            assert doc_id not in request('GET', '/api/conversations/' + ids[-1])['document_ids']
            result['checks'].append({'mode': 'remove-synthetic-document', 'result': removed})
            doc_id = None
            result['status'] = 'passed'
        except Exception as exc:
            result['status'] = 'failed'
            result['error'] = str(exc)
            raise
        finally:
            if doc_id:
                result['cleanup'].append({'document_id': doc_id, 'status': client.delete('/api/documents/' + doc_id).status_code})
            for cid in ids:
                result['cleanup'].append({'conversation_id': cid, 'status': client.delete('/api/conversations/' + cid).status_code})
            (run / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(run)
            print(result.get('status'))


if __name__ == '__main__':
    main()
