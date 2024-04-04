import typing

import httpx

from models import entry
from providers import interface as providers


class RestaurantsProvider(providers.ProviderInterface):
    def __init__(self, overpass_url: str):
        self.overpass_url = overpass_url
        self.query_template = "[out:json];area[name='{city}']->.searchArea;node[amenity={amenity_type}](area.searchArea);out {limit};"
        self.ref_template = "https://yandex.com/maps?whatshere[point]={lng},{lat}"

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:
        # TODO: remove hardcoded values
        query: str = self.query_template.format(city='Москва', amenity_type='restaurant', limit=20)

        async with httpx.AsyncClient() as client:
            r = await client.get(self.overpass_url, params={'data': query})

            data = r.json()
            return [
                entry.ProviderEntry(
                    name=element['tags']['name'],
                    descr=f"На карте: {self.ref_template.format(lat=element['lat'], lng=element['lon'])}",
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for element in data['elements'] if 'tags' in element and 'name' in element['tags']
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return RestaurantsProvider("https://maps.mail.ru/osm/tools/overpass/api/interpreter")
