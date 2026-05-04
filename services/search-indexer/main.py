import asyncio
import logging

from config import get_settings
from consumer import run_consumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def main() -> None:
    settings = get_settings()
    asyncio.run(run_consumer(settings))


if __name__ == "__main__":
    main()

