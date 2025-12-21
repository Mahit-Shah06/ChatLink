import os

class MemAcc:
    FILE = "SSmemory.txt"

    def __init__(self):
        if not os.path.exists(self.FILE):
            open(self.FILE, "w").close()
    
    def get_entries(self):
        with open(self.FILE, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        entries = []
        for line in lines:
            uid, name = line.split("|", 1)
            entries.append((int(uid), name))

        return entries

    def add_member(self, member):
        entries = self.get_entries()
        ids = [uid for uid, _ in entries]

        if member.id in ids:
            return False

        with open(self.FILE, "a") as f:
            f.write(f"{member.id}|{member.name}\n")

    def clear(self):
        with open(self.FILE, "w") as f:
            pass

        return True