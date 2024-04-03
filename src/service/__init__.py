import typing

import redis.asyncio as redis

import providers
from . import service
from . import interface


async def get_service(config: typing.Dict[str, str]) -> interface.ServiceInterface:
    # storage = redis.Redis(host=config["REDIS_HOST"], port=config["REDIS_PORT"], password=config["REDIS_PASSWORD"])
    storage = None
    p = await providers.get_providers(config)
    s = service.Service(storage, p)
    return s
