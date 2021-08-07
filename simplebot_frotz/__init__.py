"""hooks, filters and commands definitions."""

import os
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
                frotz_game = _get_game(game.name, game.player, bot)
                if os.path.exists(frotz_game.save_file):
                    os.remove(frotz_game.save_file)
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
def filter_messages(bot: DeltaBot, message: Message) -> None:
    """In the game groups you can send me instructions"""
    with session_scope() as session:
        game = session.query(Game).filter_by(chat_id=message.chat.id).first()
        if game is None:
            return
        name = game.name

    frotz_game = _get_game(name, message.get_sender_contact().addr, bot)
    response = frotz_game.do(message.text)
    if frotz_game.ended():
        message.chat.send_text(f"{response}\n\n**GAME OVER**")
        # leaving the group causes the game and save file to be deleted
        message.chat.remove_contact(bot.self_contact)
    else:
        frotz_game.stop()
        message.chat.send_text(response or "❌ Invalid command.")


@simplebot.command(name="/list")
def list_cmd(replies: Replies) -> None:
    """Get the list of available games to play."""
    text = ""
    for i, name in enumerate(os.listdir(games_dir), 1):
        name = name.rsplit(".", maxsplit=1)[0]
        text += f"▶️ /play_{i} {name}\n"
    if not text:
        text = "❌ No game available, put games files in: {games_dir}"
    replies.add(text=text)


@simplebot.command
def play(bot: DeltaBot, payload: str, message: Message, replies: Replies) -> None:
    """Start playing a game from the game list.

    Pass the number of the game in the game list.
    For example, to play the first game on the list:
    /play_1
    """
    name = os.listdir(games_dir)[int(payload)].rsplit(".", maxsplit=1)[0]
    addr = message.get_sender_contact().addr
    with session_scope() as session:
        game = session.query(Game).filter_by(name=name, player=addr).first()
        if game is None:
            chat = bot.create_group(name, [addr])
            session.add(Game(name=name, player=addr, chat_id=chat.id))
            frotz_game = _get_game(name, addr, bot)
            frotz_game.save()
            frotz_game.stop()
            replies.add(text=frotz_game.intro, chat=chat)
        else:
            text = f"❌ You are playing {name!r} already."
            replies.add(text=text, chat=bot.get_chat(game.chat_id))


def _get_folder(bot: DeltaBot) -> str:
    return os.path.join(os.path.dirname(bot.account.db_path), __name__)


def _get_game(name: str, player: str, bot: DeltaBot) -> FrotzGame:
    for filename in os.listdir(games_dir):
        if filename.startswith(name + "."):
            story_file = f"{games_dir}/{filename}"
            break
    else:
        raise ValueError(f"Game not found: {name!r}")
    save_file = f"{_get_folder(bot)}/{name}/{quote(player)}.qzl"
    return FrotzGame(story_file, save_file)
