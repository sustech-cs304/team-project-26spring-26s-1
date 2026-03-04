"""Convenience entry-point for ``uvicorn``."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Run the API server (used by the ``agent-api`` console script)."""
    uvicorn.run(
        "agent.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
