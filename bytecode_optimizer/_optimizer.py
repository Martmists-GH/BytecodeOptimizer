# Stdlib
from dis import dis, opmap, hasjabs, hasjrel, hasname, hasconst, haslocal, stack_effect
import operator
from struct import pack
from types import CodeType
from typing import T, Any, List, Tuple, Sequence, Generator


class Flags:
    DEBUG = False
    REMOVE_UNUSED_VARS = True
    TAIL_CALL_OPTIMIZATION = True
    OPTIMIZE_ACCESSORS = True
    OPTIMIZE_NAMES = True
    OPTIMIZE_ITERATIONS = 3


def debug(*args):
    if Flags.DEBUG:
        print(*args)


def dump(ops: List[Tuple[int, int, int]]):
    if Flags.DEBUG:
        print("-" * 50)
        dis(b"".join(pack("BB", op[0], op[1]) for op in ops))


def iter_size(it: Sequence[T],
              size: int) -> Generator[Sequence[T], None, None]:
    index = 0
    while index < len(it) - size:
        yield it[index:index + size]
        index += 1


def is_name_used_upper(name: str, code: CodeType) -> bool:
    return name not in code.co_varnames


def remove_unused_variables(ops: List[Tuple[int, int, int]],
                            code: CodeType) -> List[Tuple[int, int, int]]:
    found = True
    continuefrom = 0
    while found:
        copy_ops = ops[continuefrom:]
        found = False
        stored = None
        stored_index = 0
        for i, op in enumerate(copy_ops):
            i = i + continuefrom
            if stored is None and op[0] in (opmap["STORE_FAST"],
                                            opmap["STORE_NAME"]):
                if op[0] == opmap["STORE_FAST"]:
                    if not is_name_used_upper(code.co_varnames[op[1]], code):
                        debug(f"Checking: {op}")
                        stored = op
                        stored_index = i
                elif op[0] == opmap["STORE_NAME"]:
                    if not is_name_used_upper(code.co_names[op[1]], code):
                        debug(f"Checking: {op}")
                        stored = op
                        stored_index = i

            elif stored and op[0] in (*haslocal, *hasname):
                if op[1] == stored[1]:
                    if op[0] == stored[0]:  # Same store
                        debug(f"Found overriding store {op} for {stored}")
                        # Useless variable
                        ops[stored_index] = (opmap["POP_TOP"], 0, stored[2])
                        continuefrom = stored_index + 1
                        found = True
                        break
                    if ((op[0] in haslocal
                         and stored[0] == opmap["STORE_FAST"])
                            or (op[0] in hasname
                                and stored[0] == opmap["STORE_NAME"])):
                        debug(f"Found load {op} for {stored}")
                        # variable is used
                        continuefrom = stored_index + 1
                        found = True
                        break
        else:
            if stored:
                debug(f"Removing op {stored}")
                ops[stored_index] = (opmap["POP_TOP"], 0, stored[2])
                continuefrom = stored_index + 1
                found = True

    return ops


def clean_pop_top(ops: List[Tuple[int, int, int]]
                  ) -> List[Tuple[int, int, int]]:
    changed = True
    while changed:
        changed = False
        for i, (first, second) in enumerate(zip(ops[:-1], ops[1:])):
            try:
                effect = stack_effect(first[0], first[1])
            except ValueError:
                try:
                    effect = stack_effect(first[0])
                except ValueError:
                    effect = 1
            if effect == 1 and second[0] == opmap["POP_TOP"]:
                del ops[i + 1]
                del ops[i]
                changed = True
                break

    return ops


def inline_single_use_variables(ops: List[Tuple[int, int, int]]
                                ) -> List[Tuple[int, int, int]]:
    changed = True
    while changed:
        changed = False
        for i, new_ops in enumerate(iter_size(ops, 2)):
            if new_ops[0][0] in (opmap["LOAD_NAME"], opmap["LOAD_CONST"],
                                 opmap["LOAD_FAST"]
                                 ) and new_ops[1][0] == opmap["STORE_FAST"]:
                load, store = new_ops
                counter = 0
                s = (0, None)
                for j, op in enumerate(ops[i + 2:]):
                    if op[0] == opmap["LOAD_FAST"] and op[1] == store[1]:
                        s = (i + j + 2, op)
                        counter += 1
                if counter == 1:
                    ops[s[0]] = (load[0], load[1], s[1][2])
                    changed = True
    return ops


