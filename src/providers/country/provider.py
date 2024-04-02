import typing

import httpx

from models import entry
from providers import interface as providers


class CountryProvider(providers.ProviderInterface):
    def __init__(self, overpass_url: str):
        self.overpass_url = overpass_url
        self.query = ('/* Get list of countries in Russian. */'
                      '[out:csv("name:ru")];relation["admin_level"="2"]'
                      '[boundary=administrative][type!=multilinestring];out;')

    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:

        async with httpx.AsyncClient() as client:
            r = await client.post(self.overpass_url, data=self.query)

            data = [elem for elem in r.text.split('\n')[1:]]
            return [
                entry.ProviderEntry(
                    name=element,
                    descr=None,
                    rating=None,
                    price=None,
                    picture_url=None,
                )
                for element in data if len(element) > 0
            ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return CountryProvider("https://maps.mail.ru/osm/tools/overpass/api/interpreter")