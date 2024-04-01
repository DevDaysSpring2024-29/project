import typing

from models import entry
from providers import interface as providers


class DummyProvider(providers.ProviderInterface):
    async def get_entries(self, params: providers.ProviderParams) -> list[entry.ProviderEntry]:
        return [
            entry.ProviderEntry(
                name="dummy entry",
                descr=None,
                rating=None,
                price=None,
                picture_url=None,
            )
        ]


async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    return DummyProvider()
