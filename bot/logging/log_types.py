from enum import Enum

class LogType(str, Enum):
    MESSAGE = "message"
    COMMAND = "command"
    VOICE = "voice"
    MEMBER = "member"
    ADMIN = "admin"
    ERROR = "error"
