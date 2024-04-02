import typing

import httpx

from models import entry
from providers import interface as providers


class CityProvider(providers.ProviderInterface):
    def __init__(self, overpass_url: str):
        self.overpass_url = overpass_url
        self.query = ('/* Get list of cities in Russian. */'
                      '[out:json];area[name="Россия"];(node[place="city"](area););out;')

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:

        async with httpx.AsyncClient() as client:
            r = await client.post(self.overpass_url, data=self.query)

            data = [element['tags']["name:ru"] for element in r.json()['elements']]
            return [
                entry.ProviderEntry(
                    name=element,
                    descr=None,
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for element in data
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return CityProvider("https://maps.mail.ru/osm/tools/overpass/api/interpreter")