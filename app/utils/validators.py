import logging
import re
from typing import Optional, Dict, List
from datetime import date, datetime
from urllib.parse import urlparse
import phonenumbers
from pydantic import BaseModel, Field, validator, ValidationError

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PRESENT_ALIASES = {"сейчас", "н.в.", "present", "текущее", "настоящее", "настоящее время"}
DATE_FORMAT = "%Y-%m-%d"

class Experience(BaseModel):
    company: str = Field(min_length=2, max_length=100)
    position: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: Optional[date]
    responsibilities: Optional[str] = Field(max_length=1000)

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }

    @validator('start_date', 'end_date', pre=True)
    def parse_date(cls, value):
        if isinstance(value, str):
            value = value.strip().lower()
            if value in PRESENT_ALIASES:
                return None
            try:
                return datetime.strptime(value, DATE_FORMAT).date()
            except ValueError:
                raise ValueError(f"Неверный формат даты: {value}. Используйте YYYY-MM-DD или 'сейчас'.")
        return value

    @validator('end_date')
    def end_after_start(cls, v, values):
        start = values.get('start_date')
        if v and start and v < start:
            raise ValueError("Дата окончания не может быть раньше даты начала.")
        if v and v > date.today():
            raise ValueError("Дата окончания не может быть в будущем.")
        return v

class Skill(BaseModel):
    skill: str = Field(min_length=2, max_length=50)
    kind: str = Field(pattern=r'^(hard|tool|language)$')
    level: int = Field(ge=1, le=5)

class Project(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(max_length=500)
    links: Optional[Dict[str, str]] = None

    @validator('links')
    def validate_links(cls, v):
        if v:
            for key, url in v.items():
                if not is_valid_url(url):
                    raise ValueError(f"Неверный URL: {url}")
        return v

class Contacts(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None

    @validator('email')
    def validate_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError("Неверный формат email.")
        return v

    @validator('phone')
    def validate_phone(cls, v):
        if v:
            try:
                parsed = phonenumbers.parse(v, None)
                if not phonenumbers.is_possible_number(parsed):
                    raise ValueError("Неверный формат телефона.")
            except phonenumbers.NumberParseException:
                raise ValueError("Неверный формат телефона.")
        return v

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False

def parse_experience_text(text: str) -> Experience:
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    data = {}
    for line in lines:
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip().lower()] = val.strip()
    required_keys = ['company', 'position', 'start_date']
    if not all(k in data for k in required_keys):
        raise ValueError(f"Обязательные поля: {', '.join(required_keys)}.")
    try:
        return Experience(**data)
    except ValidationError as e:
        logger.error(f"Validation error in experience: {e}")
        raise ValueError(str(e))

def parse_skill_text(text: str) -> Skill:
    parts = [part.strip() for part in text.split(',')]
    data = {}
    for part in parts:
        if ':' in part:
            key, val = part.split(':', 1)
            data[key.strip().lower()] = val.strip()
    required_keys = ['name', 'kind', 'level']
    if not all(k in data for k in required_keys):
        raise ValueError(f"Обязательные поля: {', '.join(required_keys)}.")
    data['skill'] = data.pop('name')
    data['level'] = int(data['level'])
    try:
        return Skill(**data)
    except ValidationError as e:
        logger.error(f"Validation error in skill: {e}")
        raise ValueError(str(e))

def parse_project_text(title: str, description: Optional[str], links_text: Optional[str]) -> Project:
    links = {}
    if links_text:
        parts = [part.strip() for part in links_text.split(',')]
        for part in parts:
            if ':' in part and not part.lower().startswith("http"):
                key, val = part.split(':', 1)
                links[key.strip().lower()] = val.strip()
            else:
                links["main_link"] = part
    data = {
        'title': title,
        'description': description,
        'links': links if links else None
    }
    try:
        return Project(**data)
    except ValidationError as e:
        logger.error(f"Validation error in project: {e}")
        raise ValueError(str(e))

def parse_contacts_text(text: str) -> Contacts:
    pairs = [pair.strip() for pair in text.split(',') if pair.strip()]
    data = {}
    for pair in pairs:
        if ':' not in pair:
            raise ValueError("Формат: key:value, key2:value2.")
        key, value = pair.split(':', 1)
        data[key.strip().lower()] = value.strip()
    try:
        return Contacts(**data)
    except ValidationError as e:
        logger.error(f"Validation error in contacts: {e}")
        raise ValueError(str(e))

def validate_list_length(items: List, max_length: int = 10, item_type: str = "items"):
    if len(items) > max_length:
        raise ValueError(f"Максимум {max_length} {item_type}.")
