"""Run the API server: ``python -m se_pov_builder`` (binds to SEPB_HOST, default 127.0.0.1)."""

from __future__ import annotations

import uvicorn

from .app import create_app
from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    if settings.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"WARNING: binding to {settings.host}. This tool has no user authentication; "
              "set SEPB_API_TOKEN and put it behind your own access controls.")
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, access_log=False)


if __name__ == "__main__":
    main()
