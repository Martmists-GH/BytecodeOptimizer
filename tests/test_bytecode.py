import dis

from bytecode_optimizer import optimized


@optimized
def main():
    x = 10
    y = 20
    z = x + y
    return z


def main_unoptimized():
    x = 10
    y = 20
    z = x + y
    return z


if __name__ == "__main__":
    main()
    dis.dis(main)
