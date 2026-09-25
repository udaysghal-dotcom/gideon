"""Terminal chat for the ADR graph. Run with: python -m chatbot.chat"""

import asyncio
import sys

import ollama

from chatbot.agent import ChatSession
from chatbot.racecar import Racecar
from design.logo import Logo

COMMANDS = (
    "/reset, /model <name>, /debug, /context, /processor, "
    "/process, /process-show, /process-hide, /quit"
)


def grey(text):
    if not sys.stdout.isatty():
        return text
    return f"\033[90m{text}\033[0m"


def format_lookup(name, arguments):
    """For example: looking up: get_clause(ADR-13, 8.1.4)"""
    if not isinstance(arguments, dict):
        arguments = {}
    parts = [str(value) for value in arguments.values() if value is not None and value != ""]
    return f"looking up: {name}({', '.join(parts)})"


def split_command(line):
    """'/model gemma4:12b' becomes ('model', 'gemma4:12b')."""
    body = line.strip()[1:]
    command, _, rest = body.partition(" ")
    return command.lower(), rest.strip()


def process_mode(show):
    if show:
        return "Thinking is shown. Thinking and lookups will appear while the model works."
    return "Thinking is hidden. A racecar will drive while the model works."


async def chat_loop(session):
    debug = False
    show_process = True
    thinking_open = False
    car = Racecar()

    def end_thinking():
        nonlocal thinking_open
        if thinking_open:
            print(flush=True)
            thinking_open = False

    def on_thinking(text):
        nonlocal thinking_open
        if not show_process:
            return
        if not thinking_open:
            print(grey("thinking: "), end="")
            thinking_open = True
        print(grey(text), end="", flush=True)

    def on_lookup(name, arguments):
        if show_process:
            end_thinking()
            print(grey(format_lookup(name, arguments)), flush=True)

    def on_result(name, text):
        if not debug:
            return
        if show_process:
            end_thinking()
            print(grey(f"{name} result:\n{text}"), flush=True)
        else:
            car.print(grey(f"{name} result:\n{text}"))

    Logo().print()
    print(f"ADR compliance assistant. Model {session.model}, context {session.num_ctx}.")
    print(f"Commands: {COMMANDS}")
    while True:
        try:
            line = await asyncio.to_thread(input, "You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            command, rest = split_command(line)
            if command == "quit":
                return
            if command == "reset":
                session.reset()
                print("Conversation cleared.")
                continue
            if command == "model":
                if not rest:
                    print(session.model)
                else:
                    session.model = rest
                    print(f"Model is now {session.model}.")
                continue
            if command == "debug":
                debug = not debug
                if debug:
                    print("Debug is on. Tool results will be shown.")
                    for name, text in session.last_tool_results:
                        print(grey(f"{name} result:\n{text}"))
                else:
                    print("Debug is off.")
                continue
            if command == "context":
                print(session.context_line())
                continue
            if command == "processor":
                print(await session.processor())
                continue
            if command in {"process", "process-show", "process-hide"}:
                if command == "process":
                    show_process = not show_process
                else:
                    show_process = command == "process-show"
                print(process_mode(show_process))
                continue
            print(f"Unknown command. Commands: {COMMANDS}")
            continue
        car = Racecar()
        if not show_process:
            print()
            car.start()
        try:
            try:
                answer = await session.ask(
                    line,
                    on_lookup=on_lookup,
                    on_result=on_result,
                    on_thinking=on_thinking,
                )
            finally:
                await car.stop()
                end_thinking()
        except KeyboardInterrupt:
            print()
            return
        except ConnectionError:
            print("Ollama is not running. Start it with: brew services start ollama")
            continue
        except ollama.ResponseError as exc:
            print(str(exc).strip())
            continue
        except Exception as exc:
            print(f"Something went wrong: {exc}")
            continue
        print()
        print(answer)
        print()


async def run():
    try:
        async with ChatSession() as session:
            await chat_loop(session)
    except KeyboardInterrupt:
        print()
    except Exception as exc:
        print(f"Could not start the chat: {exc}")

def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
