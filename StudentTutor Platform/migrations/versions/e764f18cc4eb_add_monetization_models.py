"""add monetization models

Revision ID: e764f18cc4eb
Revises: a345f3fd31cd
Create Date: 2026-07-30 14:42:41.959879

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e764f18cc4eb'
down_revision = 'a345f3fd31cd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'payout' not in existing_tables:
        op.create_table('payout',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('tutor_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('requested_at', sa.DateTime(), nullable=True),
            sa.Column('paid_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['tutor_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    if 'subscription' not in existing_tables:
        op.create_table('subscription',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('plan', sa.String(length=20), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('started_at', sa.DateTime(), nullable=True),
            sa.Column('current_period_end', sa.DateTime(), nullable=True),
            sa.Column('gateway_subscription_id', sa.String(length=255), nullable=True),
            sa.Column('gateway_customer_id', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    if 'coupon' not in existing_tables:
        op.create_table('coupon',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('discount_type', sa.String(length=20), nullable=False),
            sa.Column('discount_value', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('max_uses', sa.Integer(), nullable=True),
            sa.Column('times_used', sa.Integer(), nullable=False),
            sa.Column('valid_from', sa.DateTime(), nullable=True),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('course_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['course_id'], ['course.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code')
        )

    if 'payment' not in existing_tables:
        op.create_table('payment',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('student_id', sa.Integer(), nullable=False),
            sa.Column('course_id', sa.Integer(), nullable=False),
            sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column('currency', sa.String(length=3), nullable=False),
            sa.Column('gateway', sa.String(length=20), nullable=False),
            sa.Column('gateway_payment_id', sa.String(length=255), nullable=True),
            sa.Column('gateway_checkout_id', sa.String(length=255), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('coupon_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['coupon_id'], ['coupon.id'], ),
            sa.ForeignKeyConstraint(['course_id'], ['course.id'], ),
            sa.ForeignKeyConstraint(['student_id'], ['user.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

    course_cols = [c['name'] for c in inspector.get_columns('course')]
    with op.batch_alter_table('course', schema=None) as batch_op:
        if 'price' not in course_cols:
            batch_op.add_column(sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'))
        if 'currency' not in course_cols:
            batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=False, server_default='usd'))

    enrollment_cols = [c['name'] for c in inspector.get_columns('enrollment')]
    with op.batch_alter_table('enrollment', schema=None) as batch_op:
        if 'payment_id' not in enrollment_cols:
            batch_op.add_column(sa.Column('payment_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_enrollment_payment', 'payment', ['payment_id'], ['id'])


def downgrade():
    with op.batch_alter_table('enrollment', schema=None) as batch_op:
        batch_op.drop_constraint('fk_enrollment_payment', type_='foreignkey')
        batch_op.drop_column('payment_id')

    with op.batch_alter_table('course', schema=None) as batch_op:
        batch_op.drop_column('currency')
        batch_op.drop_column('price')

    op.drop_table('payment')
    op.drop_table('coupon')
    op.drop_table('subscription')
    op.drop_table('payout')
