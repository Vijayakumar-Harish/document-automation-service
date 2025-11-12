import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from app.db_cleanup import safe_close_motor
import jwt
import sys
@pytest.fixture(scope="session", autouse=True)
def _patch_event_loop():
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Create a single event loop for the whole test session
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    try:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def _force_selector_loop():
    import sys
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



@pytest.fixture(scope="session", autouse=True)
def _cleanup_motor():
    yield
    if hasattr(app, "mongodb_client"):
        safe_close_motor(app.mongodb_client)



@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac



def make_token(sub="user1", email="harish@oneshot.com", role="user"):
    payload = {"sub": sub, "email": email, "role": role}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGO)


@pytest_asyncio.fixture
def user_token():
    return make_token()


@pytest_asyncio.fixture
def admin_token():
    return make_token(sub="admin", email="admin@oneshot.com", role="admin")
