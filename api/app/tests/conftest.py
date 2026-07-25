from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token
from app.config import settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    # In-memory SQLite stands in for Postgres in these fast unit tests. It is
    # wired through the same SQLAlchemy models/metadata, so schema drift would
    # still be caught; only Postgres-specific SQL would slip through, and the
    # CRUD routers used here don't touch any.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def unauthenticated_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client(unauthenticated_client: TestClient) -> TestClient:
    # A real token from the real token-creation path (not a dependency-override bypass), so
    # every existing test exercises actual auth instead of skipping it. Tests that specifically
    # need to exercise "no token"/"bad token" use `unauthenticated_client` directly.
    token = create_access_token(settings.admin_username)
    unauthenticated_client.headers["Authorization"] = f"Bearer {token}"
    return unauthenticated_client
