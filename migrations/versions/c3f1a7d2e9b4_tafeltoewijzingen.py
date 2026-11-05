"""tafeltoewijzingen

Revision ID: c3f1a7d2e9b4
Revises: ba7cbc14b3a2
Create Date: 2026-11-05 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f1a7d2e9b4'
down_revision: Union[str, Sequence[str], None] = 'ba7cbc14b3a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Nieuwe tabel; bestaande tabellen en gegevens blijven ongemoeid."""
    op.create_table('tafeltoewijzingen',
    sa.Column('reservering_id', sa.Text(), nullable=False),
    sa.Column('tafel', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['reservering_id'], ['reserveringen.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('reservering_id', 'tafel')
    )


def downgrade() -> None:
    """Verwijdert alleen de nieuwe tabel (en daarmee de tafeltoewijzingen)."""
    op.drop_table('tafeltoewijzingen')
