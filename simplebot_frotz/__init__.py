"""hooks, filters and commands definitions."""

import os
from typing import Optional
from urllib.parse import quote

import simplebot
from deltachat import Chat, Contact, Message
from pkg_resources import DistributionNotFound, get_distribution
from simplebot.bot import DeltaBot, Replies

from .game import FrotzGame
from .orm import Game, init, session_scope

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = "0.0.0.dev0-unknown"
games_dir = os.path.expanduser("~/.simplebot/frotz-games")


@simplebot.hookimpl
def deltabot_member_removed(bot: DeltaBot, contact: Contact, chat: Chat) -> None:
    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=chat.id).first()
        if game:
            if contact.addr in (game.player, bot.self_contact.addr):
                try:
                    os.remove(_get_save_file(_get_folder(bot), game.name, game.player))
                except FileNotFoundError:
                    pass
                session.delete(game)
                try:
                    chat.remove_contact(bot.self_contact)
                except ValueError:
                    pass


@simplebot.hookimpl
def deltabot_start(bot: DeltaBot) -> None:
    path = _get_folder(bot)
    if not os.path.exists(path):
        os.makedirs(path)
    path = os.path.join(path, "sqlite.db")
    init(f"sqlite:///{path}")


@simplebot.filter
def filter_messages(bot: DeltaBot, message: Message, replies: Replies) -> None:
    """Once you start a game, you must send me text messages with instructions in the game group.

    What instructions/verbs are supported depends of the game and game
    language, usually if you send "help" you will get the game's help.
    If you are new to Interactive Fiction read:
    https://www.ifwiki.org/index.php/Starters
    https://en.wikipedia.org/wiki/Interactive_fiction
    """
    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if game is None:
            return
        name = game.name

    text = " ".join(message.text.split())
    if text.startswith("\\") or text in ("save", "load", "restore", "quit"):
        response = ""
        game_over = False
    else:
        try:
            frotz_game = _get_game(name, message.get_sender_contact().addr, bot)
            response = frotz_game.do(text)
            game_over = frotz_game.ended()
            if not game_over and response:
                frotz_game.save()
            frotz_game.stop()
        except ValueError:
            response = ""
            game_over = False
    if game_over:
        message.chat.send_text(f"{response}\n\n**GAME OVER**")
        # leaving the group causes the game and save file to be deleted
        message.chat.remove_contact(bot.self_contact)
    else:
        replies.add(text=response or "❌ Invalid command.")


@simplebot.command(name="/list")
def list_cmd(replies: Replies) -> None:
    """Get the list of available games to play."""
    text = ""
    for i, name in enumerate(_get_games(), 1):
        name = name.rsplit(".", maxsplit=1)[0]
        text += f"▶️ /play_{i} {name}\n"
    if not text:
        text = f"❌ No game available, put games files in: {games_dir}"
    replies.add(text=text)


@simplebot.command
def play(bot: DeltaBot, payload: str, message: Message, replies: Replies) -> None:
    """Start playing a game from the game list.

    Pass the number of the game in the game list.
    For example, to play the first game on the list:
    /play_1
    """
    numb = int(payload) - 1 if payload.isdigit() else -1
    games = _get_games()
    if numb >= len(games) or numb < 0:
        replies.add(text="❌ Invalid game number.")
        return
    name = games[numb].rsplit(".", maxsplit=1)[0]
    addr = message.get_sender_contact().addr
    with session_scope() as session:
        game = session.query(Game).filter_by(name=name, player=addr).first()
        if game is None:
            chat = bot.create_group(name, [addr])
            session.add(Game(name=name, player=addr, chat_id=chat.id))
            frotz_game = _get_game(name, addr, bot)
            frotz_game.save()
            frotz_game.stop()
            image = _get_artwork(name)
            if image:
                chat.set_profile_image(image)
            replies.add(text=frotz_game.intro, filename=image, chat=chat)
        else:
            text = f"❌ You are playing {name!r} already."
            replies.add(text=text, chat=bot.get_chat(game.chat_id))


def _get_folder(bot: DeltaBot) -> str:
    return os.path.join(os.path.dirname(bot.account.db_path), __name__)


def _get_games() -> list:
    return [
        name
        for name in sorted(os.listdir(games_dir))
        if not name.endswith((".jpg", ".jpeg", ".png"))
    ]


def _get_artwork(name: str) -> Optional[str]:
    basename = f"{games_dir}/{name}"
    for ext in ("jpg", "jpeg", "png"):
        filename = f"{basename}.{ext}"
        if os.path.exists(filename):
            return filename
    return None


def _get_save_file(plugin_folder: str, name: str, player: str) -> str:
    saves_dir = f"{plugin_folder}/{name}"
    if not os.path.exists(saves_dir):
        os.makedirs(saves_dir)
    return f"{saves_dir}/{quote(player)}.qzl"


def _get_game(name: str, player: str, bot: DeltaBot) -> FrotzGame:
    for filename in _get_games():
        if filename.startswith(name + "."):
            story_file = f"{games_dir}/{filename}"
            break
    else:
        raise ValueError(f"Game not found: {name!r}")
    save_file = _get_save_file(_get_folder(bot), name, player)
    return FrotzGame(story_file, save_file, logger=bot.logger)
