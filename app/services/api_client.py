import httpx
from app.core.config import (
    CANDIDATE_SERVICE_URL,
    EMPLOYER_SERVICE_URL,
    SEARCH_SERVICE_URL,
)
from typing import List, Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CandidateAPIClient:
    def __init__(self):
        self.base_url = f"{CANDIDATE_SERVICE_URL}/candidates/"

    async def create_candidate(
        self, telegram_id: int, display_name: str
    ) -> dict | None:
        payload = {
            "telegram_id": telegram_id,
            "display_name": display_name,
            "headline_role": "New Candidate",
            "experience_years": 0,
            "contacts": {"telegram": f"@{display_name}"},
            "skills": [],
        }

        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.post(self.base_url, json=payload)

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

    async def get_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.get(f"{self.base_url}{candidate_id}")
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
        url = f"{self.base_url}by-telegram/{telegram_id}"

        raw_skills = profile_data.get("skills", [])
        formatted_skills = [{"skill": s, "kind": "hard"} for s in raw_skills]

        payload = {
            "headline_role": profile_data.get("headline_role"),
            "experience_years": profile_data.get("experience_years"),
            "skills": formatted_skills,
        }

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

class EmployerAPIClient:
    def __init__(self):
        self.base_url = f"{EMPLOYER_SERVICE_URL}/employers/"

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
                response = await client.post(f"{self.base_url}{employer_id}/searches", json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"EmployerAPI: HTTP error creating search session: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"EmployerAPI: Request error creating search session: {e}")
                return None


class SearchAPIClient:
    def __init__(self):
        self.base_url = f"{SEARCH_SERVICE_URL}/search/"

    async def search_candidates(self, filters: dict) -> Optional[List[Dict[str, Any]]]:
        async with httpx.AsyncClient(
            http2=False, trust_env=False, timeout=10.0
        ) as client:
            try:
                response = await client.post(self.base_url, json=filters)
                response.raise_for_status()
                return response.json().get("results", [])
            except httpx.HTTPStatusError as e:
                logger.error(f"SearchAPI: HTTP error during search: {e.response.status_code}")
                return None
            except httpx.RequestError as e:
                logger.error(f"SearchAPI: Request error during search: {e}")
                return None

candidate_api_client = CandidateAPIClient()
employer_api_client = EmployerAPIClient()
search_api_client = SearchAPIClient()
