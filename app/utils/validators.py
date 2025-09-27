import logging
import re
from typing import Optional, Dict, List
from datetime import date, datetime
from urllib.parse import urlparse
import phonenumbers
from pydantic import BaseModel, Field, validator, ValidationError
from app.core.messages import Messages

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PRESENT_ALIASES = {"сейчас", "н.в.", "present", "текущее", "настоящее", "настоящее время"}
DATE_FORMAT = "%Y-%m-%d"

class Experience(BaseModel):
    """Модель для опыта работы."""
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
                parsed_date = datetime.strptime(value, DATE_FORMAT).date()
                return parsed_date
            except ValueError:
                raise ValueError(Messages.Common.INVALID_INPUT)
        return value

    @validator('start_date')
    def start_not_future(cls, v):
        if v > date.today():
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator('end_date')
    def end_after_start(cls, v, values):
        start = values.get('start_date')
        if v and start and v < start:
            raise ValueError(Messages.Common.INVALID_INPUT)
        if v and v > date.today():
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

class Skill(BaseModel):
    """Модель для навыка."""
    skill: str = Field(min_length=2, max_length=50)
    kind: str = Field(pattern=r'^(hard|tool|language)$')
    level: int = Field(ge=1, le=5)

class Project(BaseModel):
    """Модель для проекта."""
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
    """Модель для контактов."""
    email: Optional[str] = None
    phone: Optional[str] = None
    telegram: Optional[str] = None

    @validator('email', pre=True)
    def check_email(cls, v):
        if v and not EMAIL_RE.match(v):
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator('phone', pre=True)
    def check_phone(cls, v):
        if v:
            try:
                parsed = phonenumbers.parse(v, None)
                if not phonenumbers.is_valid_number(parsed):
                    raise ValueError(Messages.Common.INVALID_INPUT)
            except phonenumbers.NumberParseException:
                raise ValueError(Messages.Common.INVALID_INPUT)
        return v

    @validator('telegram', pre=True)
    def check_telegram(cls, v):
        if v and not v.startswith('@'):
            raise ValueError(Messages.Common.INVALID_INPUT)
        return v

def is_valid_url(url: str) -> bool:
    """Проверка валидности URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def parse_experience_text(text: str) -> Experience:
    """Парсинг текста опыта работы."""
    lines = text.split('\n')
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
    """Парсинг текста навыка."""
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
    """Парсинг текста проекта."""
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
    """Парсинг текста контактов в модель Contacts."""
    pairs = [pair.strip() for pair in text.split(',') if pair.strip()]
    data = {}
    for pair in pairs:
        if ':' not in pair:
            raise ValueError(Messages.Common.INVALID_INPUT)
        key, value = pair.split(':', 1)
        data[key.strip().lower()] = value.strip()
    try:
        return Contacts(**data)
    except ValidationError:
        raise ValueError(Messages.Common.INVALID_INPUT)

def validate_list_length(items: List, max_length: int = 10, item_type: str = "items") -> None:
    """Валидация длины списка."""
    if len(items) > max_length:
        raise ValueError(f"Максимум {max_length} {item_type}.")

def validate_name(name: str) -> bool:
    """Валидация ФИО: минимум 2 слова, только буквы и пробелы."""
    return bool(re.match(r'^[A-Za-zА-Яа-я\s-]+$', name) and len(name.split()) >= 2)

def validate_headline_role(role: str) -> bool:
    """Валидация роли: минимум 2 символа, не пустая."""
    return len(role.strip()) >= 2

def validate_location(location: str) -> bool:
    """Валидация локации: не пустая строка."""
    return len(location.strip()) > 0