def optimize_accessors(ops: List[Tuple[int, int, int]]
                       ) -> List[Tuple[int, int, int]]:
    changed = True
    while changed:
        changed = False
        for i, (first, second) in enumerate(zip(ops[:-1], ops[1:])):
            if first[1] == second[1]:
                if (first[0], second[0]) in ((opmap["STORE_FAST"],
                                              opmap["LOAD_FAST"]),
                                             (opmap["STORE_NAME"],
                                              opmap["LOAD_NAME"])):
                    if not any(arg[:2] == second[:2] for arg in ops[i + 2:]):
                        # Make sure the fast isn't accessed a second time
                        del ops[i + 1]
                        del ops[i]
                        changed = True
                        break
    return ops


def get_stack_size(ops: List[Tuple[int, int, int]]) -> int:
    stack = 0
    max_stack = 0
    for op in ops:
        try:
            stack += stack_effect(op[0], op[1])
        except ValueError:
            try:
                stack += stack_effect(op[0])
            except ValueError:
                stack += 1
        max_stack = max(max_stack, stack)
    return max_stack


def fix_jumps(ops: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
    for i, op in enumerate(ops):
        if op[0] in hasjabs:
            target = [x for x in ops if x[2] >= op[1]
                      ][0]  # if not exists, jump to next instruction
            ops[i] = (op[0], ops.index(target) * 2, op[2])
        elif op[0] in hasjrel:
            target = [x for x in ops if x[2] >= op[1] + op[2]
                      ][0]  # if not exists, jump to next instruction
            ops[i] = (op[0], (ops.index(target) - ops.index(op)) * 2, op[2])
    return ops


def optimize_names(
        opcodes: List[Tuple[int, int, int]], code: CodeType
) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[Any, ...]]:
    accessed_names = []
    accessed_varnames = []
    for i in range(code.co_argcount + code.co_kwonlyargcount):
        accessed_varnames.append(code.co_varnames[i])
    accessed_consts = []
    for op in opcodes:
        if op[0] in hasname and code.co_names[op[1]] not in accessed_names:
            accessed_names.append(code.co_names[op[1]])
        elif op[0] in haslocal and code.co_varnames[
                op[1]] not in accessed_varnames:
            accessed_varnames.append(code.co_varnames[op[1]])
        elif op[0] in hasconst and code.co_consts[
                op[1]] not in accessed_consts:
            accessed_consts.append(code.co_consts[op[1]])

    for i, op in enumerate(opcodes):
        if op[0] in hasname:
            opcodes[i] = (op[0], accessed_names.index(code.co_names[op[1]]),
                          op[2])
        elif op[0] in haslocal:
            opcodes[i] = (op[0],
                          accessed_varnames.index(code.co_varnames[op[1]]),
                          op[2])
        elif op[0] in hasconst:
            opcodes[i] = (op[0], accessed_consts.index(code.co_consts[op[1]]),
                          op[2])

    return tuple(accessed_names), tuple(accessed_varnames), tuple(
        accessed_consts)


