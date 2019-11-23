import dis

from bytecode_optimizer import enable
enable()
from tests.test_bytecode import main_unoptimized as main

if __name__ == "__main__":
    main()
    dis.dis(main)
