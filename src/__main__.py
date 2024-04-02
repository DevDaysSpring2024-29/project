#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import asyncio
import logging
import os

import dotenv

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import service
from models import room

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CONFIG = None
SERVICE = None

ROOM_ID = None


# Define a few command handlers. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Help!")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""

    # TODO: store single service per server


    text = update.message.text
    cmd = text.split(' ')

    async def callback(x, _y):
        logger.info("callback: " + x)

    if cmd[0] == "create":
        params = room.RoomParams(
            provider_name=cmd[1],
            filters={},
        )

        global ROOM_ID
        ROOM_ID = await SERVICE.create_room(str(update.effective_user.id), params, callback)

        await update.message.reply_text(f"ROOM ID: {ROOM_ID}")

    if cmd[0] == "start":
        await SERVICE.start_vote(str(update.effective_user.id))

    if cmd[0] in {"like", "dislike"}:
        is_liked = (cmd[0] == "like")
        next = await SERVICE.vote(str(update.effective_user.id), is_liked, "")

        await update.message.reply_text(next)

    await update.message.reply_text(text)


def main() -> None:
    global CONFIG, SERVICE
    CONFIG = {
        **dotenv.dotenv_values(".env"),
        **os.environ,
    }

    loop = asyncio.new_event_loop()
    SERVICE = loop.run_until_complete(service.get_service(CONFIG))

    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(CONFIG["BOT_TOKEN"]).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
