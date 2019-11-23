# Stdlib
from types import FunctionType

# Project Internals
from bytecode_optimizer._import_loader import enable
from bytecode_optimizer._optimizer import Flags, optimize_code

__all__ = ("enable", "optimized", "Flags")


def optimized(func: FunctionType) -> FunctionType:
    code = func.__code__
    for _ in range(Flags.OPTIMIZE_ITERATIONS):
        code = optimize_code(code)
    func.__code__ = code
    return func
