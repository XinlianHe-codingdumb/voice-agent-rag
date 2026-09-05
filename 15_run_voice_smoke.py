from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from treasury_rag.config import PROJECT_ROOT, Settings  # noqa: E402
from treasury_rag.experiments import create_run_dir, snapshot_environment, write_run_manifest  # noqa: E402
from treasury_rag.io import write_json  # noqa: E402
from treasury_rag.rag_pipeline import HybridRAGPipeline  # noqa: E402
from treasury_rag.voice import text_for_speech  # noqa: E402
from treasury_rag.voice_evaluation import (  # noqa: E402
    critical_entity_accuracy,
    word_error_rate,
)


QUESTION = "What was the headroom against the stability rule in the OBR's March 2026 forecast?"
ENTITIES = ["headroom", "stability rule", "OBR", "March 2026"]


def main() -> None:
    settings = Settings.load()
    pipeline = HybridRAGPipeline(settings)
    run_id, run_dir = create_run_dir(settings.runs_dir, "voice-smoke", "synthetic-clean")

    started = time.perf_counter()
    question_audio = pipeline.provider.synthesize(QUESTION)
    question_tts_ms = round((time.perf_counter() - started) * 1_000)
    (run_dir / "question.mp3").write_bytes(question_audio)

    started = time.perf_counter()
    transcript = pipeline.provider.transcribe(question_audio, "question.mp3")
    asr_ms = round((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    answer, results, traces = pipeline.answer(transcript)
    rag_ms = round((time.perf_counter() - started) * 1_000)

    started = time.perf_counter()
    answer_audio = pipeline.provider.synthesize(text_for_speech(answer))
    answer_tts_ms = round((time.perf_counter() - started) * 1_000)
    (run_dir / "answer.mp3").write_bytes(answer_audio)

    metrics = {
        "wer": word_error_rate(QUESTION, transcript),
        "critical_entity_accuracy": critical_entity_accuracy(transcript, ENTITIES),
        "question_tts_ms": question_tts_ms,
        "asr_ms": asr_ms,
        "rag_ms": rag_ms,
        "answer_tts_ms": answer_tts_ms,
        "voice_round_trip_ms": asr_ms + rag_ms + answer_tts_ms,
    }
    result = {
        "question": QUESTION,
        "transcript": transcript,
        "answer": answer,
        "retrieved_pdf_pages": [item.chunk.pdf_page for item in results],
        "critical_entities": ENTITIES,
        "metrics": metrics,
        "traces": traces,
    }
    config = {
        "run_id": run_id,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "audio_condition": "synthetic clean speech; not a real-microphone benchmark",
        "asr_model": settings.asr_model,
        "tts_model": settings.tts_model,
        "tts_voice": settings.tts_voice,
        "environment": snapshot_environment(PROJECT_ROOT),
    }
    write_json(run_dir / "metrics.json", metrics)
    write_json(run_dir / "result.json", result)
    write_json(run_dir / "run_config.json", config)
    (run_dir / "summary.md").write_text(
        "# Synthetic clean voice smoke test\n\n"
        f"- WER: {metrics['wer']:.3f}\n"
        f"- Critical entity accuracy: {metrics['critical_entity_accuracy']:.3f}\n"
        f"- ASR: {asr_ms} ms\n"
        f"- RAG: {rag_ms} ms\n"
        f"- Answer TTS: {answer_tts_ms} ms\n"
        f"- Voice round trip: {metrics['voice_round_trip_ms']} ms\n\n"
        "This uses synthetic clean input and is an engineering smoke test, not a noisy real-microphone benchmark.\n",
        encoding="utf-8",
    )
    write_run_manifest(run_dir, {"run_config": config, "result": result})

    print("\nSynthetic voice smoke results")
    print(f"Transcript: {transcript}")
    print(f"WER: {metrics['wer']:.3f}")
    print(f"Critical entity accuracy: {metrics['critical_entity_accuracy']:.3f}")
    print(f"ASR / RAG / TTS ms: {asr_ms} / {rag_ms} / {answer_tts_ms}")
    print(f"Run ID: {run_id}")
    print(f"Immutable run directory: {run_dir}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise
