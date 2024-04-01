import typing


class ProviderEntry(typing.TypedDict):
    name: str
    descr: str | None
    rating: float | None  # in [0.0 : 1.0]
    price: int | None  # In rubles
    picture_url: str | None
