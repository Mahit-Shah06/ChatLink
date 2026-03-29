import discord
from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime
from bot.logging.log_types import LogType


@dataclass
class EventState:
    data: Dict[str, Any]
    timestamp: datetime


class StateManager:
    def __init__(self):
        self._states: Dict[LogType, Dict[int, EventState]] = {
            lt: {} for lt in LogType
        }
        # { guild_id: { LogType: channel_id } }
        self.log_channels: Dict[int, Dict[LogType, int]] = {}
        # { guild_id: { LogType: bool } }
        self.toggles: Dict[int, Dict[LogType, bool]] = {}

    def update(self, category: LogType, key: int, data: Dict[str, Any]):
        self._states[category][key] = EventState(
            data=data,
            timestamp=datetime.utcnow()
        )

    def get_state(self, category: LogType, key: int):
        return self._states[category].get(key)

    def get_log_channel(self, guild_id: int, log_type: LogType):
        return self.log_channels.get(guild_id, {}).get(log_type)

    def set_log_channel(self, guild_id: int, log_type: LogType, channel_id: int):
        self.log_channels.setdefault(guild_id, {})[log_type] = channel_id

    def is_enabled(self, guild_id: int, log_type: LogType) -> bool:
        return self.toggles.get(guild_id, {}).get(log_type, True)

    def toggle(self, guild_id: int, log_type: LogType) -> bool:
        current = self.is_enabled(guild_id, log_type)
        self.toggles.setdefault(guild_id, {})[log_type] = not current
        return not current


state = StateManager()