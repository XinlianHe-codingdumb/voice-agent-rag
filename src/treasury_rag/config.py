from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDF_PATH = PROJECT_ROOT / "HM_Treasury_ARA_25-26.pdf"
BASELINE_ARTIFACT_DIR = PROJECT_ROOT / "artifacts" / "baseline"
LATEST_REPORT_DIR = PROJECT_ROOT / "reports" / "latest"
RUNS_REPORT_DIR = PROJECT_ROOT / "reports" / "runs"
GOLD_DATASET_PATH = PROJECT_ROOT / "eval" / "gold_retrieval.jsonl"


@dataclass(frozen=True)
class Settings:
    pdf_path: Path
    artifact_dir: Path
    report_dir: Path
    runs_dir: Path
    gold_dataset_path: Path
    openai_api_key: str | None
    embedding_model: str
    chat_model: str
    asr_model: str
    tts_model: str
    tts_voice: str
    realtime_model: str
    realtime_voice: str
    chunk_words: int
    overlap_words: int
    top_k: int
    embedding_batch_size: int
    eval_split: str

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        eval_split = os.getenv("RAG_EVAL_SPLIT", "dev").strip().lower()
        if eval_split not in {"dev", "test", "all"}:
            raise ValueError("RAG_EVAL_SPLIT must be one of: dev, test, all")
        return cls(
            pdf_path=Path(os.getenv("RAG_PDF_PATH", str(DEFAULT_PDF_PATH))).resolve(),
            artifact_dir=Path(
                os.getenv("RAG_ARTIFACT_DIR", str(BASELINE_ARTIFACT_DIR))
            ).resolve(),
            report_dir=Path(
                os.getenv("RAG_REPORT_DIR", str(LATEST_REPORT_DIR))
            ).resolve(),
            runs_dir=Path(
                os.getenv("RAG_RUNS_DIR", str(RUNS_REPORT_DIR))
            ).resolve(),
            gold_dataset_path=Path(
                os.getenv("RAG_GOLD_DATASET", str(GOLD_DATASET_PATH))
            ).resolve(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"
            ),
            chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-5.4-mini"),
            asr_model=os.getenv("OPENAI_ASR_MODEL", "gpt-4o-transcribe"),
            tts_model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
            realtime_model=os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1"),
            realtime_voice=os.getenv("OPENAI_REALTIME_VOICE", "marin"),
            chunk_words=_positive_int("RAG_CHUNK_WORDS", 220),
            overlap_words=_non_negative_int("RAG_CHUNK_OVERLAP_WORDS", 40),
            top_k=_positive_int("RAG_TOP_K", 5),
            embedding_batch_size=_positive_int(
                "OPENAI_EMBEDDING_BATCH_SIZE", 64
            ),
            eval_split=eval_split,
        )

    def require_api_key(self) -> str:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Copy .env.example to .env, add your "
                "key, and run the script again. Do not paste the key into source code."
            )
        return self.openai_api_key


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _non_negative_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return value
