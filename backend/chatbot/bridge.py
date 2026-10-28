"""JSON-lines bridge between the Ink UI and the chat session.

Run with: python -m chatbot.bridge

Reads one JSON object per line on stdin:
    {"type": "ask", "text": "..."}
    {"type": "reset"}
    {"type": "model", "name": "..."}   (empty name reports the current model)
    {"type": "context"}
    {"type": "processor"}
Writes one JSON object per line on stdout:
    {"type": "ready", "model": "...", "num_ctx": 16384}
    {"type": "thinking", "text": "..."}
    {"type": "lookup", "text": "looking up: ..."}
    {"type": "answer", "text": "..."}
    {"type": "info", "text": "..."}
    {"type": "model", "model": "..."}
    {"type": "error", "text": "..."}
    {"type": "done"}
Anything else printed goes to stderr so stdout stays clean.
"""

import asyncio
import json
import sys

import ollama

from chatbot.agent import ChatSession
from chatbot.chat import format_lookup

_out = sys.stdout
sys.stdout = sys.stderr


def send(**event):
    _out.write(json.dumps(event) + "\n")
    _out.flush()


async def read_lines():
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return
        line = line.strip()
        if line:
            yield line


async def handle_ask(session, text):
    try:
        answer = await session.ask(
            text,
            on_lookup=lambda name, arguments: send(type="lookup", text=format_lookup(name, arguments)),
            on_thinking=lambda piece: send(type="thinking", text=piece),
        )
        send(type="answer", text=answer)
    except ConnectionError:
        send(type="error", text="Ollama is not running. Start it with: brew services start ollama")
    except ollama.ResponseError as exc:
        send(type="error", text=str(exc).strip())
    except Exception as exc:
        send(type="error", text=f"Something went wrong: {exc}")
    finally:
        send(type="done")


async def run():
    try:
        async with ChatSession() as session:
            send(type="ready", model=session.model, num_ctx=session.num_ctx)
            async for line in read_lines():
                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    send(type="error", text="Bad request.")
                    continue
                kind = request.get("type")
                if kind == "ask":
                    await handle_ask(session, str(request.get("text", "")))
                elif kind == "reset":
                    session.reset()
                    send(type="info", text="Conversation cleared.")
                    send(type="done")
                elif kind == "model":
                    name = str(request.get("name", "")).strip()
                    if name:
                        session.model = name
                        send(type="model", model=session.model)
                        send(type="info", text=f"Model is now {session.model}.")
                    else:
                        send(type="info", text=f"Model is {session.model}.")
                    send(type="done")
                elif kind == "context":
                    send(type="info", text=f"Context used: {session.context_line()}")
                    send(type="done")
                elif kind == "processor":
                    send(type="info", text=await session.processor())
                    send(type="done")
                else:
                    send(type="error", text=f"Unknown request type: {kind}")
    except Exception as exc:
        send(type="error", text=f"Could not start the chat: {exc}")


def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
