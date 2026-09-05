"""Replay consent and English Mic regression against the running local backend."""
import json
from datetime import datetime, timezone
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    run = ROOT / 'reports' / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_document-access-language')
    run.mkdir(parents=True)
    report = {'checks': [], 'cleanup': [], 'limitations': 'Synthetic MP3 replay; live microphone/WebRTC acceptance still needed.'}
    ids = []
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=120) as client:
        def post(path, **kwargs):
            response = client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()
        def compact(result):
            return {k: v for k, v in result.items() if k not in {'audio_base64', 'response_instructions'}}
        try:
            for mode in ('ask', 'realtime'):
                cid = post('/api/conversations', json={'title': 'Temporary consent verification'})['conversation_id']
                ids.append(cid)
                q = "What was the headroom against the stability rule in the OBR's March 2026 forecast?"
                endpoint = '/api/ask' if mode == 'ask' else '/api/intent'
                key = 'question' if mode == 'ask' else 'text'
                proposed = post(endpoint, json={key: q, 'conversation_id': cid})
                assert proposed['document_access']['status'] == 'pending', proposed
                assert proposed['document_access']['name'] == 'HM_Treasury_ARA_25-26.pdf'
                assert client.get('/api/conversations/' + cid).json()['document_ids'] == []
                accepted = post(endpoint, json={key: 'yes please', 'conversation_id': cid})
                assert accepted['document_access']['status'] == 'attached', accepted
                if mode == 'ask':
                    assert '23.6' in accepted['answer'], accepted['answer']
                    assert any(s['pdf_page'] == 22 for s in accepted['sources'])
                else:
                    assert accepted['question'] == q
                    assert 'original question' in accepted['response_instructions']
                    assert accepted['requires_documents'] is True
                report['checks'].append({'mode': mode, 'proposal': compact(proposed), 'accepted': compact(accepted)})
            audio = ROOT / 'reports/runs/20260903T092909Z_voice-smoke_synthetic-clean/question.mp3'
            with audio.open('rb') as handle:
                voice = post('/api/voice', data={'conversation_id': ids[0], 'language': 'en'},
                             files={'file': ('question.mp3', handle, 'audio/mpeg')})
            assert 'March 2026' in voice['transcript']
            assert '23.6' in voice['answer']
            report['checks'].append({'mode': 'Mic-English', 'result': compact(voice)})
            report['status'] = 'passed'
        except Exception as exc:
            report['status'] = 'failed'
            report['error'] = str(exc)
            raise
        finally:
            for cid in ids:
                response = client.delete('/api/conversations/' + cid)
                report['cleanup'].append({'conversation_id': cid, 'deleted': response.status_code == 200})
            (run / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(str(run))
            print(report.get('status'))


if __name__ == '__main__':
    main()
