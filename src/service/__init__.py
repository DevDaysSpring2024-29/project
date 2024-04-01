import typing

import providers
from . import service
from . import interface


async def get_service(config: typing.Dict[str, str]) -> interface.ServiceInterface:
    p = await providers.get_providers(config)
    s = service.Service(p)
    return s
