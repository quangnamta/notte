import datetime as dt
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from notte_core.actions import BrowserAction, ClickAction
from notte_core.browser.observation import Observation, StepResult
from notte_core.data.space import DataSpace
from notte_core.space import SpaceCategory
from notte_sdk.client import NotteClient
from notte_sdk.errors import AuthenticationError
from notte_sdk.types import (
    DEFAULT_OPERATION_SESSION_TIMEOUT_IN_MINUTES,
    BrowserType,
    ObserveRequestDict,
    ObserveResponse,
    SessionResponse,
    SessionStartRequestDict,
    StepRequestDict,
)


@pytest.fixture
def api_key() -> str:
    return "test-api-key"


@pytest.fixture
def client(api_key: str) -> NotteClient:
    return NotteClient(
        api_key=api_key,
    )


@pytest.fixture
def mock_response() -> MagicMock:
    return MagicMock()


def test_client_initialization_with_env_vars() -> None:
    client = NotteClient(api_key="test-api-key")
    assert client.sessions.token == "test-api-key"


def test_client_initialization_with_params() -> None:
    client = NotteClient(api_key="custom-api-key")
    assert client.sessions.token == "custom-api-key"


def test_client_initialization_without_api_key() -> None:
    with patch.dict(os.environ, clear=True):
        with pytest.raises(AuthenticationError):
            _ = NotteClient()


@pytest.fixture
def session_id() -> str:
    return "test-session-123"


def session_response_dict(session_id: str, close: bool = False) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "timeout_minutes": DEFAULT_OPERATION_SESSION_TIMEOUT_IN_MINUTES,
        "created_at": dt.datetime.now(),
        "last_accessed_at": dt.datetime.now(),
        "duration": dt.timedelta(seconds=100),
        "status": "closed" if close else "active",
    }


def _start_session(mock_post: MagicMock, client: NotteClient, session_id: str) -> SessionResponse:
    """
    Mocks the HTTP response for starting a session and triggers session initiation.

    Configures the provided mock_post to simulate a successful HTTP response using a session
    dictionary constructed with the given session_id, then calls client.sessions.start() and
    returns its response.
    """
    mock_response = session_response_dict(session_id)
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_response
    return client.sessions.start()


def _stop_session(mock_delete: MagicMock, client: NotteClient, session_id: str) -> SessionResponse:
    mock_response = session_response_dict(session_id, close=True)
    mock_delete.return_value.status_code = 200
    mock_delete.return_value.json.return_value = mock_response
    return client.sessions.stop(session_id)


@patch("requests.post")
@pytest.mark.order(1)
def test_start_session(mock_post: MagicMock, client: NotteClient, api_key: str, session_id: str) -> None:
    session_data: SessionStartRequestDict = {
        "headless": True,
        "timeout_minutes": DEFAULT_OPERATION_SESSION_TIMEOUT_IN_MINUTES,
        "proxies": False,
        "browser_type": BrowserType.CHROMIUM,
        "viewport_width": 1920,
        "viewport_height": 1080,
        "solve_captchas": False,
        "use_file_storage": False,
    }
    response = _start_session(mock_post=mock_post, client=client, session_id=session_id)
    assert response.session_id == session_id
    assert response.error is None

    mock_post.assert_called_once_with(
        url=f"{client.sessions.server_url}/sessions/start",
        headers={"Authorization": f"Bearer {api_key}"},
        json=session_data,
        params=None,
        timeout=client.sessions.DEFAULT_REQUEST_TIMEOUT_SECONDS,
        files=None,
    )


@patch("requests.delete")
@pytest.mark.order(2)
def test_close_session(mock_delete: MagicMock, client: NotteClient, api_key: str, session_id: str) -> None:
    response = _stop_session(mock_delete=mock_delete, client=client, session_id=session_id)
    assert response.session_id == session_id
    assert response.status == "closed"
    mock_delete.assert_called_once_with(
        url=f"{client.sessions.server_url}/sessions/{session_id}/stop",
        headers={"Authorization": f"Bearer {api_key}"},
        params=None,
        timeout=client.sessions.DEFAULT_REQUEST_TIMEOUT_SECONDS,
    )


@patch("requests.post")
def test_scrape(mock_post: MagicMock, client: NotteClient, api_key: str, session_id: str) -> None:
    mock_response = {
        "metadata": {
            "title": "Test Page",
            "url": "https://example.com",
            "timestamp": dt.datetime.now(),
            "viewport": {
                "scroll_x": 0,
                "scroll_y": 0,
                "viewport_width": 1000,
                "viewport_height": 1000,
                "total_width": 1000,
                "total_height": 1000,
            },
            "tabs": [],
        },
        "space": None,
        "data": {"markdown": "test space"},
        "screenshot": {"raw": b"fake_screenshot"},
        "session": session_response_dict(session_id),
        "progress": None,
    }
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_response

    observe_data: ObserveRequestDict = {
        "url": "https://example.com",
    }
    data = client.sessions.page.scrape(session_id=session_id, **observe_data)

    assert isinstance(data, DataSpace)
    mock_post.assert_called_once()
    actual_call = mock_post.call_args
    assert actual_call.kwargs["headers"] == {"Authorization": f"Bearer {api_key}"}
    assert actual_call.kwargs["json"]["url"] == "https://example.com"


