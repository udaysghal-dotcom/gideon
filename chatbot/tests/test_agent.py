"""Checks for context totals, the ollama ps processor label, streaming, and chat commands."""

import asyncio

from ollama import ChatResponse, Message, ResponseError

from chatbot.agent import (
    ChatSession,
    context_after_trim,
    ollama_tool,
    processor_for,
    processor_label,
    running_model_matches,
)
from chatbot.chat import format_lookup, split_command
from chatbot.racecar import frame


class FakeOllama:
    """Streams canned chunks and remembers the think flag of each call."""

    def __init__(self, chunks, supports_thinking=True):
        self.chunks = chunks
        self.supports_thinking = supports_thinking
        self.think_calls = []

    async def chat(self, think=None, stream=False, **kwargs):
        self.think_calls.append(think)
        if think and not self.supports_thinking:
            raise ResponseError('"tiny" does not support thinking')

        async def generate():
            for chunk in self.chunks:
                yield chunk

        return generate()


def chunk(content="", thinking=None, done=False):
    return ChatResponse(
        message=Message(role="assistant", content=content, thinking=thinking),
        done=done,
        prompt_eval_count=100 if done else None,
        eval_count=20 if done else None,
    )


def session_with(fake):
    session = ChatSession()
    session._ollama = fake
    session.messages = [{"role": "system", "content": "rules"}]
    session.think = True
    return session


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
    assert split_command("/Process-Hide") == ("process-hide", "")


def test_answer_streams_thinking_and_joins_content():
    fake = FakeOllama([
        chunk(thinking="Look up "),
        chunk(thinking="ADR-13."),
        chunk(content="- ADR-13 "),
        chunk(content="cl. 8.1.4", done=True),
    ])
    session = session_with(fake)
    seen = []
    answer = asyncio.run(session.ask("What is ADR-13?", on_thinking=seen.append))
    assert answer == "- ADR-13 cl. 8.1.4"
    assert seen == ["Look up ", "ADR-13."]
    assert session.messages[-1] == {"role": "assistant", "content": answer}
    assert session.context_tokens > 0


def test_model_without_thinking_is_retried_without_it():
    fake = FakeOllama([chunk(content="Nothing found.", done=True)], supports_thinking=False)
    session = session_with(fake)
    assert asyncio.run(session.ask("Anything?")) == "Nothing found."
    assert asyncio.run(session.ask("Again?")) == "Nothing found."
    assert fake.think_calls == [True, False, False]
