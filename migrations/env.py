import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1) читаем URL из .env/окружения или из app.config
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    # попытка импортнуть из приложения (если есть app/config.py)
    try:
        from app.config import DB_URL as CFG_DB_URL
        DB_URL = CFG_DB_URL
    except Exception:
        DB_URL = "sqlite:///./sellcase.db"  # запасной вариант

config = context.config
fileConfig(config.config_file_name)

# 2) подставляем url в конфиг alembic
config.set_main_option("sqlalchemy.url", DB_URL)

# остальной стандартный код env.py не трогаем
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Подключаем модуль app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from db import Base
from models import *

# URL БД из .env
DATABASE_URL = os.getenv("DATABASE_URL")

# Alembic config
config = context.config
fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