def optimize_tco(ops: List[Tuple[int, int, int]],
                 code: CodeType) -> List[Tuple[int, int, int]]:
    ops_copy = ops[:]
    changed = True
    name = code.co_name if "<optimized>" not in code.co_name else code.co_name[
        12:]

    while changed:
        changed = False
        for i, new_ops in enumerate(iter_size(ops_copy, 3)):
            if new_ops[0][0] in (opmap["LOAD_DEREF"], opmap["LOAD_GLOBAL"]):
                names = code.co_names if new_ops[0][0] == opmap[
                    "LOAD_GLOBAL"] else list(code.co_freevars) + list(
                        code.co_cellvars)
                if names[new_ops[0][1]] == name:
                    for j, (op,
                            op2) in enumerate(iter_size(ops_copy[i + 3:], 2)):
                        if op[0] == opmap["CALL_FUNCTION"] and op2[0] == opmap[
                                "RETURN_VALUE"]:
                            nargs = op[1]
                            added_ops = []
                            for k in reversed(range(nargs)):
                                added_ops.append(
                                    (opmap["STORE_FAST"], k, op[2]))
                            added_ops.append(
                                (opmap["JUMP_ABSOLUTE"], 0, op2[2]))
                            ops_copy[i + j + 3:i + j + 5] = added_ops
                            changed = True
                            break

    return ops_copy


def nested_tco(ops: List[Tuple[int, int, int]],
               code: CodeType) -> Tuple[Any, ...]:
    consts = list(code.co_consts)

    for i, new_ops in enumerate(iter_size(ops, 4)):
        if new_ops[0][0] == opmap["MAKE_FUNCTION"]:
            for op in ops[i + 4:]:
                if op[0] == opmap["STORE_NAME"] and op[1] == new_ops[3][1]:
                    # dont optimize
                    break
            else:
                # optimize
                new_code = consts[ops[i - 2][1]]
                opcodes = [
                    *zip(new_code.co_code[::2], new_code.co_code[1::2],
                         range(0, int(len(new_code.co_code)), 2))
                ]
                opcodes = optimize_tco(opcodes, new_code)
                co_code = b"".join(pack("BB", op[0], op[1]) for op in opcodes)
                code = CodeType(new_code.co_argcount,
                                new_code.co_kwonlyargcount,
                                new_code.co_nlocals, new_code.co_stacksize,
                                new_code.co_flags, co_code, new_code.co_consts,
                                new_code.co_names, new_code.co_varnames,
                                new_code.co_filename, new_code.co_name,
                                new_code.co_firstlineno, new_code.co_lnotab,
                                new_code.co_freevars, new_code.co_cellvars)
                consts[ops[i - 2][1]] = code
    return tuple(consts)


def fix_const_ops(ops: List[Tuple[int, int, int]], code: CodeType
                  ) -> Tuple[List[Tuple[int, int, int]], Tuple[Any, ...]]:
    consts = list(code.co_consts)
    changed = True
    while changed:
        changed = False
        for i, new_ops in enumerate(iter_size(ops, 3)):
            c1, c2, op = new_ops
            if c1[0] == c2[0] == opmap["LOAD_CONST"]:
                c1v, c2v = consts[c1[1]], consts[c2[1]]
                opname = [k for k, v in opmap.items() if v == op[0]][0]
                if opname.startswith("INPLACE") or opname.startswith("BINARY"):
                    func_name = opname.split("_", 1)[1].replace("_",
                                                                "").lower()
                    value = getattr(operator, func_name)(c1v, c2v)
                    if value not in consts:
                        consts.append(value)
                    changed = True
                    ops[i:i + 3] = [(opmap["LOAD_CONST"], consts.index(value),
                                     op[2])]
                    break
                if op[0] == opmap["COMPARE_OP"]:
                    try:
                        f = [
                            operator.lt, operator.le, operator.eq, operator.ne,
                            operator.gt, operator.ge
                        ][op[1]]
                    except IndexError:
                        continue
                    else:
                        value = f(c1v, c2v)
                        if value not in consts:
                            consts.append(value)
                        changed = True
                        ops[i:i + 3] = [(opmap["LOAD_CONST"],
                                         consts.index(value), op[2])]
                        break
            elif c1[0] == opmap["LOAD_CONST"] and c2[0] in (
                    114, 115):  # POP_JUMP_IF_X
                changed = True
                if consts[c1[1]] ^ c2[0] == opmap["POP_JUMP_IF_TRUE"]:
                    # No jump
                    ops[i:i + 2] = []
                else:
                    # Jump
                    target = [x for x in ops if x[2] >= c2[1]][0]
                    pos = ops.index(target)
                    ops[i:pos] = []

    return ops, tuple(consts)


