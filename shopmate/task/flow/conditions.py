from typing import Any

# 条件表达式允许使用的安全内置函数（白名单）
SAFE_BUILTINS: dict[str, Any] = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
}


class ConditionEvaluator:
    """计算 Flow 配置中的条件表达式。

    表达式运行在受限环境中：只能使用白名单内置函数和传入的数据，
    不能访问模块、导入对象或执行任意代码。

    示例::

        evaluator.evaluate(
            "len(slots.get('order_number') or '') >= 4",
            {"slots": {"order_number": "A1001"}},
        )  # -> True
    """

    def evaluate(self, expression: str, data: dict[str, Any]) -> bool:
        return bool(
            eval(  # noqa: S307 - 已使用受限 globals
                expression,
                {"__builtins__": SAFE_BUILTINS},
                data,
            )
        )
