"""
Notion connector implementation.
"""

import logging
from datetime import datetime
from typing import Optional

import httpx

from api.connectors.base import Note, NoteCreate, NotesConnector

logger = logging.getLogger(__name__)


class NotionConnector(NotesConnector):
    """
    Notion API connector for creating notes and managing databases.
    """

    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, credentials: dict):
        """
        Initialize with Notion OAuth tokens.

        Args:
            credentials: Dict with access_token, workspace info, etc.
        """
        super().__init__(credentials)
        self.access_token = credentials.get("access_token")
        self.workspace_id = credentials.get("workspace_id")
        self.workspace_name = credentials.get("workspace_name")

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make authenticated request to Notion API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Notion-Version": self.NOTION_VERSION,
        }

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.BASE_URL}{endpoint}",
                headers=headers,
                **kwargs,
            )

            if response.status_code == 401:
                raise NotionAuthError("Access token invalid or expired")

            response.raise_for_status()
            return response.json() if response.content else {}

    async def test_connection(self) -> bool:
        """Test if the connection is working."""
        try:
            await self._request("GET", "/users/me")
            return True
        except Exception as e:
            logger.error(f"Notion connection test failed: {e}")
            return False

    async def refresh_token(self) -> dict:
        """
        Refresh OAuth tokens.

        Note: Notion tokens don't expire but can be revoked.
        This method re-validates the token.
        """
        try:
            await self.test_connection()
            return self.credentials
        except NotionAuthError:
            raise TokenRefreshError("Notion token is invalid or revoked")

    async def list_databases(self) -> list[dict]:
        """List available databases shared with the integration."""
        data = await self._request(
            "POST",
            "/search",
            json={
                "filter": {"value": "database", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            },
        )

        databases = []
        for item in data.get("results", []):
            title = ""
            if item.get("title"):
                title = "".join(
                    t.get("plain_text", "") for t in item["title"]
                )

            databases.append({
                "id": item["id"],
                "name": title or "Untitled",
                "url": item.get("url"),
                "created_time": item.get("created_time"),
            })

        return databases

    async def create_note(
        self, note: NoteCreate, database_id: Optional[str] = None
    ) -> Note:
        """
        Create a new note (page) in Notion.

        If database_id is provided, creates in that database.
        Otherwise creates a standalone page.
        """
        if database_id:
            return await self._create_database_page(note, database_id)
        else:
            return await self._create_page(note)

    async def _create_page(self, note: NoteCreate) -> Note:
        """Create a standalone page in the workspace."""
        body = {
            "parent": {"type": "workspace", "workspace": True},
            "properties": {
                "title": {
                    "title": [{"type": "text", "text": {"content": note.title}}]
                }
            },
            "children": self._text_to_blocks(note.content),
        }

        data = await self._request("POST", "/pages", json=body)

        return Note(
            id=data["id"],
            title=note.title,
            content=note.content,
            url=data.get("url"),
            created_at=datetime.fromisoformat(
                data["created_time"].replace("Z", "+00:00")
            ),
        )

    async def _create_database_page(self, note: NoteCreate, database_id: str) -> Note:
        """Create a page in a database."""
        body = {
            "parent": {"type": "database_id", "database_id": database_id},
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": note.title}}]
                }
            },
            "children": self._text_to_blocks(note.content),
        }

        data = await self._request("POST", "/pages", json=body)

        return Note(
            id=data["id"],
            title=note.title,
            content=note.content,
            url=data.get("url"),
            created_at=datetime.fromisoformat(
                data["created_time"].replace("Z", "+00:00")
            ),
        )

    def _text_to_blocks(self, content: str) -> list[dict]:
        """Convert plain text content to Notion blocks."""
        blocks = []
        paragraphs = content.split("\n\n")

        for paragraph in paragraphs:
            if not paragraph.strip():
                continue

            # Check for bullet points
            if paragraph.strip().startswith("- ") or paragraph.strip().startswith("* "):
                items = paragraph.strip().split("\n")
                for item in items:
                    text = item.lstrip("- *").strip()
                    if text:
                        blocks.append({
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": [{"type": "text", "text": {"content": text}}]
                            },
                        })
            # Check for numbered lists
            elif paragraph.strip()[0].isdigit() and ". " in paragraph[:5]:
                items = paragraph.strip().split("\n")
                for item in items:
                    # Remove number prefix
                    parts = item.split(". ", 1)
                    text = parts[1] if len(parts) > 1 else item
                    if text.strip():
                        blocks.append({
                            "object": "block",
                            "type": "numbered_list_item",
                            "numbered_list_item": {
                                "rich_text": [{"type": "text", "text": {"content": text.strip()}}]
                            },
                        })
            # Check for headings
            elif paragraph.startswith("# "):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {
                        "rich_text": [{"type": "text", "text": {"content": paragraph[2:]}}]
                    },
                })
            elif paragraph.startswith("## "):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": paragraph[3:]}}]
                    },
                })
            elif paragraph.startswith("### "):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": paragraph[4:]}}]
                    },
                })
            else:
                # Regular paragraph
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                    },
                })

        return blocks

    async def search_pages(self, query: str) -> list[dict]:
        """Search for pages in the workspace."""
        data = await self._request(
            "POST",
            "/search",
            json={
                "query": query,
                "filter": {"value": "page", "property": "object"},
                "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            },
        )

        pages = []
        for item in data.get("results", []):
            title = ""
            title_prop = item.get("properties", {}).get("title", {})
            if title_prop.get("title"):
                title = "".join(t.get("plain_text", "") for t in title_prop["title"])

            pages.append({
                "id": item["id"],
                "title": title or "Untitled",
                "url": item.get("url"),
            })

        return pages


class NotionAuthError(Exception):
    """Raised when Notion authentication fails."""

    pass


class TokenRefreshError(Exception):
    """Raised when token refresh fails."""

    pass
