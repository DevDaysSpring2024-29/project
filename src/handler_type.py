from typing import Callable


__all__ = ["command"]


def command(fun: Callable):
    fun.is_command = True
    return fun


def button(fun: Callable):
    fun.is_button = True
    return fun