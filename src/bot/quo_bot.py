import logging
import telegram
import enum

from bot import handler_type
from models import room, entry
from service.interface import ServiceInterface
from providers.interface import ProviderKind

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CallbackContext, CallbackQueryHandler, ContextTypes
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

            # application.add_handler(CallbackQueryHandler(start, '/start', block=False))
            self.__app.add_handler(CallbackQueryHandler(self.not_in_room_handler(), '/not_in_room', block=False))
            self.__app.add_handler(CallbackQueryHandler(self.join_room_handler(), '/join_room', block=False))
            self.__app.add_handler(CallbackQueryHandler(self.create_room_handler(), '/create_room', block=False))
            self.__app.add_handler(CallbackQueryHandler(self.start_vote_handler(), '/start_vote', block=False))

            self.__app.add_handler(CallbackQueryHandler(self.choose_provider_handler(), '/choose_provider.*', block=False))
            self.__app.add_handler(CallbackQueryHandler(self.voting_handler(), '/voting.*', block=False))

            self.__app.add_handler(MessageHandler(filters.TEXT, self.message_handler(), block=False))

            self.__app.run_polling()

    # def generate_callback(self, bot: Bot, chat_id: int):

    #     async def callback(option: str, is_finished: bool):
    #         if is_finished:
    #             locations_keyboard = [
    #                 [InlineKeyboardButton("Отлично!", callback_data=f"/not_in_room")],
    #             ]
    #             await bot.send_message(
    #                 chat_id=chat_id,
    #                 text=(f"Победила опция {option}"),
    #                 reply_markup=InlineKeyboardMarkup(locations_keyboard),
    #             )
    #         else:
    #             locations_keyboard = [
    #                 [InlineKeyboardButton("Приступить", callback_data=f"/voting")],
    #                 [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
    #             ]
    #             await bot.send_message(
    #                 chat_id=chat_id,
    #                 text=("Голосование началось"),
    #                 reply_markup=InlineKeyboardMarkup(locations_keyboard),
    #             )

    #     return callback


    def not_in_room_handler(self):

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


    def create_room_handler(self):

        async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
            locations_keyboard = [
                *([InlineKeyboardButton(option.value, callback_data=f"/choose_provider {option.name}")] for option in ProviderKind),
                [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
            ]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("Выберите провайдер"),
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )

        return create_room

    def choose_provider_handler(self):

        async def choose_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_chat.id
            parsed_data = update.callback_query.data.split()
            _, provider = parsed_data
            locations_keyboard = [
                [InlineKeyboardButton("Начать е голосование", callback_data=f"/start_vote")],
                [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
            ]
            room_id = await self.__service.create_room(str(user), {"provider_name": provider, "filters": {}})
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Комната {room_id} создана",
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )

        return choose_provider

    def start_vote_handler(self):

        async def start_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_chat.id
            await self.__service.start_vote(str(user))

            participants = await self.__service.get_room_participants(str(user))

            for participant in participants:
                locations_keyboard = [
                    [InlineKeyboardButton("Приступить", callback_data=f"/voting")],
                    [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
                ]
                await context.bot.send_message(
                    chat_id=participant,
                    text=("Голосование началось"),
                    reply_markup=InlineKeyboardMarkup(locations_keyboard),
                )

        return start_vote

    def join_room_handler(self):

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

    def message_handler(self):

        async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_chat.id
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

            await self.__service.join_room(str(user), room_number_int)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("Ожидайте начало голосования"),
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )

        return message

    def voting_handler(self):

        async def voting(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_chat.id
            parsed_data = update.callback_query.data.split()
            if len(parsed_data) == 2:
                _, is_liked = parsed_data
                await self.__service.vote(str(user), is_liked == "true")

                match = await self.__service.get_match(str(user))
                if match:
                    participants = await self.__service.get_room_participants(str(user))
                    for participant in participants:
                        locations_keyboard = [
                            [InlineKeyboardButton("Отлично!", callback_data=f"/not_in_room")],
                        ]
                        await context.bot.send_message(
                            chat_id=participant,
                            text=(f'Победила опция {match["name"]}'),
                            reply_markup=InlineKeyboardMarkup(locations_keyboard),
                        )

                current_option = await self.__service.current_option(str(user))
            else:
                current_option = await self.__service.current_option(str(user))

            locations_keyboard = [
                [
                    InlineKeyboardButton("Нравится", callback_data=f"/voting true"),
                    InlineKeyboardButton("Не нравится", callback_data=f"/voting false"),
                ],
                [InlineKeyboardButton("Вернуться в главное меню", callback_data=f"/not_in_room")],
            ]

            query_txt = "Что вы думаете о {}?".format(current_option["name"])
            if current_option["descr"]:
                query_txt += "\n{}".format(current_option["descr"])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=query_txt,
                reply_markup=InlineKeyboardMarkup(locations_keyboard),
            )

        return voting



















