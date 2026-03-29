import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path("data/local_db")


def _ensure_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def _read(name: str) -> List[Dict]:
    p = _path(name)
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def _write(name: str, data: List[Dict]):
    _ensure_dir()
    with open(_path(name), "w") as f:
        json.dump(data, f, default=str, indent=2)


def _matches(doc: Dict, query: Dict) -> bool:
    for k, v in query.items():
        if isinstance(v, dict):
            doc_val = doc.get(k)
            for op, op_val in v.items():
                if op == "$gte" and not (str(doc_val) >= str(op_val)):
                    return False
                if op == "$lte" and not (str(doc_val) <= str(op_val)):
                    return False
        else:
            if doc.get(k) != v:
                return False
    return True


def _apply_set(doc: Dict, set_ops: Dict) -> Dict:
    for k, v in set_ops.items():
        if "." in k:
            parts = k.split(".", 1)
            if parts[0] not in doc:
                doc[parts[0]] = {}
            doc[parts[0]][parts[1]] = v
        else:
            doc[k] = v
    return doc


class LocalCollection:
    def __init__(self, name: str):
        self.name = name

    def find_one(self, query: Optional[Dict] = None) -> Optional[Dict]:
        for doc in _read(self.name):
            if query is None or _matches(doc, query):
                return doc
        return None

    def find(self, query: Optional[Dict] = None) -> List[Dict]:
        docs = _read(self.name)
        if query is None:
            return docs
        return [d for d in docs if _matches(d, query)]

    def insert_one(self, doc: Dict):
        docs = _read(self.name)
        docs.append(json.loads(json.dumps(doc, default=str)))
        _write(self.name, docs)

    def update_one(self, filter: Dict, update: Dict, upsert: bool = False):
        docs = _read(self.name)
        found = False
        for i, doc in enumerate(docs):
            if _matches(doc, filter):
                if "$set" in update:
                    docs[i] = _apply_set(doc, update["$set"])
                found = True
                break
        if not found and upsert:
            new_doc = {**filter}
            if "$set" in update:
                new_doc = _apply_set(new_doc, update["$set"])
            docs.append(new_doc)
        _write(self.name, docs)

    def delete_one(self, filter: Dict):
        docs = _read(self.name)
        for i, doc in enumerate(docs):
            if _matches(doc, filter):
                docs.pop(i)
                break
        _write(self.name, docs)

    def delete_many(self, filter: Dict):
        if not filter:
            _write(self.name, [])
        else:
            docs = [d for d in _read(self.name) if not _matches(d, filter)]
            _write(self.name, docs)


class AsyncLocalCollection:
    def __init__(self, name: str):
        self._sync = LocalCollection(name)

    async def insert_one(self, doc: Dict):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync.insert_one, doc)

    async def find_one(self, query: Optional[Dict] = None) -> Optional[Dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync.find_one, query)

    async def update_one(self, filter: Dict, update: Dict, upsert: bool = False):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._sync.update_one(filter, update, upsert))

    async def delete_one(self, filter: Dict):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync.delete_one, filter)

    async def delete_many(self, filter: Dict):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync.delete_many, filter)

    def find(self, query: Optional[Dict] = None) -> "AsyncCursor":
        return AsyncCursor(self._sync.find(query))

    def aggregate(self, pipeline: List[Dict]) -> "AsyncCursor":
        return AsyncCursor(_run_aggregate(self._sync.name, pipeline))


class AsyncCursor:
    def __init__(self, data):
        self._data = data if isinstance(data, list) else list(data)

    def sort(self, key: str, direction: int = 1):
        self._data.sort(key=lambda d: d.get(key, 0), reverse=(direction == -1))
        return self

    async def to_list(self, length: int = 1000) -> List[Dict]:
        return self._data[:length]


def _run_aggregate(name: str, pipeline: List[Dict]) -> List[Dict]:
    docs = _read(name)
    for stage in pipeline:
        if "$match" in stage:
            docs = [d for d in docs if _matches(d, stage["$match"])]
        elif "$group" in stage:
            spec = stage["$group"]
            id_field = spec["_id"].lstrip("$")
            groups: Dict[Any, List] = {}
            for doc in docs:
                gid = doc.get(id_field)
                groups.setdefault(gid, []).append(doc)
            result = []
            for gid, group_docs in groups.items():
                entry: Dict = {"_id": gid}
                for k, v in spec.items():
                    if k == "_id":
                        continue
                    if "$avg" in v:
                        field = v["$avg"].lstrip("$")
                        vals = [d.get(field, 0) for d in group_docs]
                        entry[k] = sum(vals) / len(vals) if vals else 0
                    elif "$sum" in v:
                        if v["$sum"] == 1:
                            entry[k] = len(group_docs)
                        else:
                            field = v["$sum"].lstrip("$")
                            entry[k] = sum(d.get(field, 0) for d in group_docs)
                result.append(entry)
            docs = result
        elif "$sort" in stage:
            for k, direction in stage["$sort"].items():
                docs.sort(key=lambda d: d.get(k, 0), reverse=(direction == -1))
    return docs


class LocalDB:
    def __getitem__(self, name: str) -> LocalCollection:
        return LocalCollection(name)

    def async_collection(self, name: str) -> AsyncLocalCollection:
        return AsyncLocalCollection(name)


local_db = LocalDB()
