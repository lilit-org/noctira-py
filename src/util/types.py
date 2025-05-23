"""
This module defines core type definitions and data structures used throughout the
project.

It includes:
- Type variables and generic type definitions
- Data classes for tracking API usage and context management
- Response output types for API interactions
- Chat completion related types for LLM interactions
- Streaming response handling types
- Input parameter types for API requests
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeAlias, TypedDict

from typing_extensions import NotRequired, TypeVar

from ..util.constants import err
from ..util.exceptions import ModelError, NetworkError

########################################################
#              Type Variables
########################################################

T = TypeVar("T")
TContext = TypeVar("TContext", bound=Any)
TContext_co = TypeVar("TContext_co", covariant=True)
MaybeAwaitable = Awaitable[T] | T
TResponseInputItem: TypeAlias = "ResponseInputItemParam"

########################################################
#              Decorator Factory
########################################################


def create_decorator_factory(
    base_class: type[Generic[TContext_co, Any]],
    sync_func_type: type,
    async_func_type: type,
    *,
    constructor_params: dict[str, Any] | None = None,
    pre_init_hook: Callable[[Any, dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable:
    """Create a decorator factory for classes that wrap functions.

    Args:
        base_class: The base class to instantiate
        sync_func_type: Type for synchronous functions
        async_func_type: Type for asynchronous functions
        constructor_params: Default parameters for the constructor
        pre_init_hook: Optional hook to modify parameters before instantiation

    Returns:
        A decorator that can be used to create instances from functions
    """

    def decorator(
        func: sync_func_type | async_func_type | None = None,
        **kwargs: Any,
    ) -> base_class | Callable[[sync_func_type | async_func_type], base_class]:
        def create_instance(
            f: sync_func_type | async_func_type,
        ) -> base_class:
            # Start with default constructor params
            params = dict(constructor_params or {})

            # Add the function as the first parameter
            params[next(iter(params.keys()) if params else "function")] = f

            # Add any additional kwargs
            params.update(kwargs)

            # Allow pre-init hook to modify params
            if pre_init_hook:
                params = pre_init_hook(f, params)

            return base_class(**params)

        if func is not None:
            return create_instance(func)
        return create_instance

    return decorator


########################################################
#            Data class for Usage and Contexts
########################################################


@dataclass(frozen=True)
class Usage:
    """Track LLM API token usage and requests."""

    requests: int = 0
    """API request count."""

    input_tokens: int = 0
    """Tokens sent to API."""

    output_tokens: int = 0
    """Tokens received from API."""

    total_tokens: int = 0
    """Total tokens used."""

    def add(self, other: Usage) -> Usage:
        """Add another Usage instance to this one."""
        return Usage(
            requests=self.requests + (other.requests or 0),
            input_tokens=self.input_tokens + (other.input_tokens or 0),
            output_tokens=self.output_tokens + (other.output_tokens or 0),
            total_tokens=self.total_tokens + (other.total_tokens or 0),
        )


@dataclass
class RunContextWrapper(Generic[TContext]):
    """Wrapper for context objects passed to Runner.run().

    Contexts are used to pass dependencies and data to custom code.
    They are not passed to the LLM.
    """

    context: TContext
    """Context object passed to Runner.run()"""

    usage: Usage = field(default_factory=Usage)
    """Usage stats for the agent run. May be stale during streaming until final chunk."""


# Sword function type aliases


########################################################
#            Queue Sentinel Types
########################################################


@dataclass(frozen=True)
class QueueCompleteSentinel:
    """Sentinel value used to indicate the end of a queue stream."""


########################################################
#            Classes for Response Outputs
########################################################


@dataclass(frozen=True)
class Response:
    """API response containing outputs and usage stats."""

    id: str
    output: Sequence[ResponseOutput]
    usage: Usage | None = None
    created_at: float | None = None
    model: str | None = None
    object: Literal["response"] | None = None
    sword_choice: Literal["auto", "required", "none"] | None = None
    temperature: float | None = None
    swords: Sequence[ChatCompletionSwordParam] | None = None
    parallel_sword_calls: bool | None = None
    top_p: float | None = None


@dataclass(frozen=True)
class ModelResponse:
    """Response from a model containing outputs and usage stats."""

    id: str
    output: Sequence[ResponseOutput]
    usage: Usage | None = None
    created_at: float | None = None
    model: str | None = None
    object: Literal["response"] | None = None
    sword_choice: Literal["auto", "required", "none"] | None = None
    temperature: float | None = None
    swords: Sequence[ChatCompletionSwordParam] | None = None
    parallel_sword_calls: bool | None = None
    top_p: float | None = None


class ResponseOutput(TypedDict):
    """Output from an API response with optional content and metadata."""

    type: str
    content: NotRequired[str | Sequence[ResponseOutputText | ResponseOutputRefusal]]
    name: NotRequired[str]
    arguments: NotRequired[Mapping[str, Any]]
    call_id: NotRequired[str]
    role: NotRequired[Literal["user", "assistant", "system", "developer"]]
    status: NotRequired[str]


class ResponseOutputText(TypedDict):
    """Text content in a response output."""

    type: Literal["output_text"]
    text: str
    annotations: Sequence[Mapping[str, Any]]


class ResponseOutputRefusal(TypedDict):
    """Refusal content in a response output."""

    type: Literal["refusal"]
    refusal: str


class ResponseFunctionSwordCall(TypedDict):
    """Function sword call in a response output."""

    type: Literal["function_call"]
    id: str
    call_id: str
    name: str
    arguments: str


class ResponseStreamEvent(TypedDict):
    """Event in a streaming response."""

    type: str
    content_index: NotRequired[int]
    item_id: NotRequired[str]
    output_index: NotRequired[int]
    delta: NotRequired[str]
    part: NotRequired[ResponseOutput]
    response: NotRequired[Response]


class ResponseTextDeltaEvent(TypedDict):
    """Event for text delta updates in streaming responses."""

    type: Literal["response.output_text.delta"]
    content_index: int
    item_id: str
    output_index: int
    delta: str


class FunctionCallOutput(TypedDict):
    """Output from a function sword call."""

    type: Literal["function_call_output"]
    call_id: str
    output: str


@dataclass(frozen=True)
class ResponseEvent:
    """Event indicating a change in response state."""

    type: Literal["completed", "content_part.added", "content_part.done", "output_text.delta"]
    response: Response | None = None
    content_index: int | None = None
    item_id: str | None = None
    output_index: int | None = None
    part: ResponseOutput | None = None
    delta: str | None = None


########################################################
#           Classes for Chat Completion Types
########################################################


class ChatCompletionSwordParam(TypedDict):
    """Sword params for chat completion."""

    name: str
    description: str
    parameters: Mapping[str, Any]


class ChatCompletionMessageSwordCallParam(TypedDict):
    """Sword call parameters in a chat message."""

    id: str
    type: Literal["function"]
    function: ChatCompletionSwordParam


class ChatCompletionContentPartParam(TypedDict):
    """Content part parameters for chat completion messages."""

    type: Literal["text", "image_url"]
    text: NotRequired[str]
    image_url: NotRequired[Mapping[str, str]]


class ChatCompletionMessage(TypedDict):
    """Message in a chat completion."""

    role: Literal["user", "assistant", "system", "developer", "sword"]
    content: NotRequired[str]
    sword_calls: NotRequired[Sequence[ChatCompletionMessageSwordCallParam]]
    refusal: NotRequired[str]
    audio: NotRequired[Mapping[str, str]]


class ChatCompletionMessageParam(TypedDict):
    """Parameters for a chat completion message."""

    role: Literal["user", "assistant", "system", "developer", "sword"]
    content: str | Sequence[ChatCompletionContentPartParam]
    sword_call_id: NotRequired[str]
    sword_calls: NotRequired[Sequence[ChatCompletionMessageSwordCallParam]]
    refusal: NotRequired[str]


class ChatCompletionUsage(TypedDict):
    """Token usage statistics for chat completion."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionDeltaFunction(TypedDict):
    """Delta update for a function call in streaming responses."""

    name: NotRequired[str]
    arguments: NotRequired[str]


