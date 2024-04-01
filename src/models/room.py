import typing


class RoomParams(typing.TypedDict):
    provider_name: str
    filters: dict[str, int | str]
