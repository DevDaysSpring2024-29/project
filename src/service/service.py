import typing

from providers import interface as providers
from models import entry
from models import room

from . import interface


class Service(interface.ServiceInterface):
    def __init__(self, providers: typing.Dict[providers.ProviderKind, providers.ProviderInterface]):
        self.providers = providers

    async def create_room(self, user_id: str, params: room.RoomParams, callback: interface.CallbackType) -> int:
        return await super().create_room(user_id, params, callback)

    async def join_room(self, user_id: str, room_id: int, callback: interface.CallbackType) -> None:
        return await super().join_room(user_id, room_id, callback)

    async def start_vote(self, user_id: str) -> None:
        return await super().start_vote(user_id)

    async def vote(self, user_id: str, is_liked: bool, option_name: str) -> entry.ProviderEntry:
        provider = self.providers[providers.ProviderKind.DUMMY]
        params = providers.ProviderParams(filters={}, exclude_names=[])
        entries = await provider.get_entries(params)
        return entries[0]
