"""Terminal chat for the ADR graph. Run with: python -m chatbot.chat"""

import asyncio
import sys

import ollama

from chatbot.agent import ChatSession

COMMANDS = "/reset, /model <name>, /debug, /context, /processor, /quit"


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


async def chat_loop(session):
    debug = False

    def on_lookup(name, arguments):
        print(grey(format_lookup(name, arguments)), flush=True)

    def on_result(name, text):
        if debug:
            print(grey(f"{name} result:\n{text}"), flush=True)

    print(f"ADR compliance chat. Model {session.model}, context {session.num_ctx}.")
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
            print(f"Unknown command. Commands: {COMMANDS}")
            continue
        try:
            answer = await session.ask(line, on_lookup=on_lookup, on_result=on_result)
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
