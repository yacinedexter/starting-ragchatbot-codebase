"""
Tests for AIGenerator in ai_generator.py.

Verifies external behavior: API calls made, tools executed, values returned.
Does not test internal state or method boundaries.
"""
import pytest
from unittest.mock import MagicMock, patch

from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helpers to build mock Anthropic SDK objects
# ---------------------------------------------------------------------------

def _text_response(text="Here is the answer."):
    """Simulate an end_turn response with a single text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def _tool_use_response(tool_name="search_course_content", tool_input=None, tool_id="toolu_01"):
    """Simulate a tool_use stop-reason response."""
    if tool_input is None:
        tool_input = {"query": "python basics"}

    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def generator():
    with patch("ai_generator.anthropic") as mock_anthropic_module:
        mock_client = MagicMock()
        mock_anthropic_module.Anthropic.return_value = mock_client
        gen = AIGenerator(api_key="test-key", model="test-model")
        gen._mock_client = mock_client
        yield gen


# ---------------------------------------------------------------------------
# Direct answer — no tool use
# ---------------------------------------------------------------------------

class TestGenerateResponseDirect:
    def test_returns_text_from_first_response(self, generator):
        generator._mock_client.messages.create.return_value = _text_response("42")
        result = generator.generate_response(query="What is 6 times 7?")
        assert result == "42"

    def test_api_called_once_when_no_tool_use(self, generator):
        generator._mock_client.messages.create.return_value = _text_response()
        generator.generate_response(query="Hello")
        assert generator._mock_client.messages.create.call_count == 1

    def test_conversation_history_appended_to_system(self, generator):
        generator._mock_client.messages.create.return_value = _text_response()
        history = "User: What is Python?\nAssistant: A language."
        generator.generate_response(query="Continue", conversation_history=history)
        call_kwargs = generator._mock_client.messages.create.call_args.kwargs
        assert "A language." in call_kwargs["system"]

    def test_tools_passed_to_api_when_provided(self, generator):
        generator._mock_client.messages.create.return_value = _text_response()
        tools = [{"name": "search_course_content", "input_schema": {}}]
        generator.generate_response(query="question", tools=tools, tool_manager=MagicMock())
        call_kwargs = generator._mock_client.messages.create.call_args.kwargs
        assert "tools" in call_kwargs
        assert call_kwargs["tools"] == tools

    def test_tool_choice_auto_set_when_tools_provided(self, generator):
        generator._mock_client.messages.create.return_value = _text_response()
        generator.generate_response(query="q", tools=[{"name": "t", "input_schema": {}}], tool_manager=MagicMock())
        call_kwargs = generator._mock_client.messages.create.call_args.kwargs
        assert call_kwargs.get("tool_choice") == {"type": "auto"}


# ---------------------------------------------------------------------------
# Single tool round (1 tool call → text)
# ---------------------------------------------------------------------------

class TestSingleToolRound:
    def test_two_api_calls_on_single_tool_use(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "search results"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response("Final answer"),
        ]
        result = generator.generate_response(
            query="What is Python?",
            tools=[{"name": "search_course_content", "input_schema": {}}],
            tool_manager=tool_manager,
        )
        assert generator._mock_client.messages.create.call_count == 2
        assert result == "Final answer"

    def test_tool_manager_called_with_correct_name_and_input(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(
                tool_name="search_course_content",
                tool_input={"query": "decorators", "course_name": "Python 101"},
            ),
            _text_response(),
        ]
        generator.generate_response(
            query="Tell me about decorators",
            tools=[],
            tool_manager=tool_manager,
        )
        tool_manager.execute_tool.assert_called_once_with(
            "search_course_content",
            query="decorators",
            course_name="Python 101",
        )

    def test_tool_result_in_second_call_messages(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "Found: decorators explanation"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="toolu_abc", tool_input={"query": "decorators"}),
            _text_response(),
        ]
        generator.generate_response(query="about decorators", tools=[], tool_manager=tool_manager)

        second_call_kwargs = generator._mock_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]

        tool_result_found = False
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        assert block["tool_use_id"] == "toolu_abc"
                        assert block["content"] == "Found: decorators explanation"
                        tool_result_found = True
        assert tool_result_found

    def test_tools_param_in_second_api_call(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "some results"
        tools = [{"name": "search_course_content", "input_schema": {"type": "object", "properties": {}}}]

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(),
            _text_response(),
        ]
        generator.generate_response(query="question", tools=tools, tool_manager=tool_manager)

        second_call_kwargs = generator._mock_client.messages.create.call_args_list[1].kwargs
        assert "tools" in second_call_kwargs

    def test_assistant_tool_use_content_in_second_call_messages(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        first_response = _tool_use_response()
        generator._mock_client.messages.create.side_effect = [first_response, _text_response()]
        generator.generate_response(query="q", tools=[], tool_manager=tool_manager)

        second_call_kwargs = generator._mock_client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        assert len(assistant_messages) == 1
        assert assistant_messages[0]["content"] == first_response.content


# ---------------------------------------------------------------------------
# Two sequential tool rounds (new capability)
# ---------------------------------------------------------------------------

class TestTwoSequentialToolRounds:
    def test_three_api_calls_on_two_tool_rounds(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "result"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="toolu_r1"),
            _tool_use_response(tool_id="toolu_r2"),
            _text_response("Final synthesis"),
        ]
        result = generator.generate_response(
            query="Complex query",
            tools=[{"name": "search_course_content", "input_schema": {}}],
            tool_manager=tool_manager,
        )
        assert generator._mock_client.messages.create.call_count == 3
        assert result == "Final synthesis"

    def test_execute_tool_called_twice_on_two_rounds(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = ["result_1", "result_2"]

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="toolu_r1", tool_input={"query": "first"}),
            _tool_use_response(tool_id="toolu_r2", tool_input={"query": "second"}),
            _text_response(),
        ]
        generator.generate_response(query="q", tools=[], tool_manager=tool_manager)
        assert tool_manager.execute_tool.call_count == 2

    def test_both_tool_results_present_in_synthesis_call(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = ["result_round_1", "result_round_2"]

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="toolu_r1"),
            _tool_use_response(tool_id="toolu_r2"),
            _text_response(),
        ]
        generator.generate_response(query="q", tools=[], tool_manager=tool_manager)

        synthesis_kwargs = generator._mock_client.messages.create.call_args_list[2].kwargs
        all_tool_results = []
        for msg in synthesis_kwargs["messages"]:
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        all_tool_results.append(block["content"])

        assert "result_round_1" in all_tool_results
        assert "result_round_2" in all_tool_results

    def test_tools_param_present_on_all_three_calls(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "r"
        tools = [{"name": "search_course_content", "input_schema": {}}]

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="r1"),
            _tool_use_response(tool_id="r2"),
            _text_response(),
        ]
        generator.generate_response(query="q", tools=tools, tool_manager=tool_manager)

        for i, call in enumerate(generator._mock_client.messages.create.call_args_list):
            assert "tools" in call.kwargs, f"Call {i + 1} is missing 'tools'"

    def test_synthesis_call_has_no_tool_choice(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "r"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="r1"),
            _tool_use_response(tool_id="r2"),
            _text_response(),
        ]
        generator.generate_response(
            query="q",
            tools=[{"name": "t", "input_schema": {}}],
            tool_manager=tool_manager,
        )
        synthesis_kwargs = generator._mock_client.messages.create.call_args_list[2].kwargs
        assert "tool_choice" not in synthesis_kwargs

    def test_max_rounds_constant_controls_loop_depth(self, generator, monkeypatch):
        monkeypatch.setattr(generator, "MAX_ROUNDS", 1)
        tool_manager = MagicMock()
        tool_manager.execute_tool.return_value = "r"

        generator._mock_client.messages.create.side_effect = [
            _tool_use_response(tool_id="r1"),
            _text_response("done after 1 round"),
        ]
        result = generator.generate_response(
            query="q",
            tools=[{"name": "t", "input_schema": {}}],
            tool_manager=tool_manager,
        )
        assert generator._mock_client.messages.create.call_count == 2
        assert result == "done after 1 round"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestToolExecutionErrors:
    def test_tool_exception_returns_error_string_not_raise(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("db offline")

        generator._mock_client.messages.create.return_value = _tool_use_response()
        result = generator.generate_response(
            query="q",
            tools=[{"name": "t", "input_schema": {}}],
            tool_manager=tool_manager,
        )
        assert isinstance(result, str)
        assert "db offline" in result

    def test_tool_exception_stops_further_api_calls(self, generator):
        tool_manager = MagicMock()
        tool_manager.execute_tool.side_effect = RuntimeError("fail")

        generator._mock_client.messages.create.return_value = _tool_use_response()
        generator.generate_response(query="q", tools=[], tool_manager=tool_manager)
        assert generator._mock_client.messages.create.call_count == 1

    def test_no_tool_manager_with_tool_use_response_returns_text(self, generator):
        generator._mock_client.messages.create.return_value = _tool_use_response()
        result = generator.generate_response(query="q", tools=[])
        assert isinstance(result, str)
        assert generator._mock_client.messages.create.call_count == 1
