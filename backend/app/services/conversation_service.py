import sqlite3
from pathlib import Path


class ConversationService:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path
        )

        connection.row_factory = sqlite3.Row

        return connection

    def _initialize_database(self) -> None:
        with self._get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id)
                        REFERENCES conversations(id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.commit()

    def create_conversation(
        self,
        title: str = "New Chat",
    ) -> int:
        with self._get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversations (title)
                VALUES (?)
                """,
                (title,),
            )

            connection.commit()

            return int(cursor.lastrowid)

    def conversation_exists(
        self,
        conversation_id: int,
    ) -> bool:
        with self._get_connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()

        return row is not None

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
    ) -> None:
        with self._get_connection() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    conversation_id,
                    role,
                    content
                )
                VALUES (?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    content,
                ),
            )

            connection.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (conversation_id,),
            )

            connection.commit()

    def get_messages(
        self,
        conversation_id: int,
    ) -> list[dict[str, str]]:
        with self._get_connection() as connection:
            rows = connection.execute(
                """
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()

        return [
            {
                "role": row["role"],
                "content": row["content"],
            }
            for row in rows
        ]

    def list_conversations(
        self,
    ) -> list[dict[str, str | int]]:
        with self._get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    title,
                    created_at,
                    updated_at
                FROM conversations
                ORDER BY updated_at DESC
                """
            ).fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]