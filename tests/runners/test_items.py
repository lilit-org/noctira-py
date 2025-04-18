from dataclasses import dataclass

from src.runners.items import (
    THINK_END,
    THINK_START,
    ItemHelpers,
    MessageOutputItem,
    ModelResponse,
    OrbsCallItem,
    OrbsOutputItem,
    ReasoningItem,
    ResponseReasoningItem,
    SwordCallItem,
    SwordCallOutputItem,
)
from src.util.types import (
    FunctionCallOutput,
    ResponseFunctionSwordCall,
    ResponseInputItemParam,
    ResponseOutput,
    Usage,
)


# Mock Agent class for testing
@dataclass
class MockAgent:
    name: str


def test_message_output_item_text_content():
    """Test MessageOutputItem text content extraction."""
    # Create a mock agent
    agent = MockAgent(name="test_agent")

    # Test case 1: Empty content
    empty_output = ResponseOutput(type="message", content=[])
    item = MessageOutputItem(agent=agent, raw_item=empty_output)
    assert item.text_content == ""

    # Test case 2: Single text content
    text_output = ResponseOutput(
        type="message", content=[{"type": "output_text", "text": "Hello world"}]
    )
    item = MessageOutputItem(agent=agent, raw_item=text_output)
    assert item.text_content == "Hello world"

    # Test case 3: Multiple text contents
    multi_output = ResponseOutput(
        type="message",
        content=[
            {"type": "output_text", "text": "Hello"},
            {"type": "output_text", "text": "world"},
        ],
    )
    item = MessageOutputItem(agent=agent, raw_item=multi_output)
    assert item.text_content == "Hello world"


def test_orbs_call_item():
    """Test OrbsCallItem creation and attributes."""
    agent = MockAgent(name="test_agent")
    sword_call = ResponseFunctionSwordCall(
        type="function_call",
        id="test_id",
        call_id="test_call_id",
        name="test_function",
        arguments="{}",
    )

    item = OrbsCallItem(agent=agent, raw_item=sword_call)
    assert item.type == "orbs_call_item"
    assert item.raw_item == sword_call


def test_sword_call_item():
    """Test SwordCallItem creation and attributes."""
    agent = MockAgent(name="test_agent")
    sword_call = ResponseFunctionSwordCall(
        type="function_call",
        id="test_id",
        call_id="test_call_id",
        name="test_function",
        arguments="{}",
    )

    item = SwordCallItem(agent=agent, raw_item=sword_call)
    assert item.type == "sword_called"
    assert item.raw_item == sword_call


def test_sword_call_output_item():
    """Test SwordCallOutputItem creation and attributes."""
    agent = MockAgent(name="test_agent")
    function_output = FunctionCallOutput(
        type="function_call_output", call_id="test_call_id", output="test output"
    )

    item = SwordCallOutputItem(agent=agent, raw_item=function_output, output="test output")
    assert item.type == "sword_call_output_item"
    assert item.raw_item == function_output
    assert item.output == "test output"


def test_model_response():
    """Test ModelResponse creation and methods."""
    output = [ResponseOutput(type="message", content=[{"type": "output_text", "text": "Hello"}])]
    usage = Usage(requests=1, input_tokens=10, output_tokens=5, total_tokens=15)

    response = ModelResponse(output=output, usage=usage, referenceable_id="test_id")

    assert len(response.output) == 1
    assert response.usage == usage
    assert response.referenceable_id == "test_id"

    input_items = response.to_input_items()
    assert len(input_items) == 1
    assert isinstance(input_items[0], dict)


def test_item_helpers_extract_last_content():
    """Test ItemHelpers.extract_last_content method."""
    # Test case 1: Empty message
    empty_message = ResponseOutput(type="message", content=[])
    assert ItemHelpers.extract_last_content(empty_message) == ""

    # Test case 2: Text content
    text_message = ResponseOutput(
        type="message", content=[{"type": "output_text", "text": "Hello"}]
    )
    assert ItemHelpers.extract_last_content(text_message) == "Hello"

    # Test case 3: Refusal content
    refusal_message = ResponseOutput(
        type="message", content=[{"type": "refusal", "refusal": "I cannot do that"}]
    )
    assert ItemHelpers.extract_last_content(refusal_message) == "I cannot do that"


def test_item_helpers_input_to_new_input_list():
    """Test ItemHelpers.input_to_new_input_list method."""
    # Test case 1: String input
    string_input = "Hello"
    result = ItemHelpers.input_to_new_input_list(string_input)
    assert len(result) == 1
    assert result[0]["content"] == "Hello"
    assert result[0]["role"] == "user"

    # Test case 2: List input
    list_input = [ResponseInputItemParam(type="message", content="Hello", role="user")]
    result = ItemHelpers.input_to_new_input_list(list_input)
    assert len(result) == 1
    assert result[0]["content"] == "Hello"
    assert result[0]["role"] == "user"


