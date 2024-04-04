import typing

import httpx

from models import entry
from providers import interface as providers


class CityProvider(providers.ProviderInterface):
    def __init__(self, overpass_url: str):
        self.overpass_url = overpass_url
        self.query = ('/* Get list of cities in Russian. */'
                      "[out:json];area[name='Россия']->.russia;(node[place=city](area.russia););out 30;")
        self.ref_template = "https://maps.yandex.ru/?text={lat}+{lng}"

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:

        async with httpx.AsyncClient() as client:
            r = await client.get(self.overpass_url, params={'data': self.query}, timeout=None)

            return [
                entry.ProviderEntry(
                    name=element['tags']["name:ru"],
                    descr=f"На карте: {self.ref_template.format(lat=element['lat'], lng=element['lon'])}",
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for element in r.json()['elements']
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return CityProvider("https://maps.mail.ru/osm/tools/overpass/api/interpreter")