@pytest.mark.parametrize("start_session", [True, False])
@patch("requests.delete")
@patch("requests.post")
def test_observe(
    mock_post: MagicMock,
    mock_delete: MagicMock,
    client: NotteClient,
    api_key: str,
    start_session: bool,
    session_id: str,
) -> None:
    if start_session:
        _ = _start_session(mock_post, client, session_id)
    mock_response = {
        "session": session_response_dict(session_id),
        "metadata": {
            "title": "Test Page",
            "url": "https://example.com",
            "timestamp": dt.datetime.now(),
            "viewport": {
                "scroll_x": 0,
                "scroll_y": 0,
                "viewport_width": 1000,
                "viewport_height": 1000,
                "total_width": 1000,
                "total_height": 1000,
            },
            "tabs": [],
        },
        "space": {
            "description": "test space",
            "interaction_actions": [
                {"type": "click", "id": "L0", "description": "my_description_0", "category": "homepage"},
                {"type": "click", "id": "L1", "description": "my_description_1", "category": "homepage"},
            ],
            "browser_actions": [s.model_dump() for s in BrowserAction.list()],
            "category": "homepage",
        },
        "screenshot": {"raw": b"fake_screenshot"},
        "progress": None,
    }
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_response

    observation = client.sessions.page.observe(session_id=session_id, url="https://example.com")

    assert isinstance(observation, Observation)
    assert observation.metadata.url == "https://example.com"
    assert len(observation.space.interaction_actions) > 0
    assert len(observation.space.browser_actions) > 0
    assert observation.screenshot.raw == b"fake_screenshot"
    if not start_session:
        mock_post.assert_called_once()
    actual_call = mock_post.call_args
    assert actual_call.kwargs["headers"] == {"Authorization": f"Bearer {api_key}"}
    assert actual_call.kwargs["json"]["url"] == "https://example.com"

    if start_session:
        _ = _stop_session(mock_delete=mock_delete, client=client, session_id=session_id)


@pytest.mark.parametrize("start_session", [True, False])
@patch("requests.delete")
@patch("requests.post")
def test_step(
    mock_post: MagicMock,
    mock_delete: MagicMock,
    client: NotteClient,
    api_key: str,
    start_session: bool,
    session_id: str,
) -> None:
    """
    Tests the client's step method with an optional session start.

    Simulates sending a step action with a defined payload and a mocked HTTP response.
    If start_session is True, a session is initiated before calling the step method and the
    client's session ID is verified; otherwise, it confirms that no session is maintained.
    The test asserts that the returned observation contains the expected metadata and that
    the HTTP request includes the appropriate authorization header and JSON payload.
    """
    if start_session:
        _ = _start_session(mock_post, client, session_id)
    mock_response = {
        "session": session_response_dict(session_id),
        "data": {
            "markdown": "test data",
        },
        "success": True,
        "message": "test message",
    }
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = mock_response

    step_data: StepRequestDict = {
        "type": "fill",
        "action_id": "I1",
        "value": "#submit-button",
        "enter": False,
    }
    obs = client.sessions.page.step(session_id=session_id, **step_data)

    assert isinstance(obs, StepResult)
    assert obs.success
    assert obs.message == "test message"

    if not start_session:
        mock_post.assert_called_once()
    actual_call = mock_post.call_args
    assert actual_call.kwargs["headers"] == {"Authorization": f"Bearer {api_key}"}
    assert actual_call.kwargs["json"]["action"]["id"] == "I1"
    assert actual_call.kwargs["json"]["action"]["value"] == "#submit-button"

    if start_session:
        _ = _stop_session(mock_delete=mock_delete, client=client, session_id=session_id)


def test_format_observe_response(client: NotteClient, session_id: str) -> None:
    response_dict = {
        "status": 200,
        "session": session_response_dict(session_id),
        "metadata": {
            "title": "Test Page",
            "url": "https://example.com",
            "timestamp": dt.datetime.now(),
            "viewport": {
                "scroll_x": 0,
                "scroll_y": 0,
                "viewport_width": 1000,
                "viewport_height": 1000,
                "total_width": 1000,
                "total_height": 1000,
            },
            "tabs": [],
        },
        "screenshot": {"raw": b"fake_screenshot"},
        "data": {"markdown": "my sample data"},
        "space": {
            "markdown": "test space",
            "description": "test space",
            "interaction_actions": [
                {"type": "click", "id": "L0", "description": "my_description_0", "category": "homepage"},
                {"type": "click", "id": "L1", "description": "my_description_1", "category": "homepage"},
            ],
            "browser_actions": [s.model_dump() for s in BrowserAction.list()],
            "category": "homepage",
        },
        "progress": None,
    }

    obs = ObserveResponse.model_validate(response_dict)
    assert obs.metadata.url == "https://example.com"
    assert obs.metadata.title == "Test Page"
    assert obs.screenshot.raw == b"fake_screenshot"
    assert obs.space is not None
    assert obs.space.description == "test space"
    assert obs.space.interaction_actions == [
        ClickAction(
            id="L0",
            description="my_description_0",
            category="homepage",
            param=None,
        ),
        ClickAction(
            id="L1",
            description="my_description_1",
            category="homepage",
            param=None,
        ),
    ]
    assert obs.space.category == SpaceCategory.HOMEPAGE
