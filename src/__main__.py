import dotenv
import os

from quo_bot import QuoBot


def main():
    config = {
        **dotenv.dotenv_values(".env"),
        **os.environ,
    }
    bot = QuoBot(config["BOT_TOKEN"])


if __name__ == "__main__":
    main()