def remove_after_return(ops: List[Tuple[int, int, int]]
                        ) -> List[Tuple[int, int, int]]:
    for i, op in enumerate(ops):
        if op[0] == opmap["RETURN_VALUE"]:
            for op_ in ops[:i]:
                if op_[0] in hasjabs:
                    target = [x for x in ops if x[2] >= op_[1]][0]
                elif op_[0] in hasjrel:
                    target = [x for x in ops if x[2] >= op_[1] + op_[2]][0]
                else:
                    continue
                if target[2] > op[2]:
                    break
            else:
                ops[i + 1:] = []
    return ops


def optimize_code(code: CodeType) -> CodeType:
    co_argcount = None
    co_kwonlyargcount = None
    co_nlocals = None
    co_flags = None
    co_filename = None
    co_names = None
    co_varnames = None
    co_name = "<optimized> " + code.co_name if not code.co_name.startswith(
        "<") else "<optimized " + code.co_name[1:]
    co_firstlineno = None
    co_lnotab = None
    co_freevars = None
    co_cellvars = None

    opcodes = [
        *zip(code.co_code[::2], code.co_code[1::2],
             range(0, int(len(code.co_code)), 2))
    ]
    co_consts = tuple(
        (const if not isinstance(const, CodeType) else optimize_code(const))
        for const in code.co_consts)
    # We do this to optimize out all nested code consts first
    code = CodeType(code.co_argcount, code.co_kwonlyargcount, code.co_nlocals,
                    code.co_stacksize, code.co_flags, code.co_code, co_consts,
                    code.co_names, code.co_varnames, code.co_filename,
                    code.co_name, code.co_firstlineno, code.co_lnotab,
                    code.co_freevars, code.co_cellvars)

    if Flags.REMOVE_UNUSED_VARS:
        opcodes = inline_single_use_variables(opcodes)
        opcodes = remove_unused_variables(opcodes, code)
        opcodes = clean_pop_top(opcodes)

    if Flags.TAIL_CALL_OPTIMIZATION:
        co_consts = nested_tco(opcodes, code)
        code = CodeType(code.co_argcount, code.co_kwonlyargcount,
                        code.co_nlocals, code.co_stacksize, code.co_flags,
                        code.co_code, co_consts, code.co_names,
                        code.co_varnames, code.co_filename, code.co_name,
                        code.co_firstlineno, code.co_lnotab, code.co_freevars,
                        code.co_cellvars)

    if Flags.OPTIMIZE_ACCESSORS:
        opcodes = optimize_accessors(opcodes)
        opcodes, co_consts = fix_const_ops(opcodes, code)
        opcodes = remove_after_return(opcodes)
        code = CodeType(code.co_argcount, code.co_kwonlyargcount,
                        code.co_nlocals, code.co_stacksize, code.co_flags,
                        code.co_code, co_consts, code.co_names,
                        code.co_varnames, code.co_filename, code.co_name,
                        code.co_firstlineno, code.co_lnotab, code.co_freevars,
                        code.co_cellvars)
        opcodes = clean_pop_top(opcodes)

    opcodes = fix_jumps(opcodes)

    if Flags.OPTIMIZE_NAMES:
        co_names, co_varnames, co_consts = optimize_names(opcodes, code)

    co_stacksize = get_stack_size(opcodes)

    co_code = b"".join(pack("BB", op[0], op[1]) for op in opcodes)
    return CodeType(co_argcount or code.co_argcount, co_kwonlyargcount
                    or code.co_kwonlyargcount, co_nlocals or code.co_nlocals,
                    co_stacksize or code.co_stacksize, co_flags
                    or code.co_flags, co_code or code.co_code, co_consts
                    or code.co_consts, co_names or code.co_names, co_varnames
                    or code.co_varnames, co_filename or code.co_filename,
                    co_name or code.co_name, co_firstlineno
                    or code.co_firstlineno, co_lnotab or code.co_lnotab,
                    co_freevars or code.co_freevars, co_cellvars
                    or code.co_cellvars)
