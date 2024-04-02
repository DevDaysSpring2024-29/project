import telegram
import functools
import enum

import handler_type

from service.interface import ServiceInterface

from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, ContextTypes
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler
from telegram.ext import filters

__all__ = ["QuoBot"]


class QuoBotState(enum.Enum):
    CHOOSE_HOST_SERVICE_TYPE = enum.auto()
    VOTE_IN_PROGRESS = enum.auto()


class QuoBot:
    __initialized = False
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(QuoBot, cls).__new__(cls)

        return cls.__instance

    def __init__(self, token: str, service: ServiceInterface):
        if not self.__initialized:
            self.__initialized = True
            self.__token = token
            self.__service = service
            self.__app = Application.builder().token(self.__token).build()
            self._setup_handlers()

            self.__button_map = {
                "start": {"Host room": self.host_room, "Join room": self.join_room},
                # TODO: Sync keys with provider names
                "choose_service_type": {"Food": self.host_type_food, "Movies": self.host_type_movies,
                                        "Custom": self.host_type_custom}
            }

            self.__app.run_polling()

    def _setup_handlers(self):
        for handler_name in filter(lambda n: not n.startswith("_"), dir(self)):
            handler = getattr(self, handler_name)
            if callable(handler) and getattr(handler, "is_command", False):
                self.__app.add_handler(CommandHandler(handler_name, handler))

        host_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Host room$"), self.host_room)],
            states={
                QuoBotState.CHOOSE_HOST_SERVICE_TYPE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_service_type)]
            },
            fallbacks=[]
        )
        self.__app.add_handler(host_handler)

    async def _handle_buttons(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        message_to_handler = functools.reduce(lambda acc, d: acc | d, self.__button_map.values())
        message = update.message.text
        if message in self.__button_map["start"]:
            await self.__button_map["start"][message](update, context)
        elif message in self.__button_map["service_type"]:
            pass
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

    async def host_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["choose_service_type"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Choose a service type",
                                       reply_markup=reply_markup)
        return QuoBotState.CHOOSE_HOST_SERVICE_TYPE

    async def choose_service_type(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        provider_name = update.message.text
        user_id = update.effective_user.id

        # callback = lambda id: id
        # await self.__service.create_room(user_id=user_id, params={"provider_name": provider_name, "filters": {}},
        #                                  callback=callback)

        return QuoBotState.VOTE_IN_PROGRESS
