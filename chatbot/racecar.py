"""Racecar that drives along a road in the terminal while the model thinks."""

import asyncio
import shutil
import sys

CAR = [
    "  _.-''''-._",
    " '-(o)---(o)-'",
]
ROAD = "_"
SPACES_PER_SECOND = 3
LINES = len(CAR) + 1


def frame(position, width):
    """Car rows and the road for one step, wrapping past the right edge."""
    rows = []
    for text in CAR:
        cells = [" "] * width
        for offset, char in enumerate(text):
            if char != " ":
                cells[(position + offset) % width] = char
        rows.append("".join(cells).rstrip())
    rows.append(ROAD * width)
    return rows


class Racecar:
    """Draws the car below the cursor until stop() erases it.

    Nothing is drawn when stdout is not a terminal.
    """

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.enabled = self.stream.isatty()
        self.position = 0
        self._task = None
        self._drawn = False

    def _width(self):
        # One column short of the edge so a full road never makes the terminal wrap.
        return max(shutil.get_terminal_size().columns - 1, len(max(CAR, key=len)))

    def _erase(self):
        if self._drawn:
            self.stream.write(f"\033[{LINES}F\033[J")
            self._drawn = False

    def _draw(self):
        self._erase()
        self.stream.write("\n".join(frame(self.position, self._width())) + "\n")
        self.stream.flush()
        self._drawn = True

    async def _drive(self):
        while True:
            self._draw()
            await asyncio.sleep(1 / SPACES_PER_SECOND)
            self.position = (self.position + 1) % self._width()

    def start(self):
        if self.enabled and self._task is None:
            self._task = asyncio.create_task(self._drive())

    async def stop(self):
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._erase()
        self.stream.flush()

    def print(self, text):
        """Print above the car without breaking the animation."""
        if not self._drawn:
            print(text, file=self.stream, flush=True)
            return
        self._erase()
        print(text, file=self.stream)
        self._draw()
