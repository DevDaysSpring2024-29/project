import typing

from . import interface
from .dummy import provider as dummy


async def get_providers(config: typing.Dict[str, str]) -> typing.Dict[interface.ProviderKind, interface.ProviderInterface]:

    return {
        interface.ProviderKind.DUMMY: await dummy.get_provider(config)
    }
