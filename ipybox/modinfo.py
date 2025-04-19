import importlib
from dataclasses import dataclass
from inspect import getfile, getsource
from pathlib import Path, PurePath, PurePosixPath


@dataclass
class ModuleInfo:
    name: str
    relpath: PurePath
    source: str


def get_module_info(module_name: str) -> ModuleInfo:
    module = importlib.import_module(module_name)
    module_path = Path(getfile(module))

    relscope = PurePosixPath(module_name.replace(".", "/"))

    if module_path.name == "__init__.py":
        relpath = relscope / "__init__.py"
    else:
        relpath = relscope.with_suffix(".py")

    try:
        code = getsource(module)
    except OSError:
        code = ""

    return ModuleInfo(name=module.__name__, relpath=relpath, source=code)
