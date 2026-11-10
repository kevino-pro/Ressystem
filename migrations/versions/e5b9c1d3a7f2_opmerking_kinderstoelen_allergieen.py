"""opmerking, kinderstoelen en allergieen bij een reservering

Revision ID: e5b9c1d3a7f2
Revises: c3f1a7d2e9b4
Create Date: 2026-11-10 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b9c1d3a7f2'
down_revision: Union[str, Sequence[str], None] = 'c3f1a7d2e9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drie nieuwe kolommen; bestaande reserveringen krijgen 0 kinderstoelen en geen opmerking of allergie."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('opmerking', sa.Text(), nullable=True))
        tabel.add_column(sa.Column('kinderstoelen', sa.Integer(), nullable=False, server_default='0'))
        tabel.add_column(sa.Column('allergieen', sa.Text(), nullable=True))


def downgrade() -> None:
    """Verwijdert de drie kolommen weer (en daarmee wat erin stond)."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('allergieen')
        tabel.drop_column('kinderstoelen')
        tabel.drop_column('opmerking')
