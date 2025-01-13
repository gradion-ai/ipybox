import tempfile

import pytest


@pytest.fixture(scope="module")
async def workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir
