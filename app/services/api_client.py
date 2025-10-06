from datetime import date
from uuid import UUID
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import (
    CANDIDATE_SERVICE_URL,
    EMPLOYER_SERVICE_URL,
    SEARCH_SERVICE_URL,
    FILE_SERVICE_URL,
)
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class APIRequestError(Exception):
    """Базовый exception для API ошибок."""
    pass

class APIHTTPError(APIRequestError):
    """HTTP-ошибка от API."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)

class APINetworkError(APIRequestError):
    """Сетевая ошибка (timeout, connection)."""
    pass

def serialize_dates(obj: Any) -> Any:
    """Сериализация дат в ISO формат."""
    if isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_dates(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [serialize_dates(item) for item in obj]
    return obj

def retry_api_call():
    """Настройка retry для API-запросов."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True
    )

class CandidateAPIClient:
    """Клиент для работы с кандидатами."""
    def __init__(self):
        self.base_url = f"{CANDIDATE_SERVICE_URL}/candidates"
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.headers = {"Content-Type": "application/json"}

    @retry_api_call()
    async def create_candidate(
        self, telegram_id: int, telegram_name: str
    ) -> Optional[Dict[str, Any]]:
        """Создание кандидата."""
        payload = {
            "telegram_id": telegram_id,
            "display_name": "FCs",
            "headline_role": "New Candidate",
            "experience_years": 0,
            "contacts": {"telegram": f"@{telegram_name}"},
            "skills": [],
        }
        payload = serialize_dates(payload)

        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=self.timeout
        ) as client:
            try:
                response = await client.post(f"{self.base_url}/", json=payload, headers=self.headers)
                if response.status_code == 409:
                    logger.info(f"Candidate with telegram_id {telegram_id} already exists.")
                    return None
                response.raise_for_status()
                logger.info(f"Successfully created candidate with telegram_id {telegram_id}")
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def get_candidate_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение кандидата по telegram_id."""
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/by-telegram/{telegram_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"CandidateAPI: Profile for telegram_id {telegram_id} not found.")
                    return None
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Получение кандидата по candidate_id."""
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=self.timeout
        ) as client:
            try:
                response = await client.get(f"{self.base_url}/{candidate_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def update_candidate_profile(
        self, telegram_id: int, profile_data: dict
    ) -> bool:
        """Обновление кандидата."""
        url = f"{self.base_url}/by-telegram/{telegram_id}"

        payload = serialize_dates(profile_data.copy())

        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=self.timeout
        ) as client:
            try:
                response = await client.patch(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Successfully updated profile for telegram_id {telegram_id}")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def replace_resume(self, telegram_id: int, file_id: UUID) -> bool:
        """Добавление/замена резюме."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        payload = {"file_id": str(file_id)}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.put(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def replace_avatar(self, telegram_id: int, file_id: UUID) -> bool:
        """Добавление/замена аватара."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        payload = {"file_id": str(file_id)}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.put(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Successfully replaced avatar for telegram_id {telegram_id}")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def delete_avatar(self, telegram_id: int) -> bool:
        """Удаление аватара."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.delete(url)
                response.raise_for_status()
                logger.info(f"Deleted avatar for telegram_id {telegram_id}")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def delete_resume(self, telegram_id: int) -> bool:
        """Удаление резюме."""
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.delete(url)
                response.raise_for_status()
                logger.info(f"Deleted resume for telegram_id {telegram_id}")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

class EmployerAPIClient:
    """Клиент для работы с работодателями."""
    def __init__(self):
        self.base_url = f"{EMPLOYER_SERVICE_URL}/employers"
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.headers = {"Content-Type": "application/json"}

    @retry_api_call()
    async def get_or_create_employer(self, telegram_id: int, username: str) -> Optional[Dict[str, Any]]:
        """Создание работодателя"""
        payload = {"telegram_id": telegram_id, "contacts": {"telegram": f"@{username}"}}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=self.timeout
        ) as client:
            try:
                response = await client.post(f"{self.base_url}/", json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def create_search_session(self, employer_id: str, filters: dict) -> Optional[Dict[str, Any]]:
        """Создание сессии поиска."""
        payload = {"title": f"Search for {filters.get('role', 'candidate')}", "filters": filters}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=self.timeout
        ) as client:
            try:
                response = await client.post(f"{self.base_url}/{employer_id}/searches", json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def save_decision(self, session_id: str, candidate_id: str, decision: str) -> bool:
        """Сохранение выбора работодателя."""
        url = f"{self.base_url}/searches/{session_id}/decisions"
        payload = {"candidate_id": candidate_id, "decision": decision}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                logger.info(f"Decision '{decision}' for candidate {candidate_id} in session {session_id} saved.")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def request_contacts(self, employer_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        """Запрос контактов."""
        url = f"{self.base_url}/{employer_id}/contact-requests"
        payload = {"candidate_id": candidate_id}
        payload = serialize_dates(payload)
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

class SearchAPIClient:
    """Клиент для работы с поиском."""
    def __init__(self):
        self.base_url = f"{SEARCH_SERVICE_URL}/search"
        self.timeout = httpx.Timeout(10.0, connect=5.0)
        self.headers = {"Content-Type": "application/json"}

    @retry_api_call()
    async def search_candidates(self, filters: dict) -> Optional[Dict[str, Any]]:
        """Поиск кандидатов."""
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/", json=filters, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

class FileAPIClient:
    """Клиент для работы с файлами."""
    def __init__(self):
        self.base_url = f"{FILE_SERVICE_URL}/files"
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    @retry_api_call()
    async def upload_file(self, filename: str, file_data: bytes, content_type: str, owner_id: int, file_type: str) -> Optional[Dict[str, Any]]:
        """Обновление файлов."""
        data = {"owner_telegram_id": owner_id, "file_type": file_type}
        files = {'file': (filename, file_data, content_type)}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/upload", data=data, files=files)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def get_download_url_by_file_id(self, file_id: UUID) -> Optional[str]:
        """Получение ссылки на файл."""
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/{file_id}/download-url")
                response.raise_for_status()
                return response.json().get("download_url")
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

    @retry_api_call()
    async def delete_file(self, file_id: UUID, owner_telegram_id: int) -> bool:
        """Удаление файла."""
        params = {"owner_telegram_id": owner_telegram_id}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=self.timeout) as client:
            try:
                response = await client.delete(f"{self.base_url}/{file_id}", params=params)
                response.raise_for_status()
                logger.info(f"FileAPI: Successfully deleted file {file_id}")
                return True
            except httpx.HTTPStatusError as e:
                raise APIHTTPError(e.response.status_code, f"HTTP error: {e.response.text}")
            except httpx.RequestError as e:
                raise APINetworkError(f"Network error: {str(e)}")

candidate_api_client = CandidateAPIClient()
employer_api_client = EmployerAPIClient()
search_api_client = SearchAPIClient()
file_api_client = FileAPIClient()