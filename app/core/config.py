import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

CANDIDATE_SERVICE_URL = os.getenv("CANDIDATE_SERVICE_URL")