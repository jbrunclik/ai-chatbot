"""
Add cost tracking table for message costs.

Stores cost information for each assistant message:
- message_id: Foreign key to messages table
- model: Model used (e.g., gemini-3-flash-preview)
- input_tokens: Number of input tokens
- output_tokens: Number of output tokens
- cost_usd: Total cost in USD
- created_at: Timestamp
"""

from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS message_costs (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (message_id) REFERENCES messages(id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        "DROP TABLE IF EXISTS message_costs"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_message_costs_message_id ON message_costs(message_id)",
        "DROP INDEX IF EXISTS idx_message_costs_message_id"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_message_costs_conversation_id ON message_costs(conversation_id)",
        "DROP INDEX IF EXISTS idx_message_costs_conversation_id"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_message_costs_user_id ON message_costs(user_id)",
        "DROP INDEX IF EXISTS idx_message_costs_user_id"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_message_costs_created_at ON message_costs(created_at)",
        "DROP INDEX IF EXISTS idx_message_costs_created_at"
    ),
]

