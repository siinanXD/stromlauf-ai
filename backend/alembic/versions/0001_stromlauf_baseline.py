"""Stromlauf-Baseline: alle Tabellen des Stands vom 2026-09-27 (MB-0).

Erzeugt offline aus `app.models` (alembic.operations.ops + render_python_code), nicht per Autogenerate
gegen eine Datenbank. Zwei Faelle:

- leere Datenbank: `CREATE EXTENSION vector`, alle Tabellen und Indizes wie im Modell;
- bestehende Datenbank aus der `create_all`-Zeit (Tabelle `knowledge_sources` vorhanden): nur die
  additiven Spalten/Indizes aus `app.migrations` (idempotent), danach ist der Stand gleich.

Downgrade entfernt alle Tabellen in umgekehrter Abhaengigkeitsreihenfolge; die Extension bleibt.

Die Leitstand-Tabellen (customers, orders, order_lines, stock) gehoerten bis Revision 0005 dazu; seit ihrem
Wegfall legt die Baseline sie nicht mehr an, 0005 raeumt sie auf Datenbanken von damals ab.

Revision ID: 0001_stromlauf_baseline
Revises:
Create Date: 2026-09-27
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op
from app.migrations import upgrade_statements

revision = "0001_stromlauf_baseline"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ['articles', 'conversations', 'halls', 'knowledge_sources', 'plant_settings', 'documents', 'machines', 'site_flows', 'cabinet_images', 'chunks', 'fault_entries', 'hall_flows', 'machine_layouts', 'machine_specs', 'materials', 'routing_steps', 'tag_occurrences', 'bom_lines', 'cabinet_hotspots', 'diagnosis_sessions', 'layout_parts']


def _schema_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table("knowledge_sources")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if _schema_exists():
        for statement in upgrade_statements():
            op.execute(statement)
        return
    op.create_table('articles',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('unit_name', sa.String(length=40), nullable=False),
    sa.Column('units_per_pallet', sa.Integer(), nullable=False),
    sa.Column('sheets_per_unit', sa.Integer(), nullable=False),
    sa.Column('sheet_w_mm', sa.Float(), nullable=False),
    sa.Column('sheet_l_mm', sa.Float(), nullable=False),
    sa.Column('plies', sa.Integer(), nullable=False),
    sa.Column('gsm', sa.Float(), nullable=False),
    sa.Column('waste_pct', sa.Float(), nullable=False),
    sa.Column('line', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('price', sa.Float(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('conversations',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('source_ids', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('halls',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('kind', sa.String(length=24), server_default='generic', nullable=False),
    sa.Column('site_x', sa.Float(), server_default='0', nullable=False),
    sa.Column('site_y', sa.Float(), server_default='0', nullable=False),
    sa.Column('site_w', sa.Float(), server_default='0', nullable=False),
    sa.Column('site_h', sa.Float(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('knowledge_sources',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('plant_settings',
    sa.Column('key', sa.String(length=60), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('documents',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('source_id', sa.String(length=32), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('storage_path', sa.String(length=1000), nullable=False),
    sa.Column('doc_type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', sa.String(length=200), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('vision_enrichment', sa.Boolean(), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_source_id'), 'documents', ['source_id'], unique=False)
    op.create_table('machines',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('hall_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('machine_type', sa.String(length=24), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('source_id', sa.String(length=32), nullable=True),
    sa.Column('image_path', sa.String(length=1000), nullable=True),
    sa.Column('pos_x', sa.Float(), nullable=False),
    sa.Column('pos_y', sa.Float(), nullable=False),
    sa.Column('order_index', sa.Integer(), nullable=False),
    sa.Column('line', sa.String(length=120), server_default='', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['hall_id'], ['halls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_id'], ['knowledge_sources.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machines_hall_id'), 'machines', ['hall_id'], unique=False)
    op.create_index(op.f('ix_machines_source_id'), 'machines', ['source_id'], unique=False)
    op.create_table('site_flows',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('from_hall_id', sa.String(length=32), nullable=False),
    sa.Column('to_hall_id', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.ForeignKeyConstraint(['from_hall_id'], ['halls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_hall_id'], ['halls.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_site_flows_from_hall_id'), 'site_flows', ['from_hall_id'], unique=False)
    op.create_index(op.f('ix_site_flows_to_hall_id'), 'site_flows', ['to_hall_id'], unique=False)
    op.create_table('cabinet_images',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('image_path', sa.String(length=1000), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cabinet_images_machine_id'), 'cabinet_images', ['machine_id'], unique=False)
    op.create_table('chunks',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('document_id', sa.String(length=32), nullable=False),
    sa.Column('source_id', sa.String(length=32), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('section', sa.String(length=500), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('meta', sa.JSON(), nullable=False),
    sa.Column('embedding', Vector(1024), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('german', content)", persisted=True), nullable=True),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunks_doc_page', 'chunks', ['document_id', 'page'], unique=False)
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)
    op.create_index('ix_chunks_embedding_hnsw', 'chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_chunks_source_id'), 'chunks', ['source_id'], unique=False)
    op.create_index('ix_chunks_tsv', 'chunks', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('fault_entries',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('symptom', sa.Text(), nullable=False),
    sa.Column('cause', sa.Text(), nullable=False),
    sa.Column('fix', sa.Text(), nullable=False),
    sa.Column('doc_ref', sa.String(length=300), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fault_entries_machine_id'), 'fault_entries', ['machine_id'], unique=False)
    op.create_table('hall_flows',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('hall_id', sa.String(length=32), nullable=False),
    sa.Column('from_machine_id', sa.String(length=32), nullable=False),
    sa.Column('to_machine_id', sa.String(length=32), nullable=False),
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.ForeignKeyConstraint(['from_machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['hall_id'], ['halls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hall_flows_hall_id'), 'hall_flows', ['hall_id'], unique=False)
    op.create_table('machine_layouts',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=False),
    sa.Column('width_mm', sa.Float(), nullable=False),
    sa.Column('depth_mm', sa.Float(), nullable=False),
    sa.Column('image_path', sa.String(length=1000), nullable=True),
    sa.Column('document_id', sa.String(length=32), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('scale_note', sa.String(length=60), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machine_layouts_machine_id'), 'machine_layouts', ['machine_id'], unique=True)
    op.create_table('machine_specs',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('unit', sa.String(length=60), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_machine_specs_machine_id'), 'machine_specs', ['machine_id'], unique=False)
    op.create_table('materials',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('price_source', sa.Text(), nullable=False),
    sa.Column('made_on_machine_id', sa.String(length=32), nullable=True),
    sa.Column('made_rate_per_h', sa.Float(), nullable=True),
    sa.Column('made_basis', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['made_on_machine_id'], ['machines.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('routing_steps',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('article_id', sa.String(length=32), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=True),
    sa.Column('rate', sa.Float(), nullable=False),
    sa.Column('rate_unit', sa.String(length=12), nullable=False),
    sa.Column('setup_min', sa.Float(), nullable=False),
    sa.Column('coupled', sa.Boolean(), nullable=False),
    sa.Column('basis', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_routing_steps_article_id'), 'routing_steps', ['article_id'], unique=False)
    op.create_table('tag_occurrences',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('document_id', sa.String(length=32), nullable=False),
    sa.Column('source_id', sa.String(length=32), nullable=False),
    sa.Column('tag', sa.String(length=120), nullable=False),
    sa.Column('tag_type', sa.String(length=16), nullable=False),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(length=500), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tag_occurrences_document_id'), 'tag_occurrences', ['document_id'], unique=False)
    op.create_index(op.f('ix_tag_occurrences_source_id'), 'tag_occurrences', ['source_id'], unique=False)
    op.create_index(op.f('ix_tag_occurrences_tag'), 'tag_occurrences', ['tag'], unique=False)
    op.create_index(op.f('ix_tag_occurrences_tag_type'), 'tag_occurrences', ['tag_type'], unique=False)
    op.create_table('bom_lines',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('article_id', sa.String(length=32), nullable=True),
    sa.Column('parent_material_id', sa.String(length=32), nullable=True),
    sa.Column('material_id', sa.String(length=32), nullable=False),
    sa.Column('qty', sa.Float(), nullable=False),
    sa.Column('per', sa.String(length=10), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_material_id'], ['materials.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bom_lines_article_id'), 'bom_lines', ['article_id'], unique=False)
    op.create_index(op.f('ix_bom_lines_parent_material_id'), 'bom_lines', ['parent_material_id'], unique=False)
    op.create_table('cabinet_hotspots',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('cabinet_id', sa.String(length=32), nullable=False),
    sa.Column('tag', sa.String(length=120), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=60), nullable=False),
    sa.Column('x', sa.Float(), nullable=False),
    sa.Column('y', sa.Float(), nullable=False),
    sa.Column('w', sa.Float(), nullable=False),
    sa.Column('h', sa.Float(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('origin', sa.String(length=16), nullable=False),
    sa.Column('confirmed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['cabinet_id'], ['cabinet_images.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cabinet_hotspots_cabinet_id'), 'cabinet_hotspots', ['cabinet_id'], unique=False)
    op.create_table('diagnosis_sessions',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('machine_id', sa.String(length=32), nullable=False),
    sa.Column('fault_id', sa.String(length=32), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('steps', sa.JSON(), nullable=False),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('finding', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['fault_id'], ['fault_entries.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['machine_id'], ['machines.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_diagnosis_sessions_fault_id'), 'diagnosis_sessions', ['fault_id'], unique=False)
    op.create_index(op.f('ix_diagnosis_sessions_machine_id'), 'diagnosis_sessions', ['machine_id'], unique=False)
    op.create_table('layout_parts',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('layout_id', sa.String(length=32), nullable=False),
    sa.Column('tag', sa.String(length=120), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('shape', sa.String(length=10), nullable=False),
    sa.Column('x_mm', sa.Float(), nullable=False),
    sa.Column('y_mm', sa.Float(), nullable=False),
    sa.Column('w_mm', sa.Float(), nullable=False),
    sa.Column('h_mm', sa.Float(), nullable=False),
    sa.Column('rotation_deg', sa.Float(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('origin', sa.String(length=16), nullable=False),
    sa.Column('confirmed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['layout_id'], ['machine_layouts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_layout_parts_layout_id'), 'layout_parts', ['layout_id'], unique=False)


def downgrade() -> None:
    for name in reversed(TABLES):
        op.drop_table(name)
