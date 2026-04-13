import os
from datetime import datetime, timezone
from decimal import Decimal

os.environ.setdefault("API_KEY", "test-api-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("FMCSA_WEBKEY", "test-fmcsa-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.models import Load  # noqa: E402
from app.deps import get_db  # noqa: E402
from app.main import app  # noqa: E402

API_KEY = "test-api-key"


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Load.__table__.create(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def seeded_session(session_factory):
    session = session_factory()
    session.add_all(
        [
            Load(
                load_id="L-9001",
                origin="Dallas, TX",
                destination="Atlanta, GA",
                pickup_datetime=datetime(2026, 4, 15, 8, tzinfo=timezone.utc),
                delivery_datetime=datetime(2026, 4, 16, 18, tzinfo=timezone.utc),
                equipment_type="Dry Van",
                loadboard_rate=Decimal("2400.00"),
                notes="Seeded for tests",
                status="available",
            ),
            Load(
                load_id="L-9002",
                origin="Los Angeles, CA",
                destination="Phoenix, AZ",
                pickup_datetime=datetime(2026, 4, 14, 6, 30, tzinfo=timezone.utc),
                delivery_datetime=datetime(2026, 4, 14, 20, tzinfo=timezone.utc),
                equipment_type="Reefer",
                loadboard_rate=Decimal("1850.00"),
                notes="Reefer test load",
                status="available",
            ),
            Load(
                load_id="L-9003",
                origin="Chicago, IL",
                destination="New York, NY",
                pickup_datetime=datetime(2026, 4, 16, 7, tzinfo=timezone.utc),
                delivery_datetime=datetime(2026, 4, 18, 12, tzinfo=timezone.utc),
                equipment_type="Dry Van",
                loadboard_rate=Decimal("2950.00"),
                status="booked",
            ),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(session_factory, seeded_session):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
