import os, json

class Memory:

    def __init__(self):
        # Ensure the folder exists
        if not os.path.exists("memory"):
            os.makedirs("memory")

    def get_memory(self, channel_id):
        path = f"memory/session_{channel_id}.json"

        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)

        # If file does not exist → return empty list
        return []

    def save_memory(self, channel_id, data):
        path = f"memory/session_{channel_id}.json"

        # Always write the file, even if it didn’t exist
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    def memory_exists(self, channel_id):
        return os.path.exists(f"memory/session_{channel_id}.json")
