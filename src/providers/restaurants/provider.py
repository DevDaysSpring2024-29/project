import typing

import httpx

from models import entry
from providers import interface as providers


class RestaurantsProvider(providers.ProviderInterface):
    def __init__(self, overpass_url: str):
        self.overpass_url = overpass_url
        self.query_template = '[out:json];node["amenity"="restaurant"](around:1000,{latitude},{longitude});out {limit};'

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:
        # TODO: remove hardcoded values
        latitude: float = 55.751999
        longitude: float = 37.617734
        query: str = self.query_template.format(latitude=latitude, longitude=longitude, limit=20)
        
        async with httpx.AsyncClient() as client:
            r = await client.post(self.overpass_url, data=query)

            data = r.json()
            return [
                entry.ProviderEntry(
                    name=element['tags']['name'],
                    descr=None,
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for element in data['elements'] if 'tags' in element and 'name' in element['tags']
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return RestaurantsProvider("https://maps.mail.ru/osm/tools/overpass/api/interpreter")