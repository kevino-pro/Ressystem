"""reserveringen: bron en ingevoerd_door

Revision ID: c4e7a1f9d2b6
Revises: a8d3f5b2c7e1
Create Date: 2026-11-10 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e7a1f9d2b6'
down_revision: Union[str, Sequence[str], None] = 'a8d3f5b2c7e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Waar een reservering vandaan komt (online, ai, telefoon, binnenloper) en welk account hem
    invoerde. Bestaande reserveringen worden 'online' zonder invoerder.
    """
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.add_column(sa.Column('bron', sa.Text(), nullable=False, server_default='online'))
        tabel.add_column(sa.Column('ingevoerd_door', sa.Text(), nullable=True))


def downgrade() -> None:
    """Verwijdert alleen de twee nieuwe kolommen."""
    with op.batch_alter_table('reserveringen') as tabel:
        tabel.drop_column('ingevoerd_door')
        tabel.drop_column('bron')
