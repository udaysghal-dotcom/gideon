"""Ollama tool loop for the ADR chatbot.

The session starts the MCP server, gives the model the tool list and the
project/ADR overview, then asks Ollama questions until it writes an answer.
Tool results are dropped after each answer so the chat stays inside the
context window.
"""

import json
import math
import os
import sys
from contextlib import AsyncExitStack

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from ollama import AsyncClient

from chatbot.graph import REPO, load_env

DEFAULT_MODEL = "gemma4:12b"
DEFAULT_NUM_CTX = 16384
MAX_TOOL_ROUNDS = 6
KEEP_ALIVE = "30m"

SYSTEM_PROMPT = """You are an assistant for the SRP8 ADR compliance spreadsheet, stored as a graph.
You summarise that spreadsheet for the team. You are not an official compliance sign-off.

Rules:
- Look up every fact with the tools. Never invent ADR numbers, clause numbers, project IDs, or verification methods.
- Cite every requirement, for example "ADR-13 cl. 8.1.4".
- If nothing is found, say so plainly.
- "Must comply with" means the master sheet assigns that ADR to the project.
- A blank verification method has not been decided yet. "N/A" means it was marked as not needing verification.
- A requirement name that starts with "invalid" means the clause does not apply to this vehicle.
- Keep answers short and use bullet points."""


def _int_env(name, default):
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bool_env(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def ollama_tool(tool):
    """Turn one MCP tool into the function schema Ollama expects."""
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    properties = {}
    for name, spec in (schema.get("properties") or {}).items():
        prop = {"type": spec.get("type", "string")}
        if spec.get("description"):
            prop["description"] = spec["description"]
        if "default" in spec:
            prop["default"] = spec["default"]
        properties[name] = prop
    parameters = {"type": "object", "properties": properties}
    if schema.get("required"):
        parameters["required"] = list(schema["required"])
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": parameters,
        },
    }


def message_text(message):
    """Plain text of a chat message, including any tool-call arguments."""
    if isinstance(message, dict):
        content = message.get("content") or ""
        calls = message.get("tool_calls") or []
        if not calls:
            return content
        return content + json.dumps(calls, default=str)
    content = getattr(message, "content", None) or ""
    calls = getattr(message, "tool_calls", None) or []
    if not calls:
        return content
    dumped = []
    for call in calls:
        function = call.function
        dumped.append({"name": function.name, "arguments": dict(function.arguments or {})})
    return content + json.dumps(dumped)


