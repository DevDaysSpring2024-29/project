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

    options: list[entry.ProviderEntry]
    options_likes: dict[int, set[str]]  # sizeof == sizeof options
    options_orders: dict[int, list[int]]  # for every key: sizeof value == sizeof options


EMPTY_ROOM = {
    "owner": None,

    "participants": [],
    "participants_positions": [],

    "options": [],
    "options_likes": {},
    "options_orders": {},
}


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

    async def get_notifications(self, user_id: str, room_id: str) -> typing.List[interface.ServiceNotification]:
        return []

    async def create_room(self, user_id: str, params: room.RoomParams) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        room_id = await self._generate_room_id()
        room_data = self._create_empty_room()
        provider = self.providers_.get(providers.ProviderKind[params["provider_name"]])
        if not provider:
            raise Exception("AAAAAAA")
        options = await provider.get_entries({"filters": params["filters"], "exclude_names": []})
        room_data["owner"] = user_id
        room_data["options"] = options
        room_data["options_likes"] = {i: set() for i in range(len(options))}

        self._add_user_to_room(room_data, user_id)
        self.users_[user_id] = room_id

        logging.info(room_data)

        await self._store_room(room_id, room_data)
        return room_id

    async def join_room(self, user_id: str, room_id: int) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        # Redis lock <room_id>
        room_data = await self._load_room(room_id)
        self._add_user_to_room(room_data, user_id)
        self.users_[user_id] = room_id
        await self._store_room(room_id, room_data)
        # Redis unlock <room_id>

    async def current_option(self, user_id: str) -> entry.ProviderEntry:
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        user_index = self._get_user_index(user_id, room_data)
        return room_data["options"][self._get_user_current_option_index(user_index, room_data)]
        # Redis unlock <room_id>

    async def vote(self, user_id: str, is_liked: bool) -> typing.Optional[entry.ProviderEntry]:
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        user_index = self._get_user_index(user_id, room_data)
        match = None
        if is_liked:
            match = await self._like_option(user_index, room_data)
        self._progress_user(user_index, room_data)
        await self._store_room(room_id, room_data)
        if match:
            return match
        # Redis unlock <room_id>

    def _get_user_index(self, user_id: str, room_data: RoomData) -> int:
        return room_data["participants"].index(user_id)

    def _get_user_current_option_index(self, user_index: int, room_data: RoomData) -> int:
        return room_data["options_orders"][user_index][
            room_data["participants_positions"][user_index]
        ]

    async def _like_option(self, user_index: int, room_data: RoomData) -> typing.Optional[entry.ProviderEntry]:
        option_index = self._get_user_current_option_index(user_index, room_data)
        room_data["options_likes"][option_index].add(room_data["participants"][user_index])

        if len(room_data["options_likes"][option_index]) == len(room_data["participants"]):
            option = room_data["options"][option_index]
            logging.info("match: " + option["name"])
            return option

        return None

    def _progress_user(self, user_index: int, room_data: RoomData):
        # To-do: check if reached final option and load more
        room_data["participants_positions"][user_index] += 1

    def _create_empty_room(self) -> RoomData:
        return copy.deepcopy(EMPTY_ROOM)  # type: ignore

    def _add_user_to_room(self, room_data: RoomData, user_id: str):
        room_data["participants"].append(user_id)
        room_data["participants_positions"].append(0)

        def get_shuffled():
            indexes = list(range(len(room_data["options"])))
            random.shuffle(indexes)
            return indexes

        room_data["options_orders"][len(room_data["participants"]) - 1] = get_shuffled()

    # Add redis later for following methods (for now can be used with one worker)
    async def _assign_users_room(self, user_id: str, room_id: int):
        self.users_[user_id] = room_id

    async def _remove_room_users_room(self, user_id: str, room_id: int):
        self.users_[user_id] = room_id

    async def _get_users_room(self, user_id: str) -> int:
        return self.users_[user_id]

    async def _load_room(self, room_id: int) -> RoomData:
        return self.rooms_[room_id]

    async def _store_room(self, room_id: int, room_data: RoomData):
        self.rooms_[room_id] = room_data

    async def _generate_room_id(self):
        new_id = self.next_room_id_
        self.next_room_id_ += 1
        return new_id
