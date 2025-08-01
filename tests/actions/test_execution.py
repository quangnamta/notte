import asyncio
from dataclasses import dataclass

import pytest
from notte_browser.session import NotteSession

from tests.mock.mock_service import MockLLMService
from tests.mock.mock_service import patch_llm_service as _patch_llm_service

patch_llm_service = _patch_llm_service


@pytest.fixture
def headless() -> bool:
    return True


@dataclass
class StepArgs:
    type: str
    action_id: str
    value: str | None
    enter: bool = False


@dataclass
class ExecutionTest:
    url: str
    steps: list[StepArgs]


@pytest.fixture
def mock_llm_service() -> MockLLMService:
    return MockLLMService(mock_response="")


@pytest.fixture
def phantombuster_login() -> ExecutionTest:
    return ExecutionTest(
        url="https://phantombuster.com/login",
        steps=[
            StepArgs(type="click", action_id="B4", value=None, enter=False),
            StepArgs(type="fill", action_id="I1", value="lucasgiordano@gmail.com", enter=False),
            StepArgs(type="fill", action_id="I2", value="lucasgiordano", enter=False),
            StepArgs(type="click", action_id="B2", value=None, enter=False),
        ],
    )


async def _test_execution(test: ExecutionTest, headless: bool, patch_llm_service: MockLLMService) -> None:
    async with NotteSession(
        headless=headless,
        enable_perception=False,
    ) as page:
        _ = await page.aobserve(test.url)
        for step in test.steps:
            if not page.snapshot.dom_node.find(step.action_id):
                inodes = [(n.id, n.text) for n in page.snapshot.interaction_nodes()]
                raise ValueError(f"Action {step.action_id} not found in context with interactions {inodes}")
            _ = await page.astep(type=step.type, action_id=step.action_id, value=step.value, enter=step.enter)
            _ = await page.aobserve()


def test_execution(phantombuster_login: ExecutionTest, headless: bool, patch_llm_service: MockLLMService) -> None:
    asyncio.run(_test_execution(phantombuster_login, headless, patch_llm_service))
