import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

TEST_DB_PATH = (Path(__file__).resolve().parent / "test_suite.db").resolve()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["BOOTSTRAP_ON_STARTUP"] = "false"

from app.db import Base, SessionLocal, engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.services.policy_seed import seed_policies  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db() -> Generator[None, None, None]:
    engine.dispose()
    try:
        Base.metadata.drop_all(bind=engine, checkfirst=True)
    except OperationalError:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_policies(session)
    yield


def override_get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_session] = override_get_session


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c
