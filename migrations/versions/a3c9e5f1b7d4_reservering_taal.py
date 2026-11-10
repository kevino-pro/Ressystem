"""reserveringen: taal van de gast

Revision ID: a3c9e5f1b7d4
Revises: f2a6c8e4b1d7
Create Date: 2026-11-10 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9e5f1b7d4'
down_revision: Union[str, Sequence[str], None] = 'f2a6c8e4b1d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    De taal waarin de gast reserveerde ('en', 'nl' of 'id'); daarin gaan de mails.
    Bestaande reserveringen zijn in het Nederlands gemaakt en worden 'nl'.
    """
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('taal', sa.Text(), nullable=False, server_default='nl'))


def downgrade() -> None:
    """Verwijdert alleen de nieuwe kolom."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('taal')
