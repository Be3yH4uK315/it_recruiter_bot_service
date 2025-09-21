import re
from typing import Optional, Dict, List
from datetime import date, datetime
from urllib.parse import urlparse
import phonenumbers
from pydantic import BaseModel, Field, validator

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PRESENT_ALIASES = {"сейчас", "н.в.", "present", "текущее", "настоящее", "настоящее время"}

class Experience(BaseModel):
    company: str = Field(min_length=2, max_length=100)
    position: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: Optional[date]
    responsibilities: Optional[str] = Field(max_length=1000)

    @validator('end_date')
    def end_after_start(cls, v, values):
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError("Дата окончания не может быть раньше даты начала.")
        if v and v > date.today():
            raise ValueError("Дата окончания не может быть в будущем.")
        return v

class Skill(BaseModel):
    skill: str = Field(min_length=2, max_length=50)
    kind: str = Field()
    level: int = Field(ge=1, le=5)

class Project(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    description: Optional[str] = Field(max_length=500)
    links: Optional[Dict[str, str]] = None

def parse_experience(text: str) -> Experience:
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    data = {}
    for line in lines:
        if ':' in line:
            key, val = line.split(':', 1)
            data[key.strip().lower()] = val.strip()
    if not all(k in data for k in ['company', 'position', 'start_date']):
        raise ValueError("Обязательные поля: company, position, start_date.")
    
    start_date = validate_date(data['start_date'])
    end_date = validate_date(data.get('end_date'))
    data['start_date'] = start_date
    data['end_date'] = end_date
    return Experience(**data)

def validate_date(date_str: str) -> Optional[date]:
    s = date_str.strip().lower()
    if s in PRESENT_ALIASES:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD или 'сейчас'.")

def parse_contacts(text: str) -> Dict[str, str]:
    if not text:
        return {}
    pairs = text.split(',')
    result = {}
    for pair in pairs:
        if ':' not in pair:
            raise ValueError("Формат: key:value, key2:value2.")
        key, value = pair.split(':', 1)
        key = key.strip().lower()
        val = value.strip()
        if key == 'email' and not EMAIL_RE.match(val):
            raise ValueError("Неверный email.")
        if key == 'phone' and not validate_phone(val):
            pass
        result[key] = val
    return result

def validate_phone(phone: str) -> bool:
    phone = phone.strip()
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.is_possible_number(parsed)
    except Exception:
        return False

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except ValueError:
        return False