import enum
import typing

from models import entry


class ProviderParams(typing.TypedDict):
    filters: dict[str, int | str]
    exclude_names: list[str]


class ProviderInterface(typing.Protocol):
    async def get_entries(self, params: ProviderParams) -> list[entry.ProviderEntry]:
        ...


class ProviderKind(enum.StrEnum):
    DUMMY = "dummy"
    KINOPOISK = "kinopoisk"
    RESTAURANTS = "restaurants"
    COUNTRY = "country"
    CITY = "city"
    CUSTOM = "custom"
