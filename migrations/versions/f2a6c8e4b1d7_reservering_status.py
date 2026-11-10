"""reserveringen: status (verwacht, gearriveerd, no_show)

Revision ID: f2a6c8e4b1d7
Revises: c4e7a1f9d2b6
Create Date: 2026-11-10 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a6c8e4b1d7'
down_revision: Union[str, Sequence[str], None] = 'c4e7a1f9d2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Of de gast er is: 'verwacht', 'gearriveerd' of 'no_show'. Bestaande reserveringen
    worden 'verwacht'.
    """
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('status', sa.Text(), nullable=False, server_default='verwacht'))


def downgrade() -> None:
    """Verwijdert alleen de nieuwe kolom."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('status')
