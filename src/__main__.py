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

from telegram import ForceReply, Update, User, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.ext.filters import TEXT

import service as service_lib
from service.service import Service
from providers.interface import ProviderKind
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


# async def start(user: User, update: Update, context: ContextTypes.DEFAULT_TYPE):
#     locations_keyboard = [
#         [InlineKeyboardButton("Отлично!", callback_data=f"/not_in_room")],
#     ]
#     await context.bot.send_message(
#         chat_id=update.effective_chat.id, 
#         text=(f"Привет {user.name}"),
#         reply_markup=InlineKeyboardMarkup(locations_keyboard),
#     )


def generate_callback(bot: Bot, chat_id: int):

    async def callback(option: str, is_finished: bool):
        if is_finished:
            locations_keyboard = [
                [InlineKeyboardButton("Отлично!", callback_data=f"/not_in_room")],
            ]
            await bot.send_message(
                chat_id=chat_id, 
                text=(f"Победила опция {option}"),
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )
        else:
            locations_keyboard = [
                [InlineKeyboardButton("Приступить", callback_data=f"/voting")],
                [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
            ]
            await bot.send_message(
                chat_id=chat_id, 
                text=("Голосование началось"),
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )
    
    return callback


def not_in_room_handler(service: Service):

    async def not_in_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
        locations_keyboard = [
            [InlineKeyboardButton("Создать комнату", callback_data=f"/create_room")],
            [InlineKeyboardButton("Присоедититься к комнате", callback_data=f"/join_room")],
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=("Вы не находитесь в комнате"),
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return not_in_room


def create_room_handler(_: Service):

    async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
        locations_keyboard = [
            *([InlineKeyboardButton(option.value, callback_data=f"/choose_provider {option.value}")] for option in ProviderKind),
            [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=("Выберите провайдер"),
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return create_room


def choose_provider_handler(service: Service, bot: Bot):

    async def choose_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.callback_query.from_user
        parsed_data = update.callback_query.data.split()
        _, provider = parsed_data
        locations_keyboard = [
            [InlineKeyboardButton("Начать е голосование", callback_data=f"/start_vote")],
            [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
        ]
        room_id = await service.create_room(user.id, {"provider_name": provider, "filters": {}}, generate_callback(bot, update.effective_chat.id))
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Комната {room_id} создана",
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return choose_provider


def start_vote_handler(service: Service):

    async def start_vote(update: Update, _: ContextTypes.DEFAULT_TYPE):
        user = update.callback_query.from_user
        await service.start_vote(user.id)
    
    return start_vote


def join_room_handler(_: Service):

    async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
        locations_keyboard = [
            [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=("Введите номер комнаты:"),
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return join_room


def message_handler(service: Service, bot: Bot):

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        room_number = update.message.text
        locations_keyboard = [
            [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
        ]
        try:
            room_number_int = int(room_number)
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, 
                text=("Неправильный номер комнаты, введите номер комнаты:"),
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )
            return

        await service.join_room(user.id, room_number_int, generate_callback(bot, update.effective_chat.id))
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=("Ожидайте начало голосования"),
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return message


def voting_handler(service: Service):

    async def voting(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.callback_query.from_user
        parsed_data = update.callback_query.data.split()
        if len(parsed_data) == 2:
            _, is_liked = parsed_data
            try:
                current_option = await service.vote(user.id, is_liked == "true", "kill me")
            except:
                return
        else:
            current_option = await service.current_option(user.id)

        locations_keyboard = [
            [
                InlineKeyboardButton("Нравится", callback_data=f"/voting true"),
                InlineKeyboardButton("Не нравится", callback_data=f"/voting false"),
            ],
            [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=(current_option),
            reply_markup=InlineKeyboardMarkup(locations_keyboard),
        )
    
    return voting


def main() -> None:
    global CONFIG, SERVICE
    CONFIG = {
        **dotenv.dotenv_values(".env"),
        **os.environ,
    }

    loop = asyncio.new_event_loop()
    SERVICE = loop.run_until_complete(service_lib.get_service(CONFIG))

    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(CONFIG["BOT_TOKEN"]).build()

    # application.add_handler(CallbackQueryHandler(start, '/start', block=False))
    application.add_handler(CallbackQueryHandler(not_in_room_handler(SERVICE), '/not_in_room', block=False))
    application.add_handler(CallbackQueryHandler(join_room_handler(SERVICE), '/join_room', block=False))
    application.add_handler(CallbackQueryHandler(create_room_handler(SERVICE), '/create_room', block=False))
    application.add_handler(CallbackQueryHandler(start_vote_handler(SERVICE), '/start_vote', block=False))

    application.add_handler(CallbackQueryHandler(choose_provider_handler(SERVICE, application.bot), '/choose_provider.*', block=False))
    application.add_handler(CallbackQueryHandler(voting_handler(SERVICE), '/voting.*', block=False))

    application.add_handler(MessageHandler(TEXT, message_handler(SERVICE, application.bot), block=False))

    application.run_polling()


if __name__ == "__main__":
    main()