def test_item_helpers_sword_call_output_item():
    """Test ItemHelpers.sword_call_output_item method."""
    sword_call = ResponseFunctionSwordCall(
        type="function_call",
        id="test_id",
        call_id="test_call_id",
        name="test_function",
        arguments="{}",
    )

    output = "test output"
    result = ItemHelpers.sword_call_output_item(sword_call, output)

    assert result["type"] == "function_call_output"
    assert result["call_id"] == "test_call_id"
    assert result["output"] == "test output"


def test_orbs_output_item():
    """Test OrbsOutputItem creation and attributes."""
    source_agent = MockAgent(name="source_agent")
    target_agent = MockAgent(name="target_agent")
    input_param = ResponseInputItemParam(type="message", content="test content", role="user")

    item = OrbsOutputItem(
        agent=source_agent,
        raw_item=input_param,
        source_agent=source_agent,
        target_agent=target_agent,
    )
    assert item.type == "orbs_output_item"
    assert item.raw_item == input_param
    assert item.source_agent == source_agent
    assert item.target_agent == target_agent


def test_reasoning_item():
    """Test ReasoningItem creation and attributes."""
    agent = MockAgent(name="test_agent")
    reasoning_item = ResponseReasoningItem(
        type="reasoning", content="test reasoning content", step=1
    )

    item = ReasoningItem(agent=agent, raw_item=reasoning_item)
    assert item.type == "reasoning_item"
    assert item.raw_item == reasoning_item


def test_item_helpers_extract_last_text():
    """Test ItemHelpers.extract_last_text method."""
    # Test case 1: Empty message
    empty_message = ResponseOutput(type="message", content=[])
    assert ItemHelpers.extract_last_text(empty_message) is None

    # Test case 2: Text content
    text_message = ResponseOutput(
        type="message", content=[{"type": "output_text", "text": "Hello"}]
    )
    assert ItemHelpers.extract_last_text(text_message) == "Hello"

    # Test case 3: Non-text content
    refusal_message = ResponseOutput(
        type="message", content=[{"type": "refusal", "refusal": "I cannot do that"}]
    )
    assert ItemHelpers.extract_last_text(refusal_message) is None


def test_item_helpers_text_message_outputs():
    """Test ItemHelpers.text_message_outputs method."""
    agent = MockAgent(name="test_agent")

    # Test case 1: Empty list
    assert ItemHelpers.text_message_outputs([]) == ""

    # Test case 2: Single message
    message_item = MessageOutputItem(
        agent=agent,
        raw_item=ResponseOutput(type="message", content=[{"type": "output_text", "text": "Hello"}]),
    )
    assert ItemHelpers.text_message_outputs([message_item]) == "Hello"

    # Test case 3: Multiple messages
    message_item2 = MessageOutputItem(
        agent=agent,
        raw_item=ResponseOutput(type="message", content=[{"type": "output_text", "text": "World"}]),
    )
    assert ItemHelpers.text_message_outputs([message_item, message_item2]) == "Hello World"


def test_item_helpers_text_message_output():
    """Test ItemHelpers.text_message_output method."""
    agent = MockAgent(name="test_agent")

    # Test case 1: Empty content
    empty_item = MessageOutputItem(agent=agent, raw_item=ResponseOutput(type="message", content=[]))
    assert ItemHelpers.text_message_output(empty_item) == ""

    # Test case 2: Single text content
    text_item = MessageOutputItem(
        agent=agent,
        raw_item=ResponseOutput(type="message", content=[{"type": "output_text", "text": "Hello"}]),
    )
    assert ItemHelpers.text_message_output(text_item) == "Hello"

    # Test case 3: Multiple text contents
    multi_item = MessageOutputItem(
        agent=agent,
        raw_item=ResponseOutput(
            type="message",
            content=[
                {"type": "output_text", "text": "Hello"},
                {"type": "output_text", "text": "World"},
            ],
        ),
    )
    assert ItemHelpers.text_message_output(multi_item) == "Hello World"


def test_item_helpers_format_content():
    """Test ItemHelpers.format_content method."""
    # Test case 1: Empty content
    assert ItemHelpers.format_content("") == ""

    # Test case 2: Simple content
    assert ItemHelpers.format_content("Hello") == "Hello"

    # Test case 3: Content with special lines
    content = f"{THINK_START}Thinking{THINK_END}"
    assert ItemHelpers.format_content(content) == "Thinking"

    # Test case 4: Content with multiple sections
    content = f"{THINK_START}First thought{THINK_END}\n{THINK_START}Second thought{THINK_END}"
    assert ItemHelpers.format_content(content) == "First thought\nSecond thought"
