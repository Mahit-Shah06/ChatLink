"""ChatLink Learning Engine.

Passive study capture. Discord is the interface; SQLite is the store.
Nothing in this package imports discord.py — the adapter lives in bot/events/.
"""

from .capture import CaptureEngine, get_engine
from .models import Attachment, ChannelContext, IncomingMessage

__version__ = "0.2.0"
__all__ = ["CaptureEngine", "get_engine", "IncomingMessage", "ChannelContext", "Attachment"]
