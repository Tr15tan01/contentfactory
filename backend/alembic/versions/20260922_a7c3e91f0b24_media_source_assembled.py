"""media source: assembled

Revision ID: a7c3e91f0b24
Revises: 4ef6ad8d77ed
Create Date: 2026-09-22

Enums are VARCHAR + CHECK constraints, so adding a value means replacing the constraint.
"""

from alembic import op

revision = "a7c3e91f0b24"
down_revision = "4ef6ad8d77ed"
branch_labels = None
depends_on = None

OLD = "'upload', 'ai_generated', 'brand', 'import'"
NEW = "'upload', 'ai_generated', 'assembled', 'brand', 'import'"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_media_assets_media_source"), "media_assets", type_="check")
    op.create_check_constraint("media_source", "media_assets", f"source IN ({NEW})")


def downgrade() -> None:
    op.execute("UPDATE media_assets SET source = 'upload' WHERE source = 'assembled'")
    op.drop_constraint(op.f("ck_media_assets_media_source"), "media_assets", type_="check")
    op.create_check_constraint("media_source", "media_assets", f"source IN ({OLD})")
