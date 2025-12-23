from yoyo import step

steps = [
    step(
        "ALTER TABLE message_costs ADD COLUMN image_generation_cost_usd REAL DEFAULT 0.0",
        "ALTER TABLE message_costs DROP COLUMN image_generation_cost_usd"
    ),
]

