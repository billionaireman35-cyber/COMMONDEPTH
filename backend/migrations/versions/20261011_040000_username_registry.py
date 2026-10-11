"""Create global username registry and backfill existing Profiles."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261011_040000"
down_revision = "add_post_bookmarks"
branch_labels = None
depends_on = None


USERNAME_PATTERN = r"^[a-z][a-z0-9_]{1,29}$"


def upgrade() -> None:
    connection = op.get_bind()

    # Fail safely before changing schema if legacy data is incompatible.
    invalid = connection.execute(
        sa.text(
            """
            SELECT id, username
            FROM profiles
            WHERE username IS NULL
               OR username <> lower(trim(username))
               OR username !~ :pattern
            LIMIT 10
            """
        ),
        {"pattern": USERNAME_PATTERN},
    ).fetchall()

    if invalid:
        raise RuntimeError(
            "Username registry migration stopped: existing Profile "
            "usernames must already be normalized and valid. "
            f"Sample rows: {invalid!r}"
        )

    duplicates = connection.execute(
        sa.text(
            """
            SELECT lower(trim(username)) AS normalized_username,
                   count(*) AS total
            FROM profiles
            GROUP BY lower(trim(username))
            HAVING count(*) > 1
            LIMIT 10
            """
        )
    ).fetchall()

    if duplicates:
        raise RuntimeError(
            "Username registry migration stopped: normalized username "
            f"collisions exist. Sample rows: {duplicates!r}"
        )

    op.create_table(
        "username_registry",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="claimed",
            nullable=False,
        ),
        sa.Column("owner_type", sa.String(length=16), nullable=True),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # Space foreign key will be added with the Space model.
        sa.Column(
            "space_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "username ~ '^[a-z][a-z0-9_]{1,29}$'",
            name="ck_username_registry_username_format",
        ),
        sa.CheckConstraint(
            "status IN ('claimed', 'reserved')",
            name="ck_username_registry_status",
        ),
        sa.CheckConstraint(
            "("
            "status = 'claimed' "
            "AND expires_at IS NULL "
            "AND reserved_at IS NULL "
            "AND ("
            "  (owner_type = 'profile' AND profile_id IS NOT NULL "
            "   AND space_id IS NULL) "
            "  OR "
            "  (owner_type = 'space' AND profile_id IS NULL "
            "   AND space_id IS NOT NULL)"
            ")"
            ") OR ("
            "status = 'reserved' "
            "AND owner_type IS NULL "
            "AND profile_id IS NULL "
            "AND space_id IS NULL "
            "AND reserved_at IS NOT NULL "
            "AND expires_at IS NOT NULL "
            "AND expires_at > reserved_at"
            ")",
            name="ck_username_registry_state",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            name="fk_username_registry_profile_id_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_username_registry"),
        sa.UniqueConstraint(
            "username",
            name="uq_username_registry_username",
        ),
        sa.UniqueConstraint(
            "profile_id",
            name="uq_username_registry_profile",
        ),
        sa.UniqueConstraint(
            "space_id",
            name="uq_username_registry_space",
        ),
    )

    op.create_index(
        "ix_username_registry_status_expiry",
        "username_registry",
        ["status", "expires_at"],
    )

    # Preserve every existing Profile username exactly as stored.
    connection.execute(
        sa.text(
            """
            INSERT INTO username_registry (
                id,
                username,
                status,
                owner_type,
                profile_id,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                username,
                'claimed',
                'profile',
                id,
                now(),
                now()
            FROM profiles
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_username_registry_status_expiry",
        table_name="username_registry",
    )
    op.drop_table("username_registry")
