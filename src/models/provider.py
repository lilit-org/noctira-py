"""
Model Provider Management

This module provides the ModelProvider class, a flexible provider interface for managing model instances
and their configurations. It handles client initialization, API key management, and model selection
with support for both chat completions and responses API modes.

Key features:
- Dynamic client initialization with environment-based configuration
- API key and base URL management with fallback to environment variables
- Support for both chat completions and responses API modes
- Organization and project context management
- Lazy client loading to prevent premature API key validation
"""

from __future__ import annotations

from src.util._client import DeepSeekClient
from src.util._constants import BASE_URL, MODEL
from src.util._http import DefaultAsyncHttpxClient
from src.util._types import AsyncDeepSeek

from . import shared
from .chat import ModelChatCompletionsModel
from .interface import Model
from .interface import ModelProvider as BaseModelProvider
from .responses import ModelResponsesModel


########################################################
#               Main Class: Model Provider
########################################################


class ModelProvider(BaseModelProvider):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model_client: AsyncDeepSeek | None = None,
        organization: str | None = None,
        project: str | None = None,
        use_responses: bool | None = None,
    ) -> None:
        """Initialize a Model provider.

        Args:
            api_key: API key for the client. Uses default if not provided.
            base_url: Base URL for the client. Uses env var if not provided.
            model_client: Optional pre-configured client.
            organization: Organization ID for the client.
            project: Project ID for the client.
            use_responses: Whether to use responses API.
        """
        if model_client is not None:
            if api_key is not None or base_url is not None:
                raise ValueError("Don't provide api_key or base_url if you provide model_client")
            self._client = model_client
        else:
            self._client = None
            self._stored_api_key = api_key
            self._stored_base_url = base_url or BASE_URL
            self._stored_organization = organization
            self._stored_project = project

        self._use_responses = (
            use_responses if use_responses is not None else shared.get_use_responses_by_default()
        )

    def _get_client(self) -> AsyncDeepSeek:
        """Lazy load the client to avoid API key errors if never used."""
        if self._client is None:
            self._client = shared.get_default_model_client() or DeepSeekClient(
                api_key=self._stored_api_key or shared.get_default_model_key(),
                base_url=self._stored_base_url,
                organization=self._stored_organization,
                project=self._stored_project,
                http_client=DefaultAsyncHttpxClient(),
            )
        return self._client

    def get_model(self, model_name: str | None = None) -> Model:
        """Get a model instance based on name and response type."""
        model_name = model_name or MODEL

        client = self._get_client()
        return (
            ModelResponsesModel(model=model_name, model_client=client)
            if self._use_responses
            else ModelChatCompletionsModel(model=model_name, model_client=client)
        )
