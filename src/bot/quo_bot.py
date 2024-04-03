import logging
import telegram
import functools
import enum

from bot import handler_type
from models import room
from service.interface import ServiceInterface
from providers.interface import ProviderKind

from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, ContextTypes
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler
from telegram.ext import filters

__all__ = ["QuoBot"]


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """Echo the user message."""
#
#     # TODO: store single service per server
#
#
#     text = update.message.text
#     cmd = text.split(' ')
#
#
#     if cmd[0] == "create":
#
#     if cmd[0] in {"like", "dislike"}:
#         is_liked = (cmd[0] == "like")
#
#     await update.message.reply_text("echo cmd: " + text)


class QuoBotState(enum.Enum):
    CHOOSE_HOST_SERVICE_TYPE = enum.auto()
    WAITING_FOR_ROOM_NUMBER = enum.auto()
    VOTE_IN_PROGRESS = enum.auto()
    WAITING_FOR_VOTE = enum.auto()


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
                "choose_service_type": {
                    kind.name: self.choose_service_type
                    for kind in ProviderKind
                },
                "vote": {
                    "Like": self.vote,
                    "Dislike": self.vote,
                },
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
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_service_type)],
                QuoBotState.WAITING_FOR_ROOM_NUMBER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.join_room_by_id)],
                QuoBotState.VOTE_IN_PROGRESS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote_start)],
                QuoBotState.WAITING_FOR_VOTE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote)],
            },
            fallbacks=[]
        )
        self.__app.add_handler(host_handler)

    @handler_type.command
    async def start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["start"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Hi!",
                                       reply_markup=reply_markup)

    @handler_type.button
    async def join_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Provide room number")

        return QuoBotState.WAITING_FOR_ROOM_NUMBER


    async def join_room_by_id(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        room_id = int(update.message.text)
        # TODO: fallback to WAITING_FOR_ROOM_NUMBER if could not parse or join

        user_id = update.effective_user.id

        async def callback(x, is_match):
            pass
            # if is_match:
            #     await context.bot.send_message(update.effective_chat.id, "match : " + x["name"])
            # else:
            #     await context.bot.send_message(update.effective_chat.id, x["name"])

        await self.__service.join_room(str(user_id), room_id, callback)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Joined room {}".format(room_id))
        return QuoBotState.VOTE_IN_PROGRESS


    async def host_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["choose_service_type"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Choose a service type",
                                       reply_markup=reply_markup)
        return QuoBotState.CHOOSE_HOST_SERVICE_TYPE

    async def vote_start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["vote"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

        user_id = update.effective_user.id
        curr_option = await self.__service.current_option(str(user_id))

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="What do you think about\n{}?".format(curr_option["name"]),
                                       reply_markup=reply_markup)
        return QuoBotState.WAITING_FOR_VOTE

    async def vote(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        vote_response = update.message.text
        user_id = update.effective_user.id

        is_liked = (vote_response == "Like")
        await self.__service.vote(str(user_id), is_liked)

        return QuoBotState.VOTE_IN_PROGRESS

    async def choose_service_type(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        provider_name = update.message.text
        user_id = update.effective_user.id

        params = room.RoomParams(
            provider_name=provider_name or "",
            filters={},
        )

        async def callback(x, is_match):
            pass
            # if is_match:
            #     await context.bot.send_message(update.effective_chat.id, "match : " + x["name"])
            # else:
            #     await context.bot.send_message(update.effective_chat.id, x["name"])

        room_id = await self.__service.create_room(str(user_id), params, callback)

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Room Created! ID: {}".format(room_id))

        await self.__service.start_vote(str(update.effective_user.id))

        return QuoBotState.VOTE_IN_PROGRESS
