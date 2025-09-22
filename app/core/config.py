from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    CANDIDATE_SERVICE_URL: str = Field(..., env="CANDIDATE_SERVICE_URL")
    EMPLOYER_SERVICE_URL: str = Field(..., env="EMPLOYER_SERVICE_URL")
    SEARCH_SERVICE_URL: str = Field(..., env="SEARCH_SERVICE_URL")
    FILE_SERVICE_URL: str = Field(..., env="FILE_SERVICE_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

BOT_TOKEN = settings.BOT_TOKEN
CANDIDATE_SERVICE_URL = settings.CANDIDATE_SERVICE_URL
EMPLOYER_SERVICE_URL = settings.EMPLOYER_SERVICE_URL
SEARCH_SERVICE_URL = settings.SEARCH_SERVICE_URL
FILE_SERVICE_URL = settings.FILE_SERVICE_URL