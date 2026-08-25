import unicodedata
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token
from app.database import Base, get_db
from app.main import app
from app.models.user import User


def _strip_diacritics(value: str | None) -> str | None:
    if value is None:
        return None
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


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

    # SQLite has no unaccent() — registers f_unaccent as a plain Python function so
    # routers/recipes.py's diacritic-insensitive title search (migration 0036) works the same way
    # here as it does against the real Postgres f_unaccent wrapper.
    @event.listens_for(engine, "connect")
    def _register_f_unaccent(dbapi_connection, _connection_record) -> None:
        dbapi_connection.create_function("f_unaccent", 1, _strip_diacritics)

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
def admin_user(db_session: Session) -> User:
    # Super admin, not just admin — `client` (built from this fixture) is used broadly across
    # existing tests for every admin-gated router, including Settings, which now needs the
    # stricter tier. `plain_admin_user`/`admin_client` below cover the "admin but not super admin"
    # case specifically for testing that distinction.
    user = User(
        email="admin@example.com",
        password_hash="x",
        is_admin=True,
        is_super_admin=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def plain_admin_user(db_session: Session) -> User:
    user = User(
        email="plainadmin@example.com",
        password_hash="x",
        is_admin=True,
        is_super_admin=False,
        is_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def regular_user(db_session: Session) -> User:
    user = User(email="regular@example.com", password_hash="x", is_admin=False, is_verified=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def client(unauthenticated_client: TestClient, admin_user: User) -> Generator[TestClient, None, None]:
    # A real token from the real token-creation path (not a dependency-override bypass), so
    # every existing test exercises actual auth instead of skipping it. Tests that specifically
    # need to exercise "no token"/"bad token" use `unauthenticated_client` directly.
    #
    # A separate TestClient(app) instance (not unauthenticated_client itself, just header-mutated)
    # — both still hit the same overridden get_db/db_session (the override lives on `app`, set up
    # by the unauthenticated_client fixture this depends on), but a test needing two identities at
    # once (e.g. an admin call and a regular user's call) needs their headers to stay independent.
    token = create_access_token(admin_user)
    with TestClient(app) as authed_client:
        authed_client.headers["Authorization"] = f"Bearer {token}"
        yield authed_client


@pytest.fixture()
def user_client(unauthenticated_client: TestClient, regular_user: User) -> Generator[TestClient, None, None]:
    # Same idea as `client`, but for a verified non-admin user — routes that any logged-in
    # visitor can reach (favorites, submissions, account) but that must reject admin-only ones.
    token = create_access_token(regular_user)
    with TestClient(app) as authed_client:
        authed_client.headers["Authorization"] = f"Bearer {token}"
        yield authed_client


@pytest.fixture()
def admin_client(
    unauthenticated_client: TestClient, plain_admin_user: User
) -> Generator[TestClient, None, None]:
    # Admin, but not super admin — for asserting that Settings/ingredient-refresh reject a
    # regular admin and require the stricter tier.
    token = create_access_token(plain_admin_user)
    with TestClient(app) as authed_client:
        authed_client.headers["Authorization"] = f"Bearer {token}"
        yield authed_client
