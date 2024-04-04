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
            
            result: list[entry.ProviderEntry] = []
            for item in data["items"]:
                premiere_r = await client.get(f'https://kinopoiskapiunofficial.tech/api/v2.2/films/{item["kinopoiskId"]}', headers=headers)
                premiere_data = premiere_r.json()
                descr: str = f'Рейтинг: {premiere_data.get("ratingKinopoisk", "Отсутствует")}\n' \
                             + f'Год: {premiere_data.get("year", "Неизвестен")}\n' \
                             + f'Жанры: {", ".join([d["genre"] for d in premiere_data.get("genres", [{"genre": "Отсутствует"}])])}\n' \
                             + premiere_data.get("webUrl", None)
                
                result.append(
                    entry.ProviderEntry(
                        name=item["nameRu"],
                        descr=descr,
                        rating=None,
                        price=None,
                        picture_url=None,
                    )
                )

            return result


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return KinopoiskProvider(config["KINOPOISK_TOKEN"])
