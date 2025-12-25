"""
Add indexes for conversation and message queries.

This migration adds indexes to optimize frequently used queries:
- list_conversations(): Filter by user_id, order by updated_at DESC
- get_messages(): Filter by conversation_id, order by created_at
"""

from yoyo import step

steps = [
    # Conversations indexes
    step(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)",
        "DROP INDEX IF EXISTS idx_conversations_user_id",
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user_id_updated_at ON conversations(user_id, updated_at DESC)",
        "DROP INDEX IF EXISTS idx_conversations_user_id_updated_at",
    ),
    # Messages indexes
    step(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)",
        "DROP INDEX IF EXISTS idx_messages_conversation_id",
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_created_at ON messages(conversation_id, created_at)",
        "DROP INDEX IF EXISTS idx_messages_conversation_id_created_at",
    ),
]
