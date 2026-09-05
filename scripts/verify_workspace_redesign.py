"""Verify new minimal backend contracts using existing speech sample, without RAG side effects."""
from datetime import datetime, timezone
from pathlib import Path
import json
import httpx

ROOT = Path(__file__).resolve().parents[1]

def main():
    run = ROOT / 'reports/runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_workspace-redesign')
    run.mkdir(parents=True)
    report = {'checks': [], 'limitations': 'Recorded MP3 replay; physical microphone/WebRTC audio is not verified by this script.'}
    try:
        with httpx.Client(base_url='http://127.0.0.1:8000', timeout=90) as client:
            before=client.get('/api/conversations').json()['conversations']
            audio=ROOT/'reports/runs/20260903T092909Z_voice-smoke_synthetic-clean/question.mp3'
            with audio.open('rb') as handle:
                response=client.post('/api/transcribe',data={'language':'en'},files={'file':('question.mp3',handle,'audio/mpeg')})
            response.raise_for_status()
            payload=response.json()
            assert 'March 2026' in payload['transcript'],payload
            assert 'answer' not in payload
            after=client.get('/api/conversations').json()['conversations']
            assert before==after, 'Transcription unexpectedly changed conversation state'
            report['checks'].append({'name':'transcribe-only-no-conversation-write','result':payload})
            html=client.get('/').text
            assert 'workspace.js' in html and 'recorder-state' in html and 'documents-page' in html
            assert 'Upgrade to Pro' not in html and '>JD<' not in html
            report['checks'].append({'name':'final-html-delivered','passed':True})
            report['status']='passed'
    except Exception as exc:
        report['status']='failed';report['error']=str(exc)
        raise
    finally:
        (run/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(run)

if __name__=='__main__':
    main()
