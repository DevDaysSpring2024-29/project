import telegram

from telegram.ext import Application, ContextTypes

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


    async def start(self, update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
        pass
