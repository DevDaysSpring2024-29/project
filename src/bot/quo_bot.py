import logging
import telegram
import enum

from bot import handler_type
from models import room, entry
from service.interface import ServiceInterface
from providers.interface import ProviderKind

from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CallbackContext, ContextTypes
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


class QuoBotState(enum.Enum):
    CHOOSE_HOST_SERVICE_TYPE = enum.auto()
    WAITING_FOR_ROOM_NUMBER = enum.auto()
    HOST_LOBBY = enum.auto()
    QUERY_ENTRY = enum.auto()
    WAITING_FOR_HOST_TO_START = enum.auto()
    VOTE_IN_PROGRESS = enum.auto()
    WAITING_FOR_VOTE = enum.auto()


def divide_chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


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
                "start": {"Создать комнату": self.host_room, "Присоединиться к комнате": self.join_room},
                "choose_service_type": {
                    kind.value: self.choose_service_type
                    for kind in ProviderKind
                },
                "host_lobby": {
                    "Запустить голосование": self.vote_start,
                    "Добавить опцию": self.add_entry,
                },
                "vote": {
                    "Лайк 👍": self.vote,
                    "Дизлайк 👎": self.vote,
                },
            }

            self.__app.run_polling()

    def _setup_handlers(self):
        for handler_name in filter(lambda n: not n.startswith("_"), dir(self)):
            handler = getattr(self, handler_name)
            if callable(handler) and getattr(handler, "is_command", False):
                self.__app.add_handler(CommandHandler(handler_name, handler))

        host_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.Regex("Создать комнату$"), self.host_room)
            ],
            states={
                QuoBotState.CHOOSE_HOST_SERVICE_TYPE: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_service_type)
                ],
                QuoBotState.HOST_LOBBY: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.Regex("^Запустить голосование$"), self.vote_start),
                    ConversationHandler(
                        entry_points=[
                            MessageHandler(filters.Regex("^Добавить опцию$"), self.add_entry)
                        ],
                        states={
                            QuoBotState.QUERY_ENTRY: [
                                MessageHandler(filters.TEXT & ~filters.COMMAND, self.query_entry)
                            ],
                        },
                        fallbacks=[],
                    ),
                ],
                QuoBotState.VOTE_IN_PROGRESS: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote_question)
                ],
                QuoBotState.WAITING_FOR_VOTE: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote)
                ],
            },
            fallbacks=[],
            block=False,
        )
        self.__app.add_handler(host_handler)

        join_handler = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^Присоединиться к комнате$"), self.join_room)],
            states={
                QuoBotState.WAITING_FOR_ROOM_NUMBER: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.join_room_by_id),
                ],
                QuoBotState.VOTE_IN_PROGRESS: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote_start)],
                QuoBotState.WAITING_FOR_VOTE: [
                    MessageHandler(filters.Regex("^Выйти$"), self.leave_room),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote)],
            },
            fallbacks=[],
            block=False,
        )
        self.__app.add_handler(join_handler)

    @handler_type.command
    async def start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [[button_option for button_option in self.__button_map["start"].keys()]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Привет! Я QuoRoom Бот. Ты сейчас не находишься ни в какой комнате",
                                       reply_markup=reply_markup)

    @handler_type.command
    async def join_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [["Выйти"]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Введи идентификатор комнаты:",
                                       reply_markup=reply_markup)

        return QuoBotState.WAITING_FOR_ROOM_NUMBER

    async def join_room_by_id(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            room_id = int(update.message.text)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Не получилось обработать идентификатор комнаты: \"{}\"".format(update.message.text))
            return await self.join_room(update, context)


        user_id = update.effective_chat.id

        try:
            await self.__service.join_room(str(user_id), room_id)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Комната \"{}\" не найдена".format(update.message.text))
            return await self.join_room(update, context)

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Успешно присоединились к комнате {}".format(room_id))

        participants = await self.__service.get_room_participants(str(user_id))
        for participant in participants:
            if participant == str(user_id):
                continue

            await context.bot.send_message(chat_id=participant,
                                            text="@{} присоединился!".format(update.effective_user.username))

        return await self.wait_for_start(update, context)

    async def wait_for_start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text="Ожидаем начала...")

        await self.__service.wait_start(str(update.effective_chat.id))

        return await self.next_vote(update, context)

    @handler_type.command
    async def add_entry(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [["Все опции добавлены"]]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Введите опицю:",
                                       reply_markup=reply_markup)
        return QuoBotState.QUERY_ENTRY

    @handler_type.command
    async def query_entry(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        new_entry = update.message.text
        if new_entry == "Все опции добавлены":
            buttons = [[button_option for button_option in self.__button_map["host_lobby"].keys()]]
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text="Запускаем?",
                                        reply_markup=reply_markup)
            return ConversationHandler.END

        user_id = update.effective_chat.id

        entry_obj = entry.ProviderEntry(name=str(new_entry), descr=None, picture_url=None, rating=None, price=None)

        await self.__service.add_entry(str(user_id), entry_obj)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Опция \"{}\" добавлена".format(new_entry))

        return await self.add_entry(update, context)

    @handler_type.command
    async def vote_start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_chat.id

        participants = await self.__service.get_room_participants(str(user_id))
        for participant in participants:
            await context.bot.send_message(chat_id=participant,
                                        text="Запускаем голосование...")

        await self.__service.start_vote(str(user_id))


        for participant in participants:
            await context.bot.send_message(chat_id=participant,
                                            text="Голосование началось!")

        return await self.next_vote(update, context)

    @handler_type.command
    async def host_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = list(divide_chunks([button_option for button_option in self.__button_map["choose_service_type"].keys()], 3)) + [["Выйти"]]

        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Из какой категории будем выбирать?",
                                       reply_markup=reply_markup)
        return QuoBotState.CHOOSE_HOST_SERVICE_TYPE

    async def next_vote(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        buttons = [
            [button_option for button_option in self.__button_map["vote"].keys()],
            ["Выйти"],
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

        user_id = update.effective_chat.id
        curr_option, maybe_match = await self.__service.current_option(str(user_id))

        query_text = "Что ты думаешь про\n{}?".format(curr_option["name"])
        if curr_option["descr"]:
            query_text += "\n{}".format(curr_option["descr"])

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=query_text,
                                       reply_markup=reply_markup)
        return QuoBotState.WAITING_FOR_VOTE

    async def choose_service_type(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        provider_name = update.message.text
        user_id = update.effective_chat.id

        try:
            _ = ProviderKind(provider_name)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                        text="А я про такую категорию ничего и не знаю... Попробуй еще раз")
            return self.host_room(update, context)


        params = room.RoomParams(
            provider_name=provider_name or "",
            filters={},
        )

        room_id = await self.__service.create_room(str(user_id), params)

        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Комната создана! Предоставьте остальным участникам идентификатор:")
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="{}".format(room_id))

        buttons = [
            [button_option for button_option in self.__button_map["host_lobby"].keys()],
            ["Выйти"],
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Ожидаем остальных участников",
                                       reply_markup=reply_markup)

        return QuoBotState.HOST_LOBBY

    @handler_type.command
    async def vote_question(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.next_vote(update, context)

    @handler_type.command
    async def leave_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_chat.id
        try:
            participants = await self.__service.get_room_participants(str(user_id))
            await self.__service.leave_room(str(user_id))

            for participant in participants:
                if participant == str(user_id):
                    continue

                await context.bot.send_message(chat_id=participant,
                                                text="@{} вышел".format(update.effective_user.username))

        except:
            logging.info("left")

        buttons = [
            [button_option for button_option in self.__button_map["start"].keys()],
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

        await context.bot.send_message(chat_id=user_id,
                                        text="Вы вышли из комнаты",
                                        reply_markup=reply_markup)

        return ConversationHandler.END


    @handler_type.command
    async def vote(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        vote_response = update.message.text
        user_id = update.effective_chat.id

        if vote_response == "Выйти":
            return await self.leave_room(update, context)

        is_liked = (vote_response == "Лайк 👍")
        await self.__service.vote(str(user_id), is_liked)

        got_match = await self.__service.get_match(str(user_id))
        if got_match:
            participants = await self.__service.get_room_participants(str(user_id))

            match_txt = "You've got a match: {}!".format(got_match["name"])
            if got_match["descr"]:
                match_txt += "\n{}".format(got_match["descr"])

            buttons = [[button_option for button_option in self.__button_map["start"].keys()]]
            reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)

            for participant in participants:
                await context.bot.send_message(chat_id=participant,
                                               text=match_txt,
                                               reply_markup=reply_markup)
            return ConversationHandler.END

        return await self.next_vote(update, context)