def context_after_trim(prompt_tokens, completion_tokens, dropped_text="", dropped_completion_text=""):
    """Tokens still in the conversation after tool results are dropped.

    prompt_tokens and completion_tokens come from Ollama. Dropped tool text is
    estimated at about 4 characters per token and removed from that count.
    With nothing dropped, the result is the exact Ollama total.
    """
    kept_prompt = max(int(prompt_tokens) - len(dropped_text) // 4, 0)
    kept_completion = max(int(completion_tokens) - len(dropped_completion_text) // 4, 0)
    return kept_prompt + kept_completion


def processor_label(size, size_vram):
    """Same PROCESSOR text as `ollama ps`.

    Ollama uses size and size_vram from /api/ps: all VRAM is "100% GPU",
    no VRAM is "100% CPU", and a mix is "48%/52% CPU/GPU".
    """
    size = int(size or 0)
    size_vram = int(size_vram or 0)
    if size_vram == 0:
        return "100% CPU"
    if size_vram == size:
        return "100% GPU"
    if size_vram > size or size == 0:
        return "Unknown"
    cpu_percent = math.floor((size - size_vram) / size * 100 + 0.5)
    return f"{int(cpu_percent)}%/{int(100 - cpu_percent)}% CPU/GPU"


def running_model_matches(running_name, wanted):
    if not running_name or not wanted:
        return False
    return running_name == wanted or running_name.startswith(wanted)


def processor_for(models, wanted):
    """PROCESSOR column for the chat model, or a note if it is not loaded."""
    for model in models:
        names = [getattr(model, "name", None) or "", getattr(model, "model", None) or ""]
        if any(running_model_matches(name, wanted) for name in names):
            return processor_label(getattr(model, "size", 0), getattr(model, "size_vram", 0))
    return f"{wanted} is not loaded."


def tool_result_text(result):
    chunks = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    if chunks:
        return "\n".join(chunks)
    if getattr(result, "structured_content", None) is not None:
        return json.dumps(result.structured_content)
    return ""


def overview_text(result):
    chunks = []
    for item in result.contents or []:
        text = getattr(item, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


class ChatSession:
    """One conversation with Ollama and the ADR tools."""

    def __init__(self):
        load_env(REPO / ".env")
        self.model = os.environ.get("CHAT_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        self.num_ctx = _int_env("CHAT_NUM_CTX", DEFAULT_NUM_CTX)
        self.think = _bool_env("CHAT_THINK", False)
        self.messages = []
        self.tools = []
        self.context_tokens = 0
        self.last_tool_results = []
        self._ollama = None
        self._stack = None
        self._mcp = None

    async def __aenter__(self):
        self._ollama = AsyncClient()
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        try:
            server = StdioServerParameters(
                command=sys.executable,
                args=["-m", "chatbot.mcp_server"],
                cwd=str(REPO),
            )
            self._mcp = await self._stack.enter_async_context(Client(server))
            listed = await self._mcp.list_tools()
            self.tools = [ollama_tool(tool) for tool in listed.tools]
            overview = overview_text(await self._mcp.read_resource("adr://overview"))
            if not overview:
                raise RuntimeError("Could not load the project and ADR list from Neo4j.")
            self.messages = [{
                "role": "system",
                "content": f"{SYSTEM_PROMPT}\n\nKnown projects, ADRs and departments:\n{overview}",
            }]
        except Exception:
            await self._stack.aclose()
            await self._ollama.close()
            self._stack = None
            self._ollama = None
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._stack is not None:
                await self._stack.aclose()
        finally:
            if self._ollama is not None:
                await self._ollama.close()
        return False

    def reset(self):
        """Forget the conversation and keep the standing instructions."""
        if self.messages:
            self.messages = self.messages[:1]
        self.context_tokens = 0
        self.last_tool_results = []

    def context_line(self):
        """For example: '1000/16384 tokens used'."""
        return f"{(self.context_tokens * 100) // self.num_ctx}%"

    async def processor(self):
        """GPU/CPU split for this chat's model, matching `ollama ps`."""
        try:
            running = await self._ollama.ps()
        except ConnectionError:
            return "Ollama is not running."
        return processor_for(running.models, self.model)

    async def ask(self, question, on_lookup=None, on_result=None):
        """Answer one question. Call on_lookup(name, arguments) before each tool."""
        self.last_tool_results = []
        self.messages.append({"role": "user", "content": question})
        user_index = len(self.messages) - 1
        try:
            return await self._answer(user_index, on_lookup, on_result)
        except Exception:
            self.messages = self.messages[:user_index]
            raise

    async def _answer(self, user_index, on_lookup, on_result):
        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._ollama.chat(
                model=self.model,
                messages=self.messages,
                tools=self.tools,
                think=self.think,
                keep_alive=KEEP_ALIVE,
                options={"num_ctx": self.num_ctx},
            )
            reply = response.message
            self.messages.append(reply)
            calls = list(reply.tool_calls or [])
            if not calls:
                dropped = self.messages[user_index + 1 : -1]
                self.context_tokens = context_after_trim(
                    response.prompt_eval_count or 0,
                    response.eval_count or 0,
                    "\n".join(message_text(item) for item in dropped),
                    getattr(reply, "thinking", None) or "",
                )
                content = (reply.content or "").strip()
                self.messages = self.messages[: user_index + 1] + [
                    {"role": "assistant", "content": content},
                ]
                return content or "The model returned an empty answer."
            for call in calls:
                name = call.function.name
                arguments = dict(call.function.arguments or {})
                if on_lookup:
                    on_lookup(name, arguments)
                text = await self._run_tool(name, arguments)
                self.last_tool_results.append((name, text))
                if on_result:
                    on_result(name, text)
                self.messages.append({"role": "tool", "tool_name": name, "content": text})
        content = (
            "I used the lookup tools 6 times and still don't have a final answer. "
            "Please ask a narrower question."
        )
        self.messages = self.messages[: user_index + 1] + [{"role": "assistant", "content": content}]
        return content

    async def _run_tool(self, name, arguments):
        try:
            result = await self._mcp.call_tool(name, arguments)
        except Exception as exc:
            return f"Tool failed: {exc}"
        return tool_result_text(result)
