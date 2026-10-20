from pathlib import Path

import pytest

from shopmate.task.flow.loader import FlowLoader

FLOW_FILE = (
    Path(__file__).resolve().parents[1]
    / "shopmate"
    / "flow_config"
    / "user_flows.yml"
)


@pytest.fixture
def flows():
    return FlowLoader().load(FLOW_FILE)
