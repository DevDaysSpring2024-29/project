import typing

from models import room
from models import entry


CallbackType = typing.Callable[[str, bool], None]  # If bool == True when room is closed


class ServiceInterface(typing.Protocol):
    async def create_room(self, user_id: str, params: room.RoomParams, callback: CallbackType) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        ...

    async def join_room(self, user_id: str, room_id: int) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        ...

    async def set_entries(self, user_id: str, room_id: int, entries: typing.List[entry.ProviderEntry]) -> None:
        """Will set custom list of entries"""
        ...

    async def add_entry(self, user_id: str, room_id: int, entry: entry.ProviderEntry) -> None:
        """Will add custom entry"""
        ...

    async def start_vote(self, user_id: str) -> None:
        """Only owner of the room can call this"""
        ...

    async def vote(self, user_id: str, is_liked: bool, option_name: str) -> entry.ProviderEntry:
        """Returns next option"""
        ...
