import typing

from . import interface
from .dummy import provider as dummy
from .kinopoisk import provider as kinopoisk
from .restaurants import provider as restaurants
from .country import provider as country
from .city import provider as city
from .city import provider as custom


async def get_providers(config: typing.Dict[str, str]) -> typing.Dict[interface.ProviderKind, interface.ProviderInterface]:

    return {
        interface.ProviderKind.DUMMY: await dummy.get_provider(config),
        interface.ProviderKind.KINOPOISK: await kinopoisk.get_provider(config),
        interface.ProviderKind.RESTAURANTS: await restaurants.get_provider(config),
        interface.ProviderKind.COUNTRY: await country.get_provider(config),
        interface.ProviderKind.CITY: await city.get_provider(config),
        interface.ProviderKind.CUSTOM: await custom.get_provider(config)
    }
