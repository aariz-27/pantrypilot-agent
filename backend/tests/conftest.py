"""Suite-wide fixtures.

Module F 4.3 (rate limiting): the limiter's in-memory storage is
process-global (module-level `app.rate_limit.limiter`), so without a
reset it accumulates hits across every test in the same pytest run --
tests unrelated to rate limiting would start seeing 429s once enough
earlier tests had called the same endpoint. Dedicated rate-limit tests
(tests/integration/test_rate_limiting.py) still work: this only resets
counts *before* each test runs, so a test that issues enough requests
to trip a limit still can.
"""

from __future__ import annotations

import pytest

from app.rate_limit import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
