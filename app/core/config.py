import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CANDIDATE_SERVICE_URL = os.getenv("CANDIDATE_SERVICE_URL")
EMPLOYER_SERVICE_URL = os.getenv("EMPLOYER_SERVICE_URL")
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL")
FILE_SERVICE_URL = os.getenv("FILE_SERVICE_URL")