#     def _setup_handlers(self):
#         for handler_name in filter(lambda n: not n.startswith("_"), dir(self)):
#             handler = getattr(self, handler_name)
#             if callable(handler) and getattr(handler, "is_command", False):
#                 self.__app.add_handler(CommandHandler(handler_name, handler))
#
#         host_handler = ConversationHandler(
#             entry_points=[
#                 MessageHandler(filters.Regex("^Host room$"), self.host_room)
#             ],
#             states={
#                 QuoBotState.CHOOSE_HOST_SERVICE_TYPE: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_service_type)
#                 ],
#                 QuoBotState.HOST_LOBBY: [
#                     MessageHandler(filters.Regex("^Start Voting$"), self.vote_start),
#                     ConversationHandler(
#                         entry_points=[
#                             MessageHandler(filters.Regex("^Add Entry$"), self.add_entry)
#                         ],
#                         states={
#                             QuoBotState.QUERY_ENTRY: [
#                                 MessageHandler(filters.TEXT & ~filters.COMMAND, self.query_entry)
#                             ],
#                         },
#                         fallbacks=[
#                             CommandHandler("start", self.start),
#                         ],
#                     ),
#                 ],
#                 QuoBotState.VOTE_IN_PROGRESS: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote_question)
#                 ],
#                 QuoBotState.WAITING_FOR_VOTE: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote)
#                 ],
#             },
#             fallbacks=[
#                 CommandHandler("start", self.start),
#             ]
#         )
#         self.__app.add_handler(host_handler)
#
#         join_handler = ConversationHandler(
#             entry_points=[MessageHandler(filters.Regex("^Join room$"), self.join_room)],
#             states={
#                 QuoBotState.WAITING_FOR_ROOM_NUMBER: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.join_room_by_id)],
#                 QuoBotState.WAITING_FOR_HOST_TO_START: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.wait_for_start)],
#                 QuoBotState.VOTE_IN_PROGRESS: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote_start)],
#                 QuoBotState.WAITING_FOR_VOTE: [
#                     MessageHandler(filters.TEXT & ~filters.COMMAND, self.vote)],
#             },
#             fallbacks=[]
#         )
#         self.__app.add_handler(join_handler)
#
#     @handler_type.command
#     async def start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         buttons = [[button_option for button_option in self.__button_map["start"].keys()]]
#         reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Hi!",
#                                        reply_markup=reply_markup)
#
#     @handler_type.command
#     async def join_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Provide room number")
#
#         return QuoBotState.WAITING_FOR_ROOM_NUMBER
#
#     async def join_room_by_id(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         room_id = int(update.message.text)
#         # TODO: fallback to WAITING_FOR_ROOM_NUMBER if could not parse or join
#
#         user_id = update.effective_chat.id
#
#         await self.__service.join_room(str(user_id), room_id)
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Joined room {}".format(room_id))
#
#         participants = await self.__service.get_room_participants(str(user_id))
#         for participant in participants:
#             if participant == str(user_id):
#                 continue
#
#             await context.bot.send_message(chat_id=participant,
#                                             text="{} joined!".format(user_id))
#
#         return QuoBotState.WAITING_FOR_HOST_TO_START
#
#     async def wait_for_start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                         text="Waiting for host to start...")
#
#         await self.__service.wait_start(str(update.effective_chat.id))
#
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Voting started!")
#
#         return await self.next_vote(update, context)
#
#     @handler_type.command
#     async def add_entry(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Provide entry:")
#         return QuoBotState.QUERY_ENTRY
#
#     @handler_type.command
#     async def query_entry(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         new_entry = update.message.text
#         user_id = update.effective_chat.id
#
#         entry_obj = entry.ProviderEntry(name=str(new_entry), descr=None, picture_url=None, rating=None, price=None)
#
#         await self.__service.add_entry(str(user_id), entry_obj)
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Entry \"{}\" added".format(new_entry))
#
#         return ConversationHandler.END
#
#     @handler_type.command
#     async def vote_start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         user_id = update.effective_chat.id
#
#         await self.__service.start_vote(str(user_id))
#
#         participants = await self.__service.get_room_participants(str(user_id))
#
#         for participant in participants:
#             await context.bot.send_message(chat_id=participant,
#                                             text="Voting started!")
#
#         return await self.next_vote(update, context)
#
#     @handler_type.command
#     async def host_room(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         buttons = [[button_option for button_option in self.__button_map["choose_service_type"].keys()]]
#         reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Choose a service type",
#                                        reply_markup=reply_markup)
#         return QuoBotState.CHOOSE_HOST_SERVICE_TYPE
#
#     async def next_vote(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         buttons = [[button_option for button_option in self.__button_map["vote"].keys()]]
#         reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
#
#         user_id = update.effective_chat.id
#         curr_option, maybe_match = await self.__service.current_option(str(user_id))
#
#         query_text = "What do you think about\n{}?".format(curr_option["name"])
#         if curr_option["descr"]:
#             query_text += "\n{}".format(curr_option["descr"])
#
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text=query_text,
#                                        reply_markup=reply_markup)
#         return QuoBotState.WAITING_FOR_VOTE
#
#     async def choose_service_type(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         provider_name = update.message.text
#         user_id = update.effective_chat.id
#
#         params = room.RoomParams(
#             provider_name=provider_name or "",
#             filters={},
#         )
#
#         room_id = await self.__service.create_room(str(user_id), params)
#
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Room Created! ID: {}".format(room_id))
#
#         buttons = [[button_option for button_option in self.__button_map["host_lobby"].keys()]]
#         reply_markup = ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
#         await context.bot.send_message(chat_id=update.effective_chat.id,
#                                        text="Waiting for other participants",
#                                        reply_markup=reply_markup)
#
#         return QuoBotState.HOST_LOBBY
#
#     @handler_type.command
#     async def vote_question(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         return await self.next_vote(update, context)
#
#     @handler_type.command
#     async def vote(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
#         vote_response = update.message.text
#         user_id = update.effective_chat.id
#
#         is_liked = (vote_response == "Like")
#         await self.__service.vote(str(user_id), is_liked)
#
#         got_match = await self.__service.get_match(str(user_id))
#         if got_match:
#             participants = await self.__service.get_room_participants(str(user_id))
#
#             for participant in participants:
#                 await context.bot.send_message(chat_id=participant,
#                                                text="You've got a match: {}!".format(got_match["name"]))
#
#             return ConversationHandler.END
#
#         return await self.next_vote(update, context)
