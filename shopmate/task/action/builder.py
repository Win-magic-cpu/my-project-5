import importlib
import inspect
import pkgutil

from shopmate.task.action.base import Action
from shopmate.task.action.registry import ActionRegistry
from shopmate.task.action.runner import ActionRunner


def register_custom_actions(registry: ActionRegistry) -> None:
    """扫描 shopmate.task.action.custom 包，自动实例化并注册 Action。

    新增业务 Action 时只需在 custom 包中新建模块，无需改动注册代码。
    """
    package = importlib.import_module("shopmate.task.action.custom")

    for _, module_name, is_package in pkgutil.iter_modules(
        package.__path__,
        prefix=f"{package.__name__}.",
    ):
        if is_package:
            continue

        module = importlib.import_module(module_name)
        for _, action_class in inspect.getmembers(
            module,
            inspect.isclass,
        ):
            if (
                not issubclass(action_class, Action)
                or action_class is Action
            ):
                continue
            if action_class.__module__ != module.__name__:
                continue
            registry.register(action_class())


def build_action_runner() -> ActionRunner:
    registry = ActionRegistry()
    register_custom_actions(registry)
    return ActionRunner(registry)
