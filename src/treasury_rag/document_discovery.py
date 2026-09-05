"""Local candidate discovery; no unselected excerpts are sent to generation."""
import re
import numpy as np


def confirmation(text: str) -> bool | None:
    value = re.sub(r"[\s.,!?。！？]+", " ", text.casefold()).strip()
    # Negation wins over a leading yes; conditional permission is not consent.
    if re.search(r"\b(no|cancel|don't|do not|not now)\b|不要|不用|取消", value):
        return False
    if re.search(r"\b(if|unless|but|maybe)\b|如果|但是|也许", value):
        return None
    if re.match(r"^(yes|sure|okay|ok|go ahead)\b", value) or re.match(r"^(好的|可以|同意)", value):
        return True
    if re.fullmatch(r"(?:please )?(?:select|read|use|open) (?:it|that|that document|the document)(?: please)?", value):
        return True
    if value in {"yes", "yes please", "sure", "ok", "okay", "go ahead", "read it",
                 "please do", "好的", "好", "可以", "是", "是的", "读取", "读吧", "同意"}:
        return True
    if value in {"no", "no thanks", "cancel", "don't", "do not", "不要", "不用", "取消", "否"}:
        return False
    return None


def asks_to_wait(text: str) -> bool:
    return bool(re.search(r"(?:i['’]ll|i will).*(?:send|ask)|(?:question|ask).*later|稍后|等下|再问", text.casefold()))


def choose_candidate(question, records, selected_ids, provider):
    unselected = [r for r in records if r.document_id not in selected_ids]
    if not unselected:
        return None
    # Explicit file names are a stronger signal than semantic similarity.
    q = question.casefold()
    named = [r for r in unselected if r.name.casefold() in q or
             (len(r.name.rsplit('.', 1)[0]) > 5 and r.name.rsplit('.', 1)[0].casefold() in q)]
    if len(named) == 1:
        return named[0]
    query_vector = provider.embed([question])[0]
    ranked = []
    for record in records:
        scores = record.pipeline.index.vectors @ query_vector
        ranked.append((float(np.max(scores)), record))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best = ranked[0]
    selected_score = max((s for s, r in ranked if r.document_id in selected_ids), default=0)
    # Conservative heuristic, not a calibrated probability or proof of an answer.
    if best.document_id not in selected_ids and best_score >= 0.35 and best_score >= selected_score + 0.04:
        return best
    return None
