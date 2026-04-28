import os
import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

# Set environment variables for testing BEFORE any other imports
# We use a temporary directory for the RSA key and SQLite for the database
tmp_dir = TemporaryDirectory()
test_key_path = Path(tmp_dir.name) / "test_rsa_private.pem"

os.environ["AUTH_PRIVATE_KEY_PATH"] = str(test_key_path)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Now we can import service modules
from auth.keys import generate_keys
from db import engine
from models import Base

# IMPORTANT: Generate keys IMMEDIATELY at module level
generate_keys(test_key_path)

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    # Setup for the whole session
    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    # Run the table creation
    # Using a new event loop for the setup
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_create_tables())
    loop.close()
    
    yield
    
    # Cleanup temporary directory
    tmp_dir.cleanup()

@pytest.fixture
def app():
    from main import app
    return app
