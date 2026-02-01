from memory.mongoFile import db

collection = db["gdrive"]

class MongoDatabase:
    def save_gdrive_token(self, user_id, token_data):
        """
        Upserts the Google Drive OAuth token for a user.
        """
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"gdrive_token": token_data}},
            upsert=True
        )

    def get_gdrive_token(self, user_id):
        """
        Retrieves the Google Drive token for a user.
        """
        user = collection.find_one({"user_id": user_id})
        return user.get("gdrive_token") if user else None

    def delete_gdrive_token(self, user_id):
        """
        Removes the token if it becomes invalid.
        """
        collection.update_one(
            {"user_id": user_id},
            {"$unset": {"gdrive_token": ""}}
        )

    def get_app_config():
        """
        Fetches the App Credentials (client_id, client_secret).
        This must be uploaded to MongoDB once via a setup script.
        """
        doc = collection.find_one({"_id": "app_config"})
        return doc.get("data") if doc else None