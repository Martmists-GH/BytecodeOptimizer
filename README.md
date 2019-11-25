# BytecodeOptimizer

This library provides methods to optimize your code automatically.

### Usage

```py
# __future imports above here
from bytecode_optimizer import enable, optimized, Flags
Flags.TAIL_CALL_OPTIMIZATION = False  # Disable TCO

# Optimize a function you made yourself ...
# this function optimizes to `return 8`, removing all variables
@optimized
def abc():
    x = 2
    b = 3
    if x:
        x = 7
        y = 1
        return x + y

# ... or optimize an entire module:
enable()
# all other imports and code below here
```

Note that it will not optimize any code in the current scope with `enable()`, only modules imported after the enable call.
