import asyncio
import copy
import json
from logging import log
import logging
import random
import typing
import itertools

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
    
    "provider_name": None,
    "filters": [],

    "participants": [],
    "participants_positions": [],
    "participants_callbacks": [],

    "options": [],
    "options_likes": [],
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
        self.next_room_id_ = 0

    async def create_room(self, user_id: str, params: room.RoomParams, callback: interface.CallbackType) -> int:
        """Callback is called when people are joining group. And will be called then voting is started and is finished and room is closed"""
        room_id = await self._generate_room_id()
        room_data = self._create_empty_room()
        self._add_user_to_room(room_data, user_id, callback)
        self.users_[user_id] = room_id
        room_data["owner"] = user_id
        room_data["provider_name"] = params["provider_name"]
        room_data["filter"] = params["filters"]

        logging.info(room_data)

        await self._store_room(room_id, room_data)
        return room_id

    async def join_room(self, user_id: str, room_id: int, callback: interface.CallbackType) -> None:
        """Will be called then voting is started and is finished and room is closed. Active only is voting is not started"""
        # Redis lock <room_id>
        room_data = await self._load_room(room_id)
        self._add_user_to_room(room_data, user_id, callback)
        await self._store_room(room_id, room_data)
        # Redis unlock <room_id>

    async def close_room(self, user_id: str, room_id: int) -> None:
        """Will be called to close room when voting is finished"""
        # Redis lock <room_id>
        await self._remove_users_room(user_id, room_id)
        # Redis unlock <room_id>

    async def set_entries(self, user_id: str, room_id: int, entries: typing.List[entry.ProviderEntry]) -> None:
        return await super().set_entries(user_id, room_id, entries)
    
    async def add_entry(self, user_id: str, room_id: int, entry: entry.ProviderEntry) -> None:
        """Will add custom entry"""
        # Redis lock <room_id>
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if room_data["vote_started"] is True or room_data["owner"] != user_id:
            raise Exception("A? A? A? A? A? A? A? A? A? A? A? A? A? A? A? A?")
        room_data["options"].append(entry)
        await self._store_room(room_id, room_data)
        # Redis unlock <room_id>

    async def start_vote(self, user_id: str) -> None:
        """Only owner of the room can call this"""
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if providers.ProviderKind[room_data["provider_name"]] != providers.ProviderKind.CUSTOM:
            provider = self.providers_.get(providers.ProviderKind[room_data["provider_name"]])
            if not provider:
                raise Exception("AAAAAAA")
            options = await provider.get_entries({"filters": room_data["filters"], "exclude_names": []})

            room_data["options"] = options
        else:
            # All options should be already set
            if len(room_data["options"]) == 0:
                 raise Exception("WHERE'S VOTES LOBOWSKI????")

        room_data["options_likes"] = [set()] * len(room_data["options"])

        if room_data["vote_started"] is True or room_data["owner"] != user_id:
            raise Exception("OH GOD WHY PLEASE STOP I BEG YOU AAAAA")
        room_data["vote_started"] = True

        room_data["options_orders"] = {i: self._reshuffle_options(room_data) for i in range(len(room_data["participants"]))}
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
        # Redis lock <room_id>
        room_id = await self._get_users_room(user_id)
        room_data = await self._load_room(room_id)
        if not room_data["vote_started"]:
            raise Exception("MAKE IT STOP MAKE IT STOP")
        user_index = self._get_user_index(user_id, room_data)
        if is_liked:
            await self._like_option(user_index, room_data, user_id)
        await self._store_room(room_id, room_data)
        return self._progress_user(user_index, room_data, user_id)
        # Redis unlock <room_id>

    def _get_user_index(self, user_id: str, room_data: RoomData) -> int:
        return room_data["participants"].index(user_id)

    def _get_user_current_option_index(self, user_index: int, room_data: RoomData) -> int:
        return room_data["options_orders"][user_index][
                room_data["participants_positions"][user_index]
            ]

    async def _like_option(self, user_index: int, room_data: RoomData, user_id: str):
        option_index = self._get_user_current_option_index(user_index, room_data)
        room_data["options_likes"][option_index].add(user_id)

        if len(room_data["options_likes"][option_index]) == len(room_data["participants"]):
            option = room_data["options"][option_index]
            await asyncio.gather(
                *(
                    callback(option, True)
                    for callback in room_data["participants_callbacks"]
                )
            )

    def _progress_user(self, user_index: int, room_data: RoomData, user_id: str) -> entry.ProviderEntry:
        # To-do: check if reached final option and load more
        room_data["participants_positions"][user_index] += 1

        # if no options left then reshuffle them and give again
        if room_data["participants_positions"][user_index] == len(room_data["options_orders"][user_index]):
            room_data["participants_positions"][user_index] = 0
            # also remove all likes for user
            for set_of_likes in room_data["options_likes"]:
                if user_id in set_of_likes:
                    set_of_likes.remove(user_id)
            room_data["options_orders"][user_index] = self._reshuffle_options(room_data)

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
        self.users_[user_id] = room_id

    async def _remove_users_room(self, user_id: str, room_id: int):
        self.users_.pop(user_id)
        self.rooms_.pop(room_id)

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
            chunks = [random.shuffle(chunk) or chunk for chunk in divide_chunks(indexes, 4)]
            indexes = list(itertools.chain.from_iterable(chunks))
            return indexes
        
        return get_shuffled()
