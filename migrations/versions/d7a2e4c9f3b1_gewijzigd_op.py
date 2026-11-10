"""reserveringen: tijdstip waarop de gast de reservering wijzigde

Revision ID: d7a2e4c9f3b1
Revises: c6f3a9d1e8b5
Create Date: 2026-11-10 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a2e4c9f3b1'
down_revision: Union[str, Sequence[str], None] = 'c6f3a9d1e8b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Wanneer de gast de reservering voor het laatst zelf wijzigde; leeg zolang dat niet is gebeurd.
    Bestaande reserveringen blijven leeg.
    """
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('gewijzigd_op', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Verwijdert alleen de nieuwe kolom."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('gewijzigd_op')
