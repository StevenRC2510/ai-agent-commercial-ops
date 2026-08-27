"""Container entrypoint. Starts Uvicorn with the JSON log configuration."""

import uvicorn

from app.infrastructure.obs import configure_logging

if __name__ == "__main__":
    # log_config=None: Uvicorn would otherwise overwrite our level-adjusted config.
    configure_logging()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 - binding all interfaces is required inside the container
        port=8000,
        log_config=None,
    )
