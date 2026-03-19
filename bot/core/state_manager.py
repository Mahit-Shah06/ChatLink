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
        self.log_channels: Dict[LogType, int] = {}

    def update(self, category: LogType, key: int, data: Dict[str, Any]):
        self._states[category][key] = EventState(
                data = data, 
                timestamp = datetime.utcnow()
        )

    def get_state(self, category: LogType, key: int):
        return self._states[category].get(key)

state = StateManager()
