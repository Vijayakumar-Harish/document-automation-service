from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.main import app
from app.config import settings
from datetime import datetime, timedelta
import jwt
from app.db import get_db

TEST_DB_NAME = "test_assignment"

@pytest_asyncio.fixture
async def test_db():
    """
    Create an isolated test DB for every test.
    """
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[TEST_DB_NAME]

    # clean before test
    for name in await db.list_collection_names():
        await db[name].delete_many({})

    yield db

    # clean after test
    for name in await db.list_collection_names():
        await db[name].drop()

    client.close()


@pytest_asyncio.fixture(autouse=True)
async def override_db_dependency(test_db):
    """
    Makes FastAPI use the test DB.
    """
    app.override_db = test_db   # <---- used by get_db()
    yield
    app.override_db = None

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"



@pytest_asyncio.fixture(autouse=True)
async def override_db_dependency(test_db):
    async def _get_test_db():
        return test_db

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()
# -----------------------------------------------------------
# HTTP Client
# -----------------------------------------------------------
@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# -----------------------------------------------------------
# JWT Token Helper + Fixtures
# -----------------------------------------------------------
def _make_token(sub="user1", email="harish@oneshot.com", role="user"):
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)   # 🔥 add expiration
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)


@pytest.fixture
def make_token():
    """Expose the token generator to tests"""
    return _make_token


@pytest.fixture
def user_token():
    return _make_token()


@pytest.fixture
def admin_token():
    return _make_token(sub="admin", email="admin@oneshot.com", role="admin")
