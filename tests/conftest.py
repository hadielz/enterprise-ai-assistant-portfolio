"""
Shared pytest fixtures.

Architecture Notes
------------------
Purpose:
    Run API and repository tests against a dedicated PostgreSQL
    database rather than the normal development database.

Isolation strategy:
    1. Create the relational schema once for the test session.
    2. Open one database connection for each test.
    3. Begin an outer transaction.
    4. Bind the SQLAlchemy Session to that connection.
    5. Allow application code to call session.commit().
    6. Roll back the outer transaction after the test.

FastAPI:
    get_db_session is overridden so API requests and direct repository
    calls use the same isolated SQLAlchemy Session.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from backend.app.main import app
from app.core.config import settings
from app.database.base import Base
from app.database.session import get_db_session
from app.security.rate_limit import rate_limiter


@pytest.fixture(autouse=True)
def reset_process_local_rate_limiter():
    """Keep the R4 process-local limiter isolated between tests."""

    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """
    Create the test engine and initialize the schema once.
    """

    engine = create_engine(
        settings.test_database_url,
        pool_pre_ping=True,
    )

    # Importing models ensures every table is registered in metadata.
    from app.database import models  # noqa: F401

    # R3 adds a pgvector-backed production RAG option. The dedicated test
    # database image includes the extension so Base.metadata can create the
    # vector column even when tests use controlled retrieval doubles.
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_connection(
    test_engine: Engine,
) -> Generator[Connection, None, None]:
    """
    Open one connection and outer transaction per test.
    """

    connection = test_engine.connect()
    transaction = connection.begin()

    yield connection

    if transaction.is_active:
        transaction.rollback()

    connection.close()


@pytest.fixture
def db_session(
    db_connection: Connection,
) -> Generator[Session, None, None]:
    """
    Provide a Session whose commits remain inside the test transaction.

    create_savepoint lets repository and API code call commit() without
    committing the fixture's outer transaction.
    """

    session = Session(
        bind=db_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    session.close()


@pytest.fixture
def client(
    db_session: Session,
) -> Generator[TestClient, None, None]:
    """
    Create a FastAPI client using the isolated database session.
    """

    def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = (
        override_get_db_session
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()