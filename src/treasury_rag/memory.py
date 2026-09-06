from __future__ import annotations

import sqlite3
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore:
    """Persistent conversation, message, and document-association store."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        max_sessions: int = 100,
        max_messages: int = 12,
    ) -> None:
        self.max_sessions = max_sessions
        self.max_messages = max_messages
        self._lock = threading.RLock()
        if db_path and str(db_path) != ":memory:":
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            database = str(path)
        else:
            database = ":memory:"
        self._connection = sqlite3.connect(database, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute("PRAGMA foreign_keys = ON")
            if database != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS conversation_documents (
                    conversation_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    attached_at TEXT NOT NULL,
                    PRIMARY KEY(conversation_id, document_id),
                    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, message_id);
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    memory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_conversation_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_document_access (
                    conversation_id TEXT PRIMARY KEY REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                    document_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS hidden_documents (document_id TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS app_flags (name TEXT PRIMARY KEY);
                """
            )

            columns = {row["name"] for row in self._connection.execute("PRAGMA table_info(messages)")}
            if "sources_json" not in columns:
                self._connection.execute("ALTER TABLE messages ADD COLUMN sources_json TEXT NOT NULL DEFAULT '[]'")

    def hidden_documents(self):
        with self._lock:
            return {row[0] for row in self._connection.execute("SELECT document_id FROM hidden_documents")}

    def remove_document(self, document_id):
        with self._lock, self._connection:
            self._connection.execute("INSERT OR IGNORE INTO hidden_documents VALUES (?)", (document_id,))
            self._connection.execute("DELETE FROM conversation_documents WHERE document_id=?", (document_id,))
            self._connection.execute("DELETE FROM pending_document_access WHERE document_id=?", (document_id,))

    def restore_document(self, document_id):
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM hidden_documents WHERE document_id=?", (document_id,))

    def first_initialization(self):
        with self._lock, self._connection:
            cursor = self._connection.execute("INSERT OR IGNORE INTO app_flags VALUES ('initialized')")
            return cursor.rowcount > 0

    def pending_access(self, conversation_id: str):
        import time
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM pending_document_access WHERE created_at < ?", (time.time() - 600,))
            row = self._connection.execute("SELECT * FROM pending_document_access WHERE conversation_id=?", (conversation_id,)).fetchone()
            return dict(row) if row else None

    def propose_access(self, conversation_id: str, document_id: str, question: str):
        import time
        self.ensure(conversation_id)
        with self._lock, self._connection:
            self._connection.execute("INSERT OR REPLACE INTO pending_document_access VALUES (?, ?, ?, ?)",
                                     (conversation_id, document_id, question, time.time()))

    def resolve_access(self, conversation_id: str, accept: bool):
        with self._lock, self._connection:
            pending = self.pending_access(conversation_id)
            if pending and accept:
                self._connection.execute("INSERT OR IGNORE INTO conversation_documents VALUES (?, ?, ?)",
                                         (conversation_id, pending['document_id'], _now()))
            self._connection.execute("DELETE FROM pending_document_access WHERE conversation_id=?", (conversation_id,))
            return pending

    def create(
        self, title: str = "New conversation", conversation_id: str | None = None
    ) -> dict[str, object]:
        conversation_id = conversation_id or uuid.uuid4().hex
        now = _now()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO conversations(conversation_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (conversation_id, title.strip() or "New conversation", now, now),
            )
        return self.get_conversation(conversation_id)

    def ensure(self, conversation_id: str, title: str = "New conversation") -> bool:
        with self._lock:
            exists = self._connection.execute(
                "SELECT 1 FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if exists:
                return False
            self.create(title=title, conversation_id=conversation_id)
            return True

    def list_conversations(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                       COUNT(DISTINCT m.message_id) AS message_count,
                       COUNT(DISTINCT cd.document_id) AS document_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.conversation_id
                LEFT JOIN conversation_documents cd
                    ON cd.conversation_id = c.conversation_id
                GROUP BY c.conversation_id
                ORDER BY c.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, object]:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT conversation_id, title, created_at, updated_at
                FROM conversations WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown conversation: {conversation_id}")
        result = dict(row)
        result["messages"] = self.history(conversation_id)
        result["document_ids"] = self.document_ids(conversation_id)
        return result

    def history(self, conversation_id: str) -> list[dict]:
        """Full display history; model context remains bounded via get()."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT message_id, role, content, sources_json FROM messages WHERE conversation_id = ? ORDER BY message_id",
                (conversation_id,),
            ).fetchall()
        return [dict(message_id=row["message_id"], role=row["role"],
                     content=row["content"], sources=json.loads(row["sources_json"])) for row in rows]

    def get(self, conversation_id: str) -> list[dict[str, str]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT role, content FROM (
                    SELECT message_id, role, content
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY message_id DESC
                    LIMIT ?
                ) ORDER BY message_id ASC
                """,
                (conversation_id, self.max_messages),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def get_all(self, conversation_id: str, *, limit: int = 80) -> list[dict[str, str]]:
        """Return a bounded chronological transcript for durable chat summaries."""
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT role, content FROM (
                    SELECT message_id, role, content
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY message_id DESC
                    LIMIT ?
                ) ORDER BY message_id ASC
                """,
                (conversation_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def user_turn_count(self, conversation_id: str) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM messages WHERE conversation_id = ? AND role = 'user'",
                (conversation_id,),
            ).fetchone()
        return int(row["total"] if row else 0)

    def append_turn(self, conversation_id: str, user: str, assistant: str,
                    sources=None, assistant_messages=None) -> None:
        self.ensure(conversation_id)
        now = _now()
        with self._lock, self._connection:
            self._connection.executemany(
                """
                INSERT INTO messages(conversation_id, role, content, created_at, sources_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (conversation_id, "user", user, now, "[]"),
                ] + [
                    (conversation_id, "assistant", item["content"], now,
                     json.dumps(item.get("sources", []), ensure_ascii=False))
                    for item in (assistant_messages or [{"content": assistant, "sources": sources or []}])
                ],
            )
            row = self._connection.execute(
                "SELECT title FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if row and row["title"] == "New conversation":
                title = " ".join(user.split())[:60] or "New conversation"
                self._connection.execute(
                    "UPDATE conversations SET title = ? WHERE conversation_id = ?",
                    (title, conversation_id),
                )
            self._connection.execute(
                "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                (now, conversation_id),
            )

    def clear(self, conversation_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )

    def delete(self, conversation_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,)
            )

    def attach_document(self, conversation_id: str, document_id: str) -> None:
        self.ensure(conversation_id)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO conversation_documents(
                    conversation_id, document_id, attached_at
                ) VALUES (?, ?, ?)
                """,
                (conversation_id, document_id, _now()),
            )

    def detach_document(self, conversation_id: str, document_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                DELETE FROM conversation_documents
                WHERE conversation_id = ? AND document_id = ?
                """,
                (conversation_id, document_id),
            )

    def document_ids(self, conversation_id: str) -> list[str]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT document_id FROM conversation_documents
                WHERE conversation_id = ? ORDER BY attached_at
                """,
                (conversation_id,),
            ).fetchall()
        return [str(row["document_id"]) for row in rows]

    def remember(
        self,
        *,
        memory_key: str,
        category: str,
        content: str,
        source_conversation_id: str | None = None,
    ) -> dict[str, object]:
        now = _now()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO long_term_memories(
                    memory_key, category, content, source_conversation_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_key) DO UPDATE SET
                    content = excluded.content,
                    source_conversation_id = excluded.source_conversation_id,
                    updated_at = excluded.updated_at
                """,
                (
                    memory_key,
                    category,
                    content.strip(),
                    source_conversation_id,
                    now,
                    now,
                ),
            )
            row = self._connection.execute(
                "SELECT * FROM long_term_memories WHERE memory_key = ?",
                (memory_key,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Long-term memory could not be stored.")
        return dict(row)

    def list_memories(self, limit: int = 30) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT memory_id, memory_key, category, content,
                       source_conversation_id, created_at, updated_at
                FROM long_term_memories
                ORDER BY updated_at DESC, memory_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def memory_by_key(self, memory_key: str) -> dict[str, object] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM long_term_memories WHERE memory_key = ?", (memory_key,)
            ).fetchone()
        return dict(row) if row else None

    def forget_memory(self, memory_id: int) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "DELETE FROM long_term_memories WHERE memory_id = ?", (memory_id,)
            )
        return cursor.rowcount > 0

    def edit_memory(self, memory_id: int, content: str) -> bool:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE long_term_memories SET content = ?, updated_at = ? WHERE memory_id = ?",
                (content.strip(), _now(), memory_id),
            )
        return cursor.rowcount > 0

    def clear_long_term_memories(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM long_term_memories")
