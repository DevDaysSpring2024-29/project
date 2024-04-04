import typing

from providers import interface as providers

async def get_provider(config: typing.Dict[str, str]) -> providers.ProviderInterface:
    raise Exception("THIS ONE SHOULDN'T BE REALLY CALLED. IT'S JUST BOGUS")
