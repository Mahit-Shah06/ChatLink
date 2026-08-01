"""ChatLink Learning Engine.

Passive study capture, classification and analytics. Discord is the interface;
SQLite is the store. Nothing in this package imports discord.py — the adapter
lives in bot/events/on_learning.py.
"""

from .capture import CaptureEngine, get_engine
from .models import (Attachment, ChannelContext, Classification, IncomingMessage,
                     Label, ProcessedMessage, TopicMatch)

__version__ = "1.0.0"
__all__ = ["CaptureEngine", "get_engine", "IncomingMessage", "ChannelContext",
           "Attachment", "Classification", "TopicMatch", "ProcessedMessage", "Label"]
