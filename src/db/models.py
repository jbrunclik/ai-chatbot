import json
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from yoyo import get_backend, read_migrations

from src.config import Config
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Path to migrations directory
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


@dataclass
class User:
    id: str
    email: str
    name: str
    picture: str | None
    created_at: datetime


@dataclass
class Conversation:
    id: str
    user_id: str
    title: str
    model: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str  # Plain text message
    created_at: datetime
    files: list[dict[str, Any]] = field(default_factory=list)  # File attachments
    sources: list[dict[str, str]] | None = None  # Web sources for assistant messages
    generated_images: list[dict[str, str]] | None = None  # Generated image metadata


@dataclass
class AgentState:
    conversation_id: str
    state_json: str
    updated_at: datetime


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Config.DATABASE_PATH
        self._init_db()

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Run yoyo migrations to initialize/update the database schema."""
        logger.debug("Initializing database", extra={"db_path": str(self.db_path)})
        backend = get_backend(f"sqlite:///{self.db_path}")
        migrations = read_migrations(str(MIGRATIONS_DIR))
        with backend.lock():
            migrations_to_apply = backend.to_apply(migrations)
            if migrations_to_apply:
                logger.info(
                    "Applying database migrations", extra={"count": len(migrations_to_apply)}
                )
            backend.apply_migrations(migrations_to_apply)

    # User operations
    def get_or_create_user(self, email: str, name: str, picture: str | None = None) -> User:
        logger.debug("Getting or creating user", extra={"email": email})
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

            if row:
                logger.debug("User found", extra={"user_id": row["id"], "email": email})
                return User(
                    id=row["id"],
                    email=row["email"],
                    name=row["name"],
                    picture=row["picture"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )

            user_id = str(uuid.uuid4())
            now = datetime.now()
            conn.execute(
                "INSERT INTO users (id, email, name, picture, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, name, picture, now.isoformat()),
            )
            conn.commit()
            logger.info("User created", extra={"user_id": user_id, "email": email})

            return User(
                id=user_id,
                email=email,
                name=name,
                picture=picture,
                created_at=now,
            )

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

            if not row:
                return None

            return User(
                id=row["id"],
                email=row["email"],
                name=row["name"],
                picture=row["picture"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    # Conversation operations
    def create_conversation(
        self, user_id: str, title: str = "New Conversation", model: str | None = None
    ) -> Conversation:
        conv_id = str(uuid.uuid4())
        model = model or Config.DEFAULT_MODEL
        now = datetime.now()
        logger.debug(
            "Creating conversation",
            extra={"user_id": user_id, "conversation_id": conv_id, "model": model},
        )

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO conversations (id, user_id, title, model, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (conv_id, user_id, title, model, now.isoformat(), now.isoformat()),
            )
            conn.commit()

        logger.info("Conversation created", extra={"conversation_id": conv_id, "user_id": user_id})
        return Conversation(
            id=conv_id,
            user_id=user_id,
            title=title,
            model=model,
            created_at=now,
            updated_at=now,
        )

    def get_conversation(self, conv_id: str, user_id: str) -> Conversation | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id),
            ).fetchone()

            if not row:
                return None

            return Conversation(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                model=row["model"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def list_conversations(self, user_id: str) -> list[Conversation]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM conversations WHERE user_id = ?
                   ORDER BY updated_at DESC""",
                (user_id,),
            ).fetchall()

            return [
                Conversation(
                    id=row["id"],
                    user_id=row["user_id"],
                    title=row["title"],
                    model=row["model"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]

    def update_conversation(
        self, conv_id: str, user_id: str, title: str | None = None, model: str | None = None
    ) -> bool:
        updates: list[str] = ["updated_at = ?"]
        params: list[Any] = [datetime.now().isoformat()]

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if model is not None:
            updates.append("model = ?")
            params.append(model)

        params.extend([conv_id, user_id])

        with self._get_conn() as conn:
            cursor = conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self._get_conn() as conn:
            # Delete messages first
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            # Delete agent state
            conn.execute("DELETE FROM agent_states WHERE conversation_id = ?", (conv_id,))
            # Delete conversation
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # Message operations
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        files: list[dict[str, Any]] | None = None,
        sources: list[dict[str, str]] | None = None,
        generated_images: list[dict[str, str]] | None = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: The conversation ID
            role: "user" or "assistant"
            content: Plain text message
            files: Optional list of file attachments
            sources: Optional list of web sources (for assistant messages)
            generated_images: Optional list of generated image metadata (for assistant messages)

        Returns:
            The created Message
        """
        msg_id = str(uuid.uuid4())
        now = datetime.now()
        files = files or []
        files_json = json.dumps(files) if files else None
        sources_json = json.dumps(sources) if sources else None
        generated_images_json = json.dumps(generated_images) if generated_images else None
        logger.debug(
            "Adding message",
            extra={
                "conversation_id": conversation_id,
                "message_id": msg_id,
                "role": role,
                "content_length": len(content),
                "file_count": len(files),
                "has_sources": bool(sources),
                "has_generated_images": bool(generated_images),
            },
        )

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO messages (id, conversation_id, role, content, files, sources, generated_images, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    files_json,
                    sources_json,
                    generated_images_json,
                    now.isoformat(),
                ),
            )
            # Update conversation's updated_at
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now.isoformat(), conversation_id),
            )
            conn.commit()

        logger.debug(
            "Message added", extra={"message_id": msg_id, "conversation_id": conversation_id}
        )
        return Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
            files=files,
            sources=sources,
            generated_images=generated_images,
        )

    def get_messages(self, conversation_id: str) -> list[Message]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
                (conversation_id,),
            ).fetchall()

            return [
                Message(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    files=json.loads(row["files"]) if row["files"] else [],
                    sources=json.loads(row["sources"]) if row["sources"] else None,
                    generated_images=json.loads(row["generated_images"])
                    if row["generated_images"]
                    else None,
                )
                for row in rows
            ]

    def get_message_by_id(self, message_id: str) -> Message | None:
        """Get a single message by its ID."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()

            if not row:
                return None

            return Message(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                created_at=datetime.fromisoformat(row["created_at"]),
                files=json.loads(row["files"]) if row["files"] else [],
                sources=json.loads(row["sources"]) if row["sources"] else None,
                generated_images=json.loads(row["generated_images"])
                if row["generated_images"]
                else None,
            )

    # Agent state operations
    def save_agent_state(self, conversation_id: str, state: dict[str, Any]) -> None:
        state_json = json.dumps(state)
        state_size = len(state_json)
        now = datetime.now().isoformat()
        logger.debug(
            "Saving agent state",
            extra={"conversation_id": conversation_id, "state_size": state_size},
        )

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO agent_states (conversation_id, state_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(conversation_id) DO UPDATE SET
                   state_json = excluded.state_json,
                   updated_at = excluded.updated_at""",
                (conversation_id, state_json, now),
            )
            conn.commit()
        logger.debug("Agent state saved", extra={"conversation_id": conversation_id})

    def get_agent_state(self, conversation_id: str) -> dict[str, Any] | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM agent_states WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()

            if not row:
                return None

            return json.loads(row["state_json"])  # type: ignore[no-any-return]


# Global database instance
db = Database()
