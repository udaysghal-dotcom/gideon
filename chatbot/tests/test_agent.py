"""Checks for context totals, the ollama ps processor label, and chat commands."""

from chatbot.agent import (
    context_after_trim,
    ollama_tool,
    processor_for,
    processor_label,
    running_model_matches,
)
from chatbot.chat import format_lookup, split_command


class Running:
    def __init__(self, name, size, size_vram, model=None):
        self.name = name
        self.model = model if model is not None else name
        self.size = size
        self.size_vram = size_vram


class Tool:
    def __init__(self):
        self.name = "get_clause"
        self.description = "Full text of one clause."
        self.input_schema = {
            "type": "object",
            "title": "get_clauseArguments",
            "required": ["adr", "clause"],
            "properties": {
                "adr": {"type": "string", "title": "Adr"},
                "clause": {"type": "string", "title": "Clause"},
            },
        }


def test_context_is_exact_when_nothing_is_dropped():
    assert context_after_trim(1000, 50) == 1050


def test_context_drops_tool_text():
    # 400 characters is about 100 tokens, removed from the prompt count.
    assert context_after_trim(1000, 50, "x" * 400) == 950


def test_context_drops_thinking_text():
    assert context_after_trim(100, 40, dropped_completion_text="y" * 40) == 130


def test_processor_matches_ollama_ps():
    assert processor_label(0, 0) == "100% CPU"
    assert processor_label(500, 0) == "100% CPU"
    assert processor_label(500, 500) == "100% GPU"
    assert processor_label(100, 52) == "48%/52% CPU/GPU"
    assert processor_label(8, 1) == "88%/12% CPU/GPU"
    assert processor_label(100, 150) == "Unknown"


def test_processor_for_the_chat_model():
    loaded = [Running("gemma4:12b", 100, 100), Running("qwen3.5:9b", 80, 40)]
    assert processor_for(loaded, "gemma4:12b") == "100% GPU"
    assert processor_for(loaded, "qwen3.5:9b") == "50%/50% CPU/GPU"
    assert processor_for(loaded, "llama3.1:8b") == "llama3.1:8b is not loaded."
    assert running_model_matches("gemma4:12b", "gemma4:12b")
    assert not running_model_matches("gemma4:12b", "qwen3.5:9b")


def test_ollama_tool_keeps_name_and_required_fields():
    tool = ollama_tool(Tool())
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "get_clause"
    assert tool["function"]["parameters"]["required"] == ["adr", "clause"]
    assert "title" not in tool["function"]["parameters"]
    assert tool["function"]["parameters"]["properties"]["adr"] == {"type": "string"}


def test_lookup_line_skips_empty_arguments():
    assert format_lookup("get_clause", {"adr": "ADR-13", "clause": "8.1.4"}) == (
        "looking up: get_clause(ADR-13, 8.1.4)"
    )
    assert format_lookup("list_requirements", {"adr": "ADR-13", "project_id": ""}) == (
        "looking up: list_requirements(ADR-13)"
    )


def test_split_command():
    assert split_command("/model qwen3.5:9b") == ("model", "qwen3.5:9b")
    assert split_command("/CONTEXT") == ("context", "")
    assert split_command("/quit") == ("quit", "")
