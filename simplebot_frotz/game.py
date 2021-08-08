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
        prompt_symbol=">",
        reformat_spacing=True,
    ) -> None:
        self.screen_width = 250
        self.logger = logger
        self.story_file = story_file
        self.save_file = save_file
        self.prompt_symbol = prompt_symbol
        self.reformat_spacing = reformat_spacing
        self._init_frotz(interpreter)

    def _init_frotz(self, interpreter: str) -> None:
        self.frotz = subprocess.Popen(  # noqa
            (interpreter, "-m", "-Z0", f"-w{self.screen_width}", self.story_file),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        sleep(0.1)  # Allow to load

        lines = self._read(reformat=False).split("\n")[2:]
        if lines and lines[0].lower().strip() == "found zcode chunk in blorb file.":
            lines.pop(0)
        self.intro = self._reformat("\n".join(lines))
        if not self.intro:
            self.stop()
            raise ValueError(f"Invalid Game: {self.story_file!r}")

        # Load game save
        if os.path.exists(self.save_file):
            self.load(self.save_file)

    def _read(
        self, prompts: tuple = None, include_prompt: bool = False, reformat: bool = None
    ) -> str:
        """Read from frotz interpreter process."""
        prompts = tuple(
            prompt.encode() for prompt in (prompts or (self.prompt_symbol,))
        )
        reformat = self.reformat_spacing if reformat is None else reformat
        output = b""
        while True:
            rlist, _, _ = select.select([self.frotz.stdout], [], [], 1)
            if self.frotz.stdout in rlist:
                chunk = self.frotz.stdout.read(len(self.frotz.stdout.peek()))  # type: ignore
                if not chunk:
                    return ""
                output += chunk
            elif any(map(lambda p: p in output, prompts)):
                for prompt in prompts:
                    index = output.rfind(prompt)
                    if index != -1:
                        output = output[: index + int(include_prompt)]
                        break
                break
            elif output.endswith(b"\n"):
                self.logger.debug("Received MORE-like input")
                self.frotz.stdin.write(b"\n")  # type: ignore
                self.frotz.stdin.flush()  # type: ignore
                if output.endswith(b"]\n"):
                    output = output[: output.rfind(b"[")]
            else:
                self.logger.debug(f"Unexpected end of file, after reading: {output!r}")
                return ""
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
        return formated

    def _check(self, response: str) -> None:
        if not response:
            self.stop()
            raise ValueError("Unexpected result")

    def save(self, filename=None) -> None:
        """Save game state."""
        filename = filename or self.save_file
        self._check(self.do("save", (":",)))
        self.frotz.stdin.write(filename.encode() + b"\n")  # type: ignore
        self.frotz.stdin.flush()  # type: ignore
        response = self._read(("?", self.prompt_symbol), include_prompt=True)
        self._check(response)
        if response.endswith("?"):  # Indicates an overwrite query
            self._check(self.do("y"))  # reply yes
        self.logger.debug("Game saved.")

    def load(self, filename=None) -> None:
        """Restore saved game."""
        filename = filename or self.save_file
        self._check(self.do("restore", (":",)) or self.do("load", (":",)))
        self._check(self.do(filename))
        self.logger.debug("Game restored.")

    def do(self, action: str, prompts: tuple = None) -> str:  # noqa
        """Write a command to the interpreter.

        If stop is True, the Frotz interpreter will be stop after
        getting the command response.
        """
        self.frotz.stdin.write(action.encode(errors="ignore") + b"\n")  # type: ignore
        self.frotz.stdin.flush()  # type: ignore
        return self._read(prompts)

    def ended(self) -> bool:
        """Return True if game is over, False otherwise."""
        return self.frotz.poll() is not None

    def stop(self) -> None:
        """Stop Frotz interpreter"""
        self.frotz.kill()
