"""reserveringen: tijdstip van de herinneringsmail

Revision ID: c6f3a9d1e8b5
Revises: b8e2d4f6a1c9
Create Date: 2026-11-10 21:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f3a9d1e8b5'
down_revision: Union[str, Sequence[str], None] = 'b8e2d4f6a1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Wanneer de herinneringsmail voor een reservering is verstuurd; leeg zolang dat niet is gebeurd.
    Bestaande reserveringen blijven leeg en kunnen dus nog een herinnering krijgen.
    """
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('herinnering_verstuurd', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Verwijdert alleen de nieuwe kolom."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('herinnering_verstuurd')
