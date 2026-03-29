from memory.mongoFile import MONGO_AVAILABLE, async_db
from memory.local_store import AsyncLocalCollection
from datetime import datetime, timedelta

if MONGO_AVAILABLE:
    collection = async_db["productivity_logs"]
else:
    collection = AsyncLocalCollection("productivity_logs")


class ProductivityDB:
    async def add_log(self, user_id, content, score, summary):
        entry = {
            "user_id": user_id,
            "content": content,
            "score": score,
            "summary": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
        await collection.insert_one(entry)

    async def get_logs(self, user_id=None, start_date=None, end_date=None):
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        query = {"timestamp": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}}
        if user_id:
            query["user_id"] = user_id

        cursor = collection.find(query).sort("timestamp", 1)
        return await cursor.to_list(length=1000)

    async def get_leaderboard(self, start_date=None, end_date=None):
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}}},
            {"$group": {
                "_id": "$user_id",
                "avg_score": {"$avg": "$score"},
                "total_entries": {"$sum": 1}
            }},
            {"$sort": {"avg_score": -1}}
        ]
        return await collection.aggregate(pipeline).to_list(length=20)


productivity_db = ProductivityDB()