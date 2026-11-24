"""tafels_buiten_gebruik: per dag welke tafels niet gebruikt kunnen worden

Revision ID: b4f7d2c9a1e6
Revises: e8b3f1a6c2d9
Create Date: 2026-11-24 14:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f7d2c9a1e6'
down_revision: Union[str, Sequence[str], None] = 'e8b3f1a6c2d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Nieuwe tabel; de bestaande tabellen veranderen niet. Hij blijft leeg tot een beheerder
    een tafel buiten gebruik zet.
    """
    op.create_table(
        'tafels_buiten_gebruik',
        sa.Column('datum', sa.Text(), nullable=False),
        sa.Column('tafel', sa.Text(), nullable=False),
        sa.Column('door', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('datum', 'tafel'),
    )


def downgrade() -> None:
    """Verwijdert alleen de nieuwe tabel (en daarmee de tafels buiten gebruik)."""
    op.drop_table('tafels_buiten_gebruik')
