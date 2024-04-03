import enum
import typing

from models import room
from models import entry


class ServiceNotificationKind(enum.Enum):
    MATCH = enum.auto()
    JOINED = enum.auto()
    LEFT = enum.auto()


class ServiceNotification(typing.TypedDict):
    kind: ServiceNotificationKind
    data: typing.Dict[str, str]



class ServiceInterface(typing.Protocol):
    async def create_room(self, user_id: str, params: room.RoomParams) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        ...

    async def join_room(self, user_id: str, room_id: int) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        ...


    async def get_notifications(self, user_id: str, room_id: str) -> typing.List[ServiceNotification]:
        ...

    async def current_option(self, user_id: str) -> entry.ProviderEntry:
        ...

    async def vote(self, user_id: str, is_liked: bool) -> typing.Optional[entry.ProviderEntry]:
        ...
