"""personeel: taal van het account

Revision ID: b8e2d4f6a1c9
Revises: a3c9e5f1b7d4
Create Date: 2026-11-10 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e2d4f6a1c9'
down_revision: Union[str, Sequence[str], None] = 'a3c9e5f1b7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    De taal waarin een medewerker de personeelspagina's ziet ('en', 'nl' of 'id').
    Bestaande accounts gebruikten de site in het Nederlands en worden 'nl'.
    """
    with op.batch_alter_table('personeel') as tabel:
        tabel.add_column(sa.Column('taal', sa.Text(), nullable=False, server_default='nl'))


def downgrade() -> None:
    """Verwijdert alleen de nieuwe kolom."""
    with op.batch_alter_table('personeel') as tabel:
        tabel.drop_column('taal')
