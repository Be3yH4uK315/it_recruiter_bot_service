from uuid import UUID
import httpx
from app.core.config import (
    CANDIDATE_SERVICE_URL,
    EMPLOYER_SERVICE_URL,
    SEARCH_SERVICE_URL,
    FILE_SERVICE_URL,
)
from typing import List, Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- КЛИЕНТ ДЛЯ CANDIDATE SERVICE ---
class CandidateAPIClient:
    def __init__(self):
        self.base_url = f"{CANDIDATE_SERVICE_URL}/candidates"

    async def create_candidate(
        self, telegram_id: int, telegram_name: str
    ) -> dict | None:
        payload = {
            "telegram_id": telegram_id,
            "display_name": "FCs",
            "headline_role": "New Candidate",
            "experience_years": 0,
            "contacts": {"telegram": f"@{telegram_name}"},
            "skills": [],
        }

        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.post(f"{self.base_url}/", json=payload)

                if response.status_code == 409:
                    logger.info(
                        f"Candidate with telegram_id {telegram_id} already exists."
                    )
                    return None

                response.raise_for_status()

                logger.info(
                    f"Successfully created candidate with telegram_id {telegram_id}"
                )
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
                )
                return None
            except httpx.RequestError as e:
                logger.error(f"An error occurred while requesting {e.request.url!r}.")
                return None

    async def get_candidate_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/by-telegram/{telegram_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"CandidateAPI: Profile for telegram_id {telegram_id} not found.")
                    return None
                logger.error(f"CandidateAPI: HTTP error getting candidate by tg_id: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"CandidateAPI: Request error getting candidate by tg_id: {e}")
                return None

    async def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.get(f"{self.base_url}/{candidate_id}")
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"CandidateAPI: HTTP error getting candidate {candidate_id}: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"CandidateAPI: Request error getting candidate: {e}")
                return None

    async def update_candidate_profile(
        self, telegram_id: int, profile_data: dict
    ) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}"

        payload = profile_data.copy()

        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.patch(url, json=payload)
                response.raise_for_status()
                logger.info(
                    f"Successfully updated profile for telegram_id {telegram_id}"
                )
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on profile update: {e.response.status_code} - {e.response.text}"
                )
                return False
            except httpx.RequestError as e:
                logger.error(f"Request error on profile update for {e.request.url!r}.")
                return False

    async def replace_resume(self, telegram_id: int, file_id: UUID) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        payload = {"file_id": str(file_id)}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.put(url, json=payload)
                response.raise_for_status()
                return True
            except (httpx.RequestError, httpx.HTTPStatusError):
                return False

    async def replace_avatar(self, telegram_id: int, file_id: UUID) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        payload = {"file_id": str(file_id)}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.put(url, json=payload)
                response.raise_for_status()
                logger.info(f"Successfully replaced avatar for telegram_id {telegram_id}")
                return True
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"CandidateAPI: Error replacing avatar: {e}")
                return False

    async def delete_avatar(self, telegram_id: int) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/avatar"
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.delete(url)
                response.raise_for_status()
                logger.info(f"Deleted avatar for telegram_id {telegram_id}")
                return True
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"Error deleting avatar: {e}")
                return False

    async def delete_resume(self, telegram_id: int) -> bool:
        url = f"{self.base_url}/by-telegram/{telegram_id}/resume"
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.delete(url)
                response.raise_for_status()
                logger.info(f"Deleted resume for telegram_id {telegram_id}")
                return True
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"Error deleting resume: {e}")
                return False

# --- EMPLOYER ---
class EmployerAPIClient:
    def __init__(self):
        self.base_url = f"{EMPLOYER_SERVICE_URL}/employers"

    async def get_or_create_employer(self, telegram_id: int, username: str) -> Optional[Dict[str, Any]]:
        payload = {"telegram_id": telegram_id, "contacts": {"telegram": f"@{username}"}}
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"EmployerAPI: HTTP error on get_or_create: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"EmployerAPI: Request error on get_or_create: {e}")
                return None

    async def create_search_session(self, employer_id: str, filters: dict) -> Optional[Dict[str, Any]]:
        payload = {"title": f"Search for {filters.get('role', 'candidate')}", "filters": filters}
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.post(f"{self.base_url}/{employer_id}/searches", json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"EmployerAPI: HTTP error creating search session: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"EmployerAPI: Request error creating search session: {e}")
                return None

    async def save_decision(self, session_id: str, candidate_id: str, decision: str) -> bool:
        url = f"{self.base_url}/searches/{session_id}/decisions"
        payload = {"candidate_id": candidate_id, "decision": decision}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info(f"Decision '{decision}' for candidate {candidate_id} in session {session_id} saved.")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"EmployerAPI: HTTP error saving decision: {e.response.status_code}")
                return False
            except httpx.RequestError as e:
                logger.error(f"EmployerAPI: Request error saving decision: {e}")
                return False

    async def request_contacts(self, employer_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/{employer_id}/contact-requests"
        payload = {"candidate_id": candidate_id}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"EmployerAPI: HTTP error requesting contacts: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"EmployerAPI: Request error requesting contacts: {e}")
                return None

# --- SEARCH ---
class SearchAPIClient:
    def __init__(self):
        self.base_url = f"{SEARCH_SERVICE_URL}/search"

    async def search_candidates(self, filters: dict) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=filters)
                response.raise_for_status()
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"SearchAPI: Error during search: {e}")
                return None

# --- FILE ---
class FileAPIClient:
    def __init__(self):
        self.base_url = f"{FILE_SERVICE_URL}/files"

    async def upload_file(self, filename: str, file_data: bytes, content_type: str, owner_id: int, file_type: str) -> Optional[Dict[str, Any]]:
        data = {"owner_telegram_id": owner_id, "file_type": file_type}
        files = {'file': (filename, file_data, content_type)}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.post(f"{self.base_url}/upload", data=data, files=files)
                response.raise_for_status()
                return response.json()
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.error(f"FileAPI: Error uploading file: {e}")
                return None

    async def get_download_url_by_file_id(self, file_id: UUID) -> Optional[str]:
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.get(f"{self.base_url}/{file_id}/download-url")
                response.raise_for_status()
                return response.json().get("download_url")
            except (httpx.RequestError, httpx.HTTPStatusError):
                logger.error(f"FileAPI: Error getting download URL for file_id {file_id}")
                return None

    async def delete_file(self, file_id: UUID, owner_telegram_id: int) -> bool:
        params = {"owner_telegram_id": owner_telegram_id}
        async with httpx.AsyncClient(http2=False, trust_env=False, timeout=10.0) as client:
            try:
                response = await client.delete(f"{self.base_url}/{file_id}", params=params)
                response.raise_for_status()
                logger.info(f"FileAPI: Successfully deleted file {file_id}")
                return True
            except (httpx.RequestError, httpx.HTTPStatusError):
                logger.error(f"FileAPI: Error deleting file {file_id}")
                return False

# --- API ---
candidate_api_client = CandidateAPIClient()
employer_api_client = EmployerAPIClient()
search_api_client = SearchAPIClient()
file_api_client = FileAPIClient()