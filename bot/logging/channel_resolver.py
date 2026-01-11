from bot.logging.log_types import LogType

CHANNEL_MAP = {
    LogType.MESSAGE: "message-logs",
    LogType.COMMAND: "command-logs",
    LogType.VOICE: "voice-logs",
    LogType.MEMBER: "member-logs",
    LogType.ADMIN: "admin-logs",
    LogType.ERROR: "error-logs",
}

def resolve_channel(log_type: LogType):
    return CHANNEL_MAP.get(log_type)
