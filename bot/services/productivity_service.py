import spacy
import pandas as pd
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from dateutil import parser as date_parser
from datetime import datetime, timedelta
from memory.mongoFile import db

# Load lightweight English model
# Remember to run: python -m spacy download en_core_web_sm
nlp = spacy.load("en_core_web_sm")
collection = db["productivity_logs"]

class ProductivityService:
    def __init__(self):
        self.summarizer = LsaSummarizer()

    def get_metrics(self, text):
        """Uses spaCy to estimate a productivity score (1-10) based on keywords."""
        doc = nlp(text.lower())
        score = 5

        # Weighted keywords for local NLP analysis
        boost = ["code", "study", "work", "build", "learn", "gym", "read", "practice", "coding", "exercise"]
        drop = ["gaming", "game", "netflix", "youtube", "slept", "scrolled", "lazy", "val", "cs", "movie"]

        for token in doc:
            if token.lemma_ in boost: 
                score += 1
            if token.lemma_ in drop: 
                score -= 1
        
        return max(1, min(10, score))

    def summarize(self, text):
        """Condenses updates into a single sentence using LSA summarization."""
        if len(text.split()) < 12: 
            return text

        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summary_sentences = self.summarizer(parser.document, 1)

        return str(summary_sentences[0]) if summary_sentences else text

    def parse_dates(self, start_str=None, end_str=None):
        """Intelligently parses user input strings into datetime objects."""
        try:
            end_date = date_parser.parse(end_str) if end_str else datetime.utcnow()
            if start_str:
                start_date = date_parser.parse(start_str)
            else:
                # Default to last 7 days if no start date provided
                start_date = end_date - timedelta(days=7)
            return start_date, end_date
        except Exception:
            return None, None

    async def save_entry(self, user_id, content, event_type="SENT"):
        """Processes and saves a productivity log entry to MongoDB."""
        score = self.get_metrics(content)
        summary = self.summarize(content)

        entry = {
            "user_id": user_id,
            "content": content,
            "summary": summary,
            "score": score,
            "event": event_type,
            "timestamp": datetime.utcnow()
        }

        return await collection.insert_one(entry)

    async def get_stats_dataframe(self, user_id=None, start_date=None, end_date=None):
        """Fetches logs for a date range and returns a Pandas DataFrame."""
        # Use provided dates or default to the last 7 days
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=7)

        query = {"timestamp": {"$gte": start_date, "$lte": end_date}}
        if user_id:
            query["user_id"] = user_id

        # Using motor/pymongo to fetch data
        cursor = collection.find(query).sort("timestamp", 1)
        data = await cursor.to_list(length=1000)

        if not data:
            return None

        df = pd.DataFrame(data)
        # Create a clean date column for grouping in charts/leaderboards
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
        return df