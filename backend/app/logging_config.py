"""Module F 4.7: minimal logging setup.

`logging.basicConfig` attaches a handler to the root logger only if
one isn't already present, so this is safe to call from `create_app()`
on every import/test run without producing duplicate log lines. It
covers every logger in the process (this app's own
"pantrypilot.access" plus the pre-existing
"app.integrations.recipeapi_io" logger) via normal propagation,
without needing per-module configuration. The format never includes
request bodies, headers, or secrets -- callers are responsible for
only ever passing safe, pre-reviewed message content (see
app.middleware.request_logging and app.integrations.recipeapi_io).
"""

from __future__ import annotations

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
