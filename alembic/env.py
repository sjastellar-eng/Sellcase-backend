import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic Config object (reads alembic.ini)
config = context.config

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---- IMPORT YOUR SQLALCHEMY BASE / MODELS ----
# Важно: чтобы Alembic видел модели и сравнивал метадату
from app.db import Base  # noqa: E402

# Импортни models, чтобы таблицы зарегистрировались в metadata
# (если у тебя все модели в app/models.py — этого достаточно)
import app.models  # noqa: F401, E402

target_metadata = Base.metadata


def _normalize_database_url(url: str) -> str:
    """
    Render часто дает URL вида postgres://...
    SQLAlchemy ожидает postgresql://...
    Также гарантируем SSL (Render Postgres часто требует SSL/TLS).
    """
    if not url:
        return url

    url = url.strip()

    # 1) postgres:// -> postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # 2) Если драйвер не указан — ставим psycopg2 по умолчанию
    # postgresql://user:pass@host/db -> postgresql+psycopg2://user:pass@host/db
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]

    # 3) Добавляем sslmode=require, если его нет
    if "sslmode=" not in url:
        if "?" in url:
            url = url + "&sslmode=require"
        else:
            url = url + "?sslmode=require"

    return url


def get_url() -> str:
    # берем из окружения (Render / Codespaces / локально)
    url = os.getenv("DATABASE_URL", "")
    url = _normalize_database_url(url)

    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it in your environment before running Alembic."
        )

    # IMPORTANT: Alembic configparser использует % для интерполяций.
    # Чтобы не словить баги, экранируем % -> %%
    url = url.replace("%", "%%")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()

    # Подставляем URL прямо в конфиг Alembic (без %(...)% в alembic.ini)
    config.set_main_option("sqlalchemy.url", url)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
