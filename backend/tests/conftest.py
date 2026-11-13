import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import build_engine


@pytest.fixture(scope="module")
def database():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL checks")
    if not make_url(url).database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a dedicated database ending in _test")
    settings = Settings(database_url=url)
    engine = build_engine(settings)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(config, "head")
        yield engine, settings
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        engine.dispose()
