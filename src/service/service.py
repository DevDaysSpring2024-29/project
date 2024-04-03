import asyncio
import copy
import json
from logging import log
import logging
import random
import typing

import redis.asyncio as redis

from providers import interface as providers
from models import entry
from models import room

from . import interface


class RoomData(typing.TypedDict):
    owner: str

    participants: list[str]
    participants_positions: list[int]  # sizeof == sizeof participants
    participants_callbacks: list[interface.CallbackType]  # sizeof == sizeof participants

    options: list[entry.ProviderEntry]
    options_likes: list[int]  # sizeof == sizeof options
    options_orders: dict[int, list[int]]  # for every key: sizeof value == sizeof options

    vote_started: bool


EMPTY_ROOM = {
    "owner": None,

    "participants": [],
    "participants_positions": [],
    "participants_callbacks": [],

    "options": [],
    "options_likes": [],
    "options_orders": {},

    "vote_started": False,
}

ROOM_KEY_TEMPLATE = "room:{room_id}"
ROOM_LOCK_TEMPLATE = "room-lock:{room_id}"

USER_KEY_TEMPLATE = "user:{user_id}"

ROOM_ID_COUNTER = "room-id-counter"


class Service(interface.ServiceInterface):
    providers_: dict[providers.ProviderKind, providers.ProviderInterface]
    rooms_: dict[int, RoomData]  # room_id to RoomData mapping
    users_: dict[str, int]  # user_id to room_id mapping
    next_room_id_: int

    def __init__(self, storage: redis.Redis, providers: typing.Dict[providers.ProviderKind, providers.ProviderInterface]):
        self.providers_ = providers
        self.storage_ = storage
        self.rooms_ = dict()
        self.users_ = dict()
        self.next_room_id_ = 0

    async def create_room(self, user_id: str, params: room.RoomParams, callback: interface.CallbackType) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        room_id = await self._generate_room_id()
        room_data = self._create_empty_room()
        self._add_user_to_room(room_data, user_id, callback)
        self.users_[user_id] = room_id
        provider = self.providers_.get(providers.ProviderKind[params["provider_name"]])
        if not provider:
            raise Exception("AAAAAAA")
        options = await provider.get_entries({"filters": params["filters"], "exclude_names": []})
        room_data["owner"] = user_id
        room_data["options"] = options
        room_data["options_likes"] = [0] * len(options)

        logging.info(room_data)

        await self._store_room(room_id, room_data)
        return room_id

    async def join_room(self, user_id: str, room_id: int, callback: interface.CallbackType) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        room_data = await self._load_room(room_id)
        async with self.storage_.lock(ROOM_LOCK_TEMPLATE.format(room_id = room_id)) as lock:
            self._add_user_to_room(room_data, user_id, callback)
            await self._store_room(room_id, room_data)

    async def set_entries(self, user_id: str, room_id: int, entries: typing.List[entry.ProviderEntry]) -> None:
        return await super().set_entries(user_id, room_id, entries)

    async def start_vote(self, user_id: str) -> None:
        """Only owner of the room can call this"""
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if room_data["vote_started"] is True or room_data["owner"] != user_id:
            raise Exception("OH GOD WHY PLEASE STOP I BEG YOU AAAAA")
        room_data["vote_started"] = True

        def get_shuffled():
            indexes = list(range(len(room_data["options"])))
            random.shuffle(indexes)
            return indexes

        room_data["options_orders"] = {i: get_shuffled() for i in range(len(room_data["participants"]))}
        await self._store_room(room_id, room_data)

        await asyncio.gather(
            *(
                callback(room_data["options"][
                    self._get_user_current_option_index(i, room_data)
                ], False)
                for i, callback in enumerate(room_data["participants_callbacks"])
            )
        )

    async def vote(self, user_id: str, is_liked: bool, _: str) -> entry.ProviderEntry:
        """Returns next option"""
        room_id = await self._get_users_room(user_id)
        async with self.storage_.lock(ROOM_LOCK_TEMPLATE.format(room_id = room_id)) as lock:
            room_data = await self._load_room(room_id)
            if not room_data["vote_started"]:
                raise Exception("MAKE IT STOP MAKE IT STOP")
            user_index = self._get_user_index(user_id, room_data)
            if is_liked:
                await self._like_option(user_index, room_data)
            await self._store_room(room_id, room_data)
            return self._progress_user(user_index, room_data)

    def _get_user_index(self, user_id: str, room_data: RoomData) -> int:
        return room_data["participants"].index(user_id)

    def _get_user_current_option_index(self, user_index: int, room_data: RoomData) -> int:
        return room_data["options_orders"][user_index][
                room_data["participants_positions"][user_index]
            ]

    async def _like_option(self, user_index: int, room_data: RoomData):
        option_index = self._get_user_current_option_index(user_index, room_data)
        room_data["options_likes"][option_index] += 1

        if room_data["options_likes"][option_index] == len(room_data["participants"]):
            option = room_data["options"][option_index]
            await asyncio.gather(
                *(
                    callback(option, True)
                    for callback in room_data["participants_callbacks"]
                )
            )

    def _progress_user(self, user_index: int, room_data: RoomData) -> entry.ProviderEntry:
        # To-do: check if reached final option and load more
        room_data["participants_positions"][user_index] += 1

        return room_data["options"][
            self._get_user_current_option_index(user_index, room_data)
        ]

    def _create_empty_room(self) -> RoomData:
        return copy.deepcopy(EMPTY_ROOM)  # type: ignore

    def _add_user_to_room(self, room_data: RoomData, user_id: str, callback: interface.CallbackType):
        room_data["participants"].append(user_id)
        room_data["participants_positions"].append(0)
        room_data["participants_callbacks"].append(callback)

    # Add redis later for following methods (for now can be used with one worker)
    async def _assign_users_room(self, user_id: str, room_id: int):
        user_key = USER_KEY_TEMPLATE.format(user_id=user_id)
        await self.storage_.set(user_key, room_id)

    async def _get_users_room(self, user_id: str) -> int:
        user_key = USER_KEY_TEMPLATE.format(user_id=user_id)
        return typing.cast(int, await self.storage_.get(user_key))

    async def _load_room(self, room_id: int) -> RoomData:
        room_key = ROOM_KEY_TEMPLATE.format(room_id=room_id)
        raw_room_data = typing.cast(bytes, await self.storage_.get(room_key))
        return json.loads(raw_room_data.decode("utf-8"))

    async def _store_room(self, room_id: int, room_data: RoomData):
        room_key = ROOM_KEY_TEMPLATE.format(room_id=room_id)
        raw_room_data = json.dumps(room_data).encode("utf-8")
        await self.storage_.set(room_key, raw_room_data)
        
    async def _generate_room_id(self):
        return self.storage_.incr(ROOM_ID_COUNTER)
