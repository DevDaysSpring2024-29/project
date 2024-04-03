import typing

import httpx

from models import entry
from providers import interface as providers


class KinopoiskProvider(providers.ProviderInterface):
    def __init__(self, token: str):
        self.token = token

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:
        headers = {
            'x-api-key': self.token,
        }

        async with httpx.AsyncClient() as client:
            r = await client.get('https://kinopoiskapiunofficial.tech/api/v2.2/films/premieres?year=2024&month=JANUARY', headers=headers)

            data = r.json()
            return [
                entry.ProviderEntry(
                    name=item["nameRu"],
                    descr=item["webUrl"],
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for item in data["items"]
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return KinopoiskProvider(config["KINOPOISK_TOKEN"])
