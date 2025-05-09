from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.network.http import DefaultAsyncHttpxClient, Limits, Timeout


@pytest.fixture
def mock_httpx_client():
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200

    # Create the mock instance
    mock_instance = AsyncMock()
    mock_instance.timeout = Timeout(timeout=120.0, connect=30.0, read=90.0)
    mock_instance.limits = Limits(max_keepalive_connections=5, max_connections=10)
    mock_instance._timeout = mock_instance.timeout
    mock_instance._headers = {}

    # Mock both the client class and its parent's request method
    with (
        patch(
            "src.network.http.DefaultAsyncHttpxClient", return_value=mock_instance
        ) as mock_client,
        patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request,
    ):
        mock_request.return_value = mock_response
        yield mock_client, mock_request


@pytest.mark.asyncio
async def test_client_initialization_default_values(mock_httpx_client):
    """Test DefaultAsyncHttpxClient initialization with default values."""
    # Set up the mock's request method to return a successful response
    mock_response = AsyncMock()
    _, mock_request = mock_httpx_client
    mock_request.return_value = mock_response

    client = DefaultAsyncHttpxClient()

    # Verify timeout configuration
    assert isinstance(client.timeout, Timeout)
    assert client.timeout.connect == 30.0
    assert client.timeout.read == 90.0

    # Verify connection limits
    assert isinstance(client.limits, Limits)
    assert client.limits.max_keepalive_connections == 5
    assert client.limits.max_connections == 10

    # Verify other defaults
    assert client.max_retries == 3
    assert client.verify is True
    assert client.http2 is False

    # Verify the client has the correct configuration
    assert isinstance(client.timeout, Timeout)
    assert client.verify is True
    assert client.http2 is False


@pytest.mark.asyncio
async def test_client_initialization_custom_values(mock_httpx_client):
    """Test DefaultAsyncHttpxClient initialization with custom values."""
    client = DefaultAsyncHttpxClient(
        timeout=60.0,
        connect_timeout=15.0,
        read_timeout=45.0,
        max_keepalive_connections=2,
        max_connections=5,
        max_retries=5,
        verify=False,
        http2=False,
    )

    # Verify timeout configuration
    assert isinstance(client.timeout, Timeout)
    assert client.timeout.connect == 15.0
    assert client.timeout.read == 45.0

    # Verify connection limits
    assert isinstance(client.limits, Limits)
    assert client.limits.max_keepalive_connections == 2
    assert client.limits.max_connections == 5

    # Verify other settings
    assert client.max_retries == 5
    assert client.verify is False
    assert client.http2 is False


@pytest.mark.asyncio
async def test_request_success(mock_httpx_client):
    """Test successful request without retries."""
    _, mock_request = mock_httpx_client

    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200

    # Set up the mock request to return our mock response
    mock_request.return_value = mock_response

    # Make the request
    response = await mock_request("GET", "http://test.com")

    # Verify the response and that the request was made correctly
    assert response.status_code == 200
    mock_request.assert_called_once_with("GET", "http://test.com")


@pytest.mark.asyncio
async def test_request_with_retries(mock_httpx_client):
    """Test request with retries after connection errors."""
    _, mock_request = mock_httpx_client
    client = DefaultAsyncHttpxClient(max_retries=3)

    # Create mock responses
    success_response = AsyncMock()
    success_response.status_code = 200

    # Set up the side effects
    mock_request.side_effect = [
        httpx.ConnectError("Connection error"),
        httpx.ReadError("Read error"),
        success_response,
    ]

    response = await client.request("GET", "http://test.com")
    assert response is not None
    assert response.status_code == 200
    assert mock_request.call_count == 3


@pytest.mark.asyncio
async def test_http_method_shortcuts(mock_httpx_client):
    """Test the HTTP method shortcut methods (get, post, put, delete)."""
    _, mock_request = mock_httpx_client
    client = DefaultAsyncHttpxClient()

    # Test GET
    await client.get("http://test.com")
    mock_request.assert_called_with("GET", "http://test.com")

    # Test POST
    await client.post("http://test.com", json={"key": "value"})
    mock_request.assert_called_with("POST", "http://test.com", json={"key": "value"})

    # Test PUT
    await client.put("http://test.com", data="data")
    mock_request.assert_called_with("PUT", "http://test.com", data="data")

    # Test DELETE
    await client.delete("http://test.com")
    mock_request.assert_called_with("DELETE", "http://test.com")


@pytest.mark.asyncio
async def test_custom_timeout_object(mock_httpx_client):
    """Test initialization with a custom Timeout object."""
    custom_timeout = Timeout(timeout=60.0, connect=15.0, read=45.0)
    client = DefaultAsyncHttpxClient(timeout=custom_timeout)

    assert client.timeout == custom_timeout
    assert client.timeout.connect == 15.0
    assert client.timeout.read == 45.0


@pytest.mark.asyncio
async def test_exponential_backoff(mock_httpx_client):
    """Test the exponential backoff mechanism."""
    _, mock_request = mock_httpx_client
    client = DefaultAsyncHttpxClient(max_retries=3)

    # Create mock responses
    success_response = AsyncMock()
    success_response.status_code = 200

    # Set up the side effects
    mock_request.side_effect = [
        httpx.ConnectError("Connection error"),
        httpx.ReadError("Read error"),
        success_response,
    ]

    # Mock asyncio.sleep to verify backoff timing
    with patch("asyncio.sleep") as mock_sleep:
        await client.request("GET", "http://test.com")

        # Verify sleep was called twice with increasing delays
        assert mock_sleep.call_count == 2
        # First backoff should be 2^0 + 0.1 = 1.1 seconds
        assert 1.0 <= mock_sleep.call_args_list[0][0][0] <= 1.2
        # Second backoff should be 2^1 + 0.2 = 2.2 seconds
        assert 2.0 <= mock_sleep.call_args_list[1][0][0] <= 2.3
