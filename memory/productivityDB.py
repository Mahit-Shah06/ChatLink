from memory.mongoFile import db
from datetime import datetime, timedelta

collection = db["productivity_logs"]

class ProductivityDB:
    async def add_log(self, user_id, content, score, summary):
        entry = {
            "user_id": user_id,
            "content": content,
            "score": score,
            "summary": summary,
            "timestamp": datetime.utcnow()
        }
        await collection.insert_one(entry)

    async def get_logs(self, user_id=None, start_date=None, end_date=None):
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        query = {"timestamp": {"$gte": start_date, "$lte": end_date}}
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
            {"$match": {"timestamp": {"$gte": start_date, "$lte": end_date}}},
            {"$group": {
                "_id": "$user_id",
                "avg_score": {"$avg": "$score"},
                "total_entries": {"$sum": 1}
            }},
            {"$sort": {"avg_score": -1}}
        ]
        return await collection.aggregate(pipeline).to_list(length=20)

productivity_db = ProductivityDB()