class ChatCompletionDeltaSwordCall(TypedDict):
    """Delta update for a sword call in streaming responses."""

    index: int
    id: NotRequired[str]
    type: NotRequired[Literal["function"]]
    function: NotRequired[ChatCompletionDeltaFunction]


class ChatCompletionDelta(TypedDict):
    """Delta update for streaming responses."""

    role: NotRequired[Literal["assistant"]]
    content: NotRequired[str]
    function: NotRequired[dict[str, str]]


class ChatCompletionChoice(TypedDict):
    """Choice in a chat completion response."""

    index: int
    message: ChatCompletionMessage
    finish_reason: NotRequired[str]
    delta: NotRequired[ChatCompletionDelta]


class ChatCompletion(TypedDict):
    """Chat completion response."""

    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: Sequence[ChatCompletionChoice]
    usage: NotRequired[ChatCompletionUsage]


class ChatCompletionChunk(TypedDict):
    """Streaming response chunk."""

    id: str
    object: Literal["chat.completion.chunk"]
    created: int
    model: str
    choices: Sequence[ChatCompletionChoice]
    usage: NotRequired[ChatCompletionUsage]


ChatCompletionSwordChoiceOptionParam: TypeAlias = (
    Literal["auto", "required", "none"] | Mapping[str, Any]
)


