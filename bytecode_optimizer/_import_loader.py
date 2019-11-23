# Stdlib
import dis
from importlib._bootstrap_external import FileFinder, SourceLoader
import sys

# Project Internals
from bytecode_optimizer._optimizer import optimize_code, Flags


class ByteOptimizerLoader(SourceLoader):
    def __init__(self, *args):
        self.module, self.path = args

    def get_filename(self, _):
        return self.path

    def get_data(self, _):
        with open(self.path, "rb") as fp:
            return fp.read()

    def source_to_code(self, data, path='<string>', **_):
        code = SourceLoader.source_to_code(self, data, path)
        # is_site_package_or_local = ("python" not in self.path or "site-packages" in self.path)
        excluded_modules = ("six", )
        if b"# no-optimize" not in data and not self.module.startswith(
                "_") and self.module not in excluded_modules:
            # Don't optimize python internals or files marked
            # with `# no-optimize` anywhere in the file
            for _ in range(Flags.OPTIMIZE_ITERATIONS):
                code = optimize_code(code)
        return code

    @classmethod
    def enable(cls):
        loader_opts = [cls, [".py"]]
        sys.path_hooks.insert(0, FileFinder.path_hook(loader_opts))
        for k, v in sys.path_importer_cache.copy().items():
            if isinstance(v, FileFinder) and ("python3" not in v.path
                                              or "site-packages" in v.path):
                # Don't modify stdlib
                del sys.path_importer_cache[k]


def enable():
    ByteOptimizerLoader.enable()
