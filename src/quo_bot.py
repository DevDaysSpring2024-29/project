import telegram
import functools

import handler_type

from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, ContextTypes
from telegram.ext import CommandHandler, MessageHandler
from telegram.ext import filters

__all__ = ["QuoBot"]


class QuoBot:
    __initialized = False
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(QuoBot, cls).__new__(cls)

        return cls.__instance

    def __init__(self, token: str):
        if not self.__initialized:
            self.__initialized = True
            self.__token = token
            self.__app = Application.builder().token(self.__token).build()
            self._setup_handlers()

            self.__button_map = {
                "start": {"Host room": self.host_room, "Join room": self.join_room},
            }

            self.__app.run_polling()

    def _setup_handlers(self):
        for handler_name in filter(lambda n: not n.startswith("_"), dir(self)):
            handler = getattr(self, handler_name)
            if callable(handler) and getattr(handler, "is_command", False):
                self.__app.add_handler(CommandHandler(handler_name, handler))

        button_reply_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_buttons)
        self.__app.add_handler(button_reply_handler)

    async def _handle_buttons(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        message_to_handler = functools.reduce(lambda acc, d: acc | d, self.__button_map.values())
        message = update.message.text
        if message in message_to_handler:
            await message_to_handler[message](update, context)
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="There is no such button option!")

    @handler_type.command
    async def start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["start"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="TODO: Greetings",
                                       reply_markup=reply_markup)

    @handler_type.button
    async def join_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        print("join room")
        pass

    @handler_type.button
    async def host_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        print("host room")
        pass