########################################################
#            Class for Response Input
########################################################


class ResponseInputItemParam(TypedDict):
    """Input item for API requests."""

    type: str
    content: NotRequired[str]
    role: NotRequired[Literal["user", "assistant", "system", "developer"]]
    name: NotRequired[str]
    arguments: NotRequired[Mapping[str, Any]]
    call_id: NotRequired[str]


InputItem: TypeAlias = ResponseInputItemParam


class ResponseFormat(TypedDict):
    """Format specification for API responses."""

    type: Literal["json_schema"]
    json_schema: Mapping[str, Any]


########################################################
#           Main class for Async Streaming
########################################################


class AsyncStream(AsyncIterator[ChatCompletionChunk]):
    """Async iterator for streaming chat completion chunks."""

    def __init__(self, stream: AsyncIterator[str | dict]):
        self._stream = stream

    def _create_fallback_chunk(self, data: Any, content: str = "") -> ChatCompletionChunk:
        """Create a fallback chat completion chunk with default values."""
        return {
            "id": ("fallback-id" if not isinstance(data, dict) else data.get("id", "fallback-id")),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": ("unknown" if not isinstance(data, dict) else data.get("model", "unknown")),
            "choices": [{"index": 0, "delta": {"content": content or str(data)}}],
        }

    async def __anext__(self) -> ChatCompletionChunk:
        try:
            line = await anext(self._stream)

            # If line is already a dictionary, return it directly
            if isinstance(line, dict):
                return line

            if line.startswith("data: "):
                line = line[6:]
            if line == "[DONE]":
                raise StopAsyncIteration

            data = json.loads(line)

            # Handle Ollama's specific response format
            if "message" in data:
                content = data["message"].get("content", "")
                return {
                    "id": data.get("id", f"ollama-{hash(content)}"),
                    "object": "chat.completion.chunk",
                    "created": data.get("created", int(time.time())),
                    "model": data.get("model", "unknown"),
                    "choices": [{"index": 0, "delta": {"content": content}}],
                }

            # Handle invalid or incomplete response structures
            if not isinstance(data, dict) or "choices" not in data:
                return self._create_fallback_chunk(data)

            # Ensure choices array is not empty and has delta
            if not data["choices"]:
                data["choices"] = [{"index": 0, "delta": {"content": ""}}]
            elif "delta" not in data["choices"][0]:
                data["choices"][0]["delta"] = {"content": str(data["choices"][0])}

            return data
        except StopAsyncIteration:
            raise
        except json.JSONDecodeError as e:
            raise ModelError(
                err.MODEL_ERROR.format(error=f"Failed to parse JSON from stream: {e}")
            ) from e
        except Exception as e:
            raise NetworkError(
                err.NETWORK_ERROR.format(error=f"Error processing stream chunk: {e}")
            ) from e


class AsyncDeepSeek:
    """Async DeepSeek API client."""

    class chat:
        class completions:
            @classmethod
            async def create(
                cls,
                model: str,
                messages: Sequence[ChatCompletionMessageParam],
                swords: Sequence[ChatCompletionSwordParam] | None = None,
                temperature: float | None = None,
                top_p: float | None = None,
                max_tokens: int | None = None,
                sword_choice: ChatCompletionSwordChoiceOptionParam | None = None,
                response_format: ResponseFormat | None = None,
                parallel_sword_calls: bool | None = None,
                stream: bool = False,
                stream_options: Mapping[str, bool] | None = None,
                extra_headers: Mapping[str, str] | None = None,
            ) -> ChatCompletion | AsyncStream:
                """Create chat completion."""
                raise NotImplementedError


ResponseReasoningItem: TypeAlias = ResponseOutput
