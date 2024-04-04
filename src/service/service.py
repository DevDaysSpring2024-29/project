import asyncio
import copy
import json
import itertools
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

    params: room.RoomParams

    participants: set[str]
    participants_positions: dict[str, int]  # sizeof == sizeof participants

    options: list[entry.ProviderEntry]
    options_likes: dict[int, set[str]]  # sizeof == sizeof options
    options_orders: dict[str, list[int]]  # for every key: sizeof value == sizeof options

    match: typing.Optional[entry.ProviderEntry]
    vote_started: bool


EMPTY_ROOM = {
    "owner": None,
    "match": None,

    "params": None,

    "participants": set(),
    "participants_positions": {},

    "options": [],
    "options_likes": {},
    "options_orders": {},

    "vote_started": False,
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
        self.next_room_id_ = random.randint(10000, 50000)

    async def get_room_participants(self, user_id: str) -> list[str]:
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        return list(room_data["participants"])

    async def wait_start(self, user_id: str):
        room_id = await self._get_users_room(user_id)

        room_data = await self._load_room(room_id)
        while room_data["vote_started"] is False:
            # FIXME
            await asyncio.sleep(1)
            logging.info("waiting")
            room_data = await self._load_room(room_id)

    async def create_room(self, user_id: str, params: room.RoomParams) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        room_id = await self._generate_room_id()
        room_data = self._create_empty_room()

        room_data["params"] = params
        room_data["owner"] = user_id

        self._add_user_to_room(room_data, user_id)
        self.users_[user_id] = room_id

        logging.info(room_data)

        await self._store_room(room_id, room_data)
        return room_id

    async def add_entry(self, user_id: str, entry: entry.ProviderEntry) -> None:
        """Will add custom entry"""
        # Redis lock <room_id>
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if room_data["vote_started"] is True or room_data["owner"] != user_id:
            raise Exception("A? A? A? A? A? A? A? A? A? A? A? A? A? A? A? A?")
        room_data["options"].append(entry)
        await self._store_room(room_id, room_data)
        # Redis unlock <room_id>

    async def leave_room(self, user_id: str) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        # Redis lock <room_id>
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        self._remove_user_from_room(room_data, user_id)
        self.users_[user_id] = -1
        await self._store_room(room_id, room_data)

    async def join_room(self, user_id: str, room_id: int) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        # Redis lock <room_id>
        room_data = await self._load_room(room_id)

        if room_data["vote_started"] is True:
            raise Exception("OH GOD WHY PLEASE STOP I BEG YOU AAAAA")

        self._add_user_to_room(room_data, user_id)
        self.users_[user_id] = room_id
        await self._store_room(room_id, room_data)
        # Redis unlock <room_id>

    async def current_option(self, user_id: str):
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        return room_data["options"][self._get_user_current_option_index(user_id, room_data)], room_data["match"]
        # Redis unlock <room_id>

    async def get_match(self, user_id: str) -> typing.Optional[entry.ProviderEntry]:
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        return room_data["match"]

    async def reset_match(self, user_id: str):
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        room_data["match"] = None
        await self._store_room(room_id, room_data)

    async def vote(self, user_id: str, is_liked: bool):
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if is_liked:
            await self._like_option(user_id, room_data)
        self._progress_user(user_id, room_data)
        await self._store_room(room_id, room_data)

    async def start_vote(self, user_id: str) -> None:
        """Only owner of the room can call this"""
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if providers.ProviderKind(room_data["params"]["provider_name"]) != providers.ProviderKind.CUSTOM:
            provider = self.providers_.get(providers.ProviderKind(room_data["params"]["provider_name"]))
            if not provider:
                raise Exception("AAAAAAA")
            options = await provider.get_entries({"filters": room_data["params"]["filters"], "exclude_names": []})

            random.shuffle(options)
            room_data["options"] += options
        else:
            # All options should be already set
            if len(room_data["options"]) == 0:
                 raise Exception("WHERE'S VOTES LOBOWSKI????")

        room_data["options_likes"] = {i: set() for i in range(len(room_data["options"]))}

        if room_data["vote_started"] is True or room_data["owner"] != user_id:
            raise Exception("OH GOD WHY PLEASE STOP I BEG YOU AAAAA")

        logging.info("STARTED")
        room_data["vote_started"] = True

        room_data["options_orders"] = {id: self._reshuffle_options(room_data) for id in room_data["participants"]}
        await self._store_room(room_id, room_data)
        logging.info("STORED")
        # Redis unlock <room_id>

    def _get_user_current_option_index(self, user_id: str, room_data: RoomData) -> int:
        return room_data["options_orders"][user_id][
            room_data["participants_positions"][user_id]
        ]

    async def _like_option(self, user_id: str, room_data: RoomData):
        option_index = self._get_user_current_option_index(user_id, room_data)
        room_data["options_likes"][option_index].add(user_id)

        if len(room_data["options_likes"][option_index]) >= len(room_data["participants"]) and room_data["match"] is None:
            option = room_data["options"][option_index]
            logging.info("match: " + option["name"])
            room_data["match"] = option

    def _progress_user(self, user_id: str, room_data: RoomData):
        room_data["participants_positions"][user_id] += 1

        # if no options left then reshuffle them and give again
        if room_data["participants_positions"][user_id] == len(room_data["options_orders"][user_id]):
            room_data["participants_positions"][user_id] = 0
            room_data["options_orders"][user_id] = self._reshuffle_options(room_data)

    def _create_empty_room(self) -> RoomData:
        return copy.deepcopy(EMPTY_ROOM)  # type: ignore

    def _add_user_to_room(self, room_data: RoomData, user_id: str):
        room_data["participants"].add(user_id)
        room_data["participants_positions"][user_id] = 0

    def _remove_user_from_room(self, room_data: RoomData, user_id: str):
        room_data["participants"].remove(user_id)
        del room_data["participants_positions"][user_id]

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

    def _reshuffle_options(self, room_data: RoomData) -> list:
        def divide_chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i + n]

        def get_shuffled():
            indexes = list(range(len(room_data["options"])))
            chunks = [random.shuffle(chunk) or chunk for chunk in divide_chunks(indexes, 10)]
            indexes = list(itertools.chain.from_iterable(chunks))
            return indexes

        return get_shuffled()
