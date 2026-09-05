import pytest
from test_document_discovery import state_fixture
from treasury_rag.document_discovery import confirmation
from treasury_rag.memory import ConversationStore
from treasury_rag.pdf import extract_pages, inspect_pdf


@pytest.mark.parametrize('phrase', ['Yes, please do that.', 'Yes, please select it.', 'Sure, go ahead.', '好的，请读取'])
def test_natural_consent_attaches_and_resumes(tmp_path, phrase):
    state = state_fixture(tmp_path)
    state.memory.attach_document('a', 'other')
    state.prepare_turn('Where is DPO discussed?', 'a')
    result = state.prepare_turn(phrase, 'a')
    assert result['question'] == 'Where is DPO discussed?'
    assert set(state.memory.document_ids('a')) == {'book', 'other'}
    assert result['document_access']['status'] == 'attached'


def test_select_then_wait(tmp_path):
    state = state_fixture(tmp_path)
    state.prepare_turn('Where is DPO discussed?', 'a')
    result = state.prepare_turn("Yes, please select it. I'll send you my question based on that.", 'a')
    assert 'Selected book.pdf' in result['direct_reply']
    assert state.memory.document_ids('a') == ['book']
    assert 'document_access' not in state.prepare_turn('Where is DPO discussed?', 'a')


@pytest.mark.parametrize('text,expected', [("Yes but don't select it", False), ('Maybe, if it is relevant', None), ('No thanks', False)])
def test_not_unconditional_consent(text, expected):
    assert confirmation(text) is expected


def test_delete_document_clears_all_chats_pending_and_survives_restart(tmp_path):
    state = state_fixture(tmp_path)
    state.memory.attach_document('a', 'book')
    state.memory.attach_document('b', 'book')
    state.memory.propose_access('c', 'book', 'question')
    state.delete_document('book')
    assert 'book' not in state.documents
    reopened = ConversationStore(tmp_path / 'test.sqlite3')
    assert reopened.document_ids('a') == reopened.document_ids('b') == []
    assert reopened.pending_access('c') is None
    assert reopened.hidden_documents() == {'book'}
    reopened.restore_document('book')
    assert reopened.hidden_documents() == set()


def test_delete_default_does_not_reimport(tmp_path):
    store = ConversationStore(tmp_path / 'db')
    assert store.first_initialization()
    store.append_turn('default', 'question', 'answer')
    store.delete('default')
    assert not ConversationStore(tmp_path / 'db').first_initialization()
    assert store.list_conversations() == []


def test_real_scanned_pdf_ocr(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1600, 900), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('DejaVuSans.ttf' if __import__('os').name != 'nt' else 'arial.ttf', 48)
    draw.text((90, 120), 'Project ORION budget is 4729 dollars.', fill='black', font=font)
    pdf = tmp_path / 'scan.pdf'
    image.save(pdf, 'PDF', resolution=150)
    assert inspect_pdf(pdf).pages_with_text == 0
    assert extract_pages(pdf, ocr=False)[0].text == ''
    trace = []
    pages = extract_pages(pdf, extraction_trace=trace)
    assert trace[0]['source'] == 'ocr'
    assert trace[0]['native_characters'] == 0
    assert pages[0].pdf_page == 1
    assert '4729' in pages[0].text
    expected = 'Project ORION budget is 4729 dollars.'
    # OCR may confuse uppercase I and lowercase l; do not hide that limitation.
    assert len(pages[0].text) == len(expected)
    assert sum(a != b for a, b in zip(expected, pages[0].text)) / len(expected) < 0.05
