import typing

from models import room
from models import entry


class ServiceInterface(typing.Protocol):
    async def create_room(self, user_id: str, params: room.RoomParams) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        ...

    async def join_room(self, user_id: str, room_id: int) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        ...

    async def leave_room(self, user_id: str) -> None:
        ...

    async def current_option(self, user_id: str) -> typing.Tuple[entry.ProviderEntry, typing.Optional[entry.ProviderEntry]]:
        ...

    async def get_match(self, user_id: str) -> typing.Optional[entry.ProviderEntry]:
        ...

    async def add_entry(self, user_id: str, entry: entry.ProviderEntry) -> None:
        """Will add custom entry"""
        ...

    async def wait_start(self, user_id: str) -> None:
        ...

    async def start_vote(self, user_id: str) -> None:
        """Only owner of the room can call this"""
        ...

    async def get_room_participants(self, user_id: str) -> list[str]:
        ...

    async def vote(self, user_id: str, is_liked: bool):
        ...
