import uvicorn

from shopmate.conf.config import settings


def main() -> None:
    uvicorn.run(
        "shopmate.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
