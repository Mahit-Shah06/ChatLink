import random
from memory.ssm_utils import MemAcc

class SecretSantaService:
    def __init__(self):
        self.ssm = MemAcc()

    def add_member(self, member):
        return self.ssm.add_member(member)

    def get_entries(self):
        return self.ssm.get_entries()

    def clear(self):
        self.ssm.clear()

    def generate_pairs(self):
        entries = self.ssm.get_entries()
        if len(entries) < 2:
            return None, None

        ids = [uid for uid, _ in entries]
        names = {uid: name for uid, name in entries}

        shuffled = ids[:]
        while True:
            random.shuffle(shuffled)
            if all(a != b for a, b in zip(ids, shuffled)):
                break

        return ids, shuffled, names
