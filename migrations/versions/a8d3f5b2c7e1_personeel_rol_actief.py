"""personeel: rol en actief

Revision ID: a8d3f5b2c7e1
Revises: e5b9c1d3a7f2
Create Date: 2026-11-10 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d3f5b2c7e1'
down_revision: Union[str, Sequence[str], None] = 'e5b9c1d3a7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Twee kolommen erbij; geen gegevens gaan verloren. Alle bestaande accounts worden beheerder:
    tot nu toe kon alleen de eigenaar inloggen. Nieuwe accounts zijn standaard medewerker.
    """
    with op.batch_alter_table('personeel') as tabel:
        tabel.add_column(sa.Column('rol', sa.Text(), nullable=False, server_default='medewerker'))
        tabel.add_column(sa.Column('actief', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute("UPDATE personeel SET rol = 'beheerder'")


def downgrade() -> None:
    """Verwijdert alleen de twee nieuwe kolommen."""
    with op.batch_alter_table('personeel') as tabel:
        tabel.drop_column('actief')
        tabel.drop_column('rol')
