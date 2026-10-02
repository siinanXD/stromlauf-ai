from app.migrations import upgrade_statements


def test_upgrade_statements_add_each_column_idempotently():
    statements = upgrade_statements()
    assert statements[0] == (
        "ALTER TABLE machines ADD COLUMN IF NOT EXISTS line VARCHAR(120) NOT NULL DEFAULT ''"
    )
    alters = [s for s in statements if s.startswith("ALTER TABLE")]
    columns = [(s.split()[2], s.split()[8]) for s in alters]
    assert columns == [
        ("machines", "line"),
        ("documents", "attempts"),
        ("chunks", "tsv"),
    ]
    assert statements[len(alters) :] == [
        "CREATE INDEX IF NOT EXISTS ix_chunks_tsv ON chunks USING gin (tsv)"
    ]
