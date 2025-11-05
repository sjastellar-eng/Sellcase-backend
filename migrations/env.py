import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# берем metadata из моделей — нужно для автогенерации
from app.models import Base
target_metadata = Base.metadata

# URL БД: из окружения, из app.config, либо SQLite как запасной
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    try:
        from app.config import DB_URL as CFG_DB_URL
        DB_URL = CFG_DB_URL
    except Exception:
        DB_URL = "sqlite:///./sellcase.db"

# Alembic config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# подставляем URL БД в конфиг Alembic
config.set_main_option("sqlalchemy.url", DB_URL)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Запуск в offline-режиме."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # batch-режим нужен SQLite для ALTER TABLE
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Запуск в online-режиме."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=(connection.dialect.name == "sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
