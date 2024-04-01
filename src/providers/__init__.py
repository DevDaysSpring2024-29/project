import typing

from . import interface
from .dummy import provider as dummy
from .kinopoisk import provider as kinopoisk


async def get_providers(config: typing.Dict[str, str]) -> typing.Dict[interface.ProviderKind, interface.ProviderInterface]:

    return {
        interface.ProviderKind.DUMMY: await dummy.get_provider(config),
        interface.ProviderKind.KINOPOISK: await kinopoisk.get_provider(config),
    }
