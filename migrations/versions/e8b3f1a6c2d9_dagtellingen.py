"""dagtellingen: aantallen per dag en bron, zonder namen, voor de cijfers na de bewaartermijn

Revision ID: e8b3f1a6c2d9
Revises: d7a2e4c9f3b1
Create Date: 2026-11-10 20:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b3f1a6c2d9'
down_revision: Union[str, Sequence[str], None] = 'd7a2e4c9f3b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Nieuwe tabel; de bestaande tabellen veranderen niet. Hij blijft leeg tot het nachtelijk
    opschonen de eerste oude reserveringen verwijdert.
    """
    op.create_table(
        'dagtellingen',
        sa.Column('datum', sa.Text(), nullable=False),
        sa.Column('bron', sa.Text(), nullable=False),
        sa.Column('reserveringen', sa.Integer(), server_default='0', nullable=False),
        sa.Column('gasten', sa.Integer(), server_default='0', nullable=False),
        sa.Column('no_shows', sa.Integer(), server_default='0', nullable=False),
        sa.PrimaryKeyConstraint('datum', 'bron'),
    )


def downgrade() -> None:
    """Verwijdert alleen de nieuwe tabel (en daarmee de bewaarde tellingen)."""
    op.drop_table('dagtellingen')
