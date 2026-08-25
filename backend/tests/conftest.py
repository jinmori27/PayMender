from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest


TEST_DB = Path(tempfile.gettempdir()) / f"paymender-tests-{uuid4().hex}.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "test_webhook_secret"
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["OPERATOR_API_TOKEN"] = "test_operator_token_32_bytes_long"


@pytest.fixture(scope="session", autouse=True)
def database_lifecycle():
    from app.database import Base, engine

    Base.metadata.create_all(engine)
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture()
def db():
    from app.database import SessionLocal
    from app.services import reset_demo
    from app.config import get_settings

    with SessionLocal() as session:
        reset_demo(session, get_settings())
        yield session
