from dataclasses import dataclass


@dataclass
class FlowStepLink:
    """Step 之间的连接。"""

    target: str


@dataclass
class StaticLink(FlowStepLink):
    """直接跳转。"""

    pass


@dataclass
class ConditionalLink(FlowStepLink):
    """条件成立时跳转，对应配置中的 if / then。"""

    condition: str


@dataclass
class FallbackLink(FlowStepLink):
    """条件都不成立时跳转，对应配置中的 else。"""

    pass
