""" Very cool I know """

import sys

SUNSWIFT = """\
 ███████╗ ██╗   ██╗ ███╗   ██╗ ███████╗ ██╗    ██╗ ██╗ ███████╗ ████████╗
 ██╔════╝ ██║   ██║ ████╗  ██║ ██╔════╝ ██║    ██║ ██║ ██╔════╝ ╚══██╔══╝
 ███████╗ ██║   ██║ ██╔██╗ ██║ ███████╗ ██║ █╗ ██║ ██║ █████╗      ██║
 ╚════██║ ██║   ██║ ██║╚██╗██║ ╚════██║ ██║███╗██║ ██║ ██╔══╝      ██║
 ███████║ ╚██████╔╝ ██║ ╚████║ ███████║ ╚███╔███╔╝ ██║ ██║         ██║
 ╚══════╝  ╚═════╝  ╚═╝  ╚═══╝ ╚══════╝  ╚══╝╚══╝  ╚═╝ ╚═╝         ╚═╝"""

RACING = """\
 ██████╗   █████╗   ██████╗ ██╗ ███╗   ██╗  ██████╗
 ██╔══██╗ ██╔══██╗ ██╔════╝ ██║ ████╗  ██║ ██╔════╝
 ██████╔╝ ███████║ ██║      ██║ ██╔██╗ ██║ ██║  ███╗
 ██╔══██╗ ██╔══██║ ██║      ██║ ██║╚██╗██║ ██║   ██║
 ██║  ██║ ██║  ██║ ╚██████╗ ██║ ██║ ╚████║ ╚██████╔╝
 ╚═╝  ╚═╝ ╚═╝  ╚═╝  ╚═════╝ ╚═╝ ╚═╝  ╚═══╝  ╚═════╝"""

UNSW_START = 9
UNSW_END = 50

WHITE = "\033[38;2;255;255;255m"
RESET = "\033[0m"

YELLOW_TOP = (255, 230, 0)
YELLOW_BOTTOM = (179, 134, 0)


def rgb(colour):
    red, green, blue = colour
    return f"\033[38;2;{red};{green};{blue}m"


def gradient(start, end, steps):
    if steps == 1:
        return [start]
    return [
        tuple(round(a + (b - a) * i / (steps - 1)) for a, b in zip(start, end))
        for i in range(steps)
    ]


class Logo:
    def __init__(self):
        self.text = self._render()

    @staticmethod
    def _render():
        rows = []
        sunswift = SUNSWIFT.splitlines()
        yellows = gradient(YELLOW_TOP, YELLOW_BOTTOM, len(sunswift))
        for row, yellow in zip(sunswift, yellows):
            rows.append(
                WHITE + row[:UNSW_START]
                + rgb(yellow) + row[UNSW_START:UNSW_END]
                + WHITE + row[UNSW_END:]
                + RESET
            )
        rows.append("")
        for row in RACING.splitlines():
            rows.append(WHITE + row + RESET)
        return "\n".join(rows)

    def print(self):
        if not sys.stdout.isatty():
            return
        print()
        print(self.text)
        print()
