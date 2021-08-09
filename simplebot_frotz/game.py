"""Frotz engine wrapper"""

import os
import select
import subprocess
from logging import Logger
from time import sleep


class FrotzGame:  # noqa
    """Class representing an interactive fiction game."""

    def __init__(
        self,
        story_file: str,
        save_file: str,
        logger: Logger,
        interpreter: str = os.path.expanduser("~/.simplebot") + "/dfrotz",
        reformat_spacing=True,
    ) -> None:
        self.screen_width = 250
        self.logger = logger
        self.story_file = story_file
        self.save_file = save_file
        self.reformat_spacing = reformat_spacing
        self._init_frotz(interpreter)

    def _init_frotz(self, interpreter: str) -> None:
        self.frotz = subprocess.Popen(  # noqa
            (
                interpreter,
                "-m",
                "-R",
                "/dev/null",
                "-Z0",
                f"-w{self.screen_width}",
                self.story_file,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        sleep(0.1)  # Allow to load

        lines = self._read(reformat=False).split("\n")[2:]
        if lines and lines[0].lower().strip() == "found zcode chunk in blorb file.":
            lines.pop(0)
        self.intro = self._reformat("\n".join(lines))
        if not self.intro and not self.ended():
            self.intro = self.do("look")
        if not self.intro:
            self.stop()
            raise ValueError(f"Invalid Game: {self.story_file!r}")

        # Load game save
        if os.path.exists(self.save_file):
            self.load()

    def _read(self, reformat: bool = None) -> str:
        """Read from frotz interpreter process."""
        reformat = self.reformat_spacing if reformat is None else reformat
        output = b""
        while True:
            rlist, _, _ = select.select([self.frotz.stdout], [], [], 1)
            if self.frotz.stdout in rlist:
                chunk = self.frotz.stdout.read(len(self.frotz.stdout.peek()))  # type: ignore
                if not chunk:
                    break
                output += chunk
            else:
                break
        text = output.decode(errors="replace")
        return self._reformat(text) if reformat else text

    def _reformat(self, text: str) -> str:
        formated = ""
        lines = [line.strip() for line in text.split("\n")]
        for line, next_line in zip(lines, lines[1:] + [""]):
            if line:
                formated += line
                if next_line and not line.endswith("."):
                    size = len(line + next_line.split()[0]) + 1
                    if size > self.screen_width:
                        formated += " "
                        continue
                formated += "\n"
        return formated.strip()

    def save_action(self, action: str, filename=None) -> None:
        """Save action/command."""
        filename = filename or self.save_file
        with open(filename, "a") as file:
            if not action.endswith("\n"):
                action += "\n"
            file.write(action)

    def load(self, filename=None) -> None:
        """Restore saved game."""
        filename = filename or self.save_file
        with open(filename) as file:
            self.do(file.read())
        self.logger.debug("Game restored.")

    def do(self, action: str) -> str:  # noqa
        """Write a command to the interpreter."""
        if not action.endswith("\n"):
            action += "\n"
        self.frotz.stdin.write(action.encode(errors="ignore"))  # type: ignore
        self.frotz.stdin.flush()  # type: ignore
        return self._read()

    def ended(self) -> bool:
        """Return True if Frotz stopped, False otherwise."""
        return self.frotz.poll() is not None

    def stop(self) -> None:
        """Stop Frotz interpreter"""
        self.frotz.kill()
