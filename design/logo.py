""" Very cool I know"""

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

# Column range of "UNSW" within each SUNSWIFT row.
UNSW_START = 9
UNSW_END = 50

WHITE = "\033[38;2;255;255;255m"
YELLOW = "\033[38;2;255;230;0m"
RESET = "\033[0m"


class Logo:
    def __init__(self):
        self.text = self._render()

    @staticmethod
    def _render():
        rows = []
        for row in SUNSWIFT.splitlines():
            rows.append(
                WHITE + row[:UNSW_START]
                + YELLOW + row[UNSW_START:UNSW_END]
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
