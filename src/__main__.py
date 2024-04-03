#!/usr/bin/env python
import asyncio
import os

import dotenv

import service
from bot import quo_bot


def main() -> None:
    config = {
        **dotenv.dotenv_values(".env"),
        **os.environ,
    }

    loop = asyncio.new_event_loop()
    s = loop.run_until_complete(service.get_service(config))
    quo_bot.QuoBot(config["BOT_TOKEN"], s)


if __name__ == "__main__":
    main()
