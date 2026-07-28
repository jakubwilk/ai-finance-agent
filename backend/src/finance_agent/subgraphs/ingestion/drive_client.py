"""Thin, testable wrapper around the Google Drive API v3 client.

Per docs/02-spec-google-drive-ingestion.md: OAuth with a personal Google
account, credentials built directly from GOOGLE_OAUTH_CLIENT_ID/_SECRET/
_REFRESH_TOKEN (obtained once, out-of-band, by the user) — no interactive
consent flow in code. Read-only scope only, since this client never writes
to Drive.

GoogleDriveClient takes an already-built googleapiclient service resource
rather than constructing one internally, so tests can inject a fake service
without mocking googleapiclient.discovery.build.
"""

import io
from dataclasses import dataclass
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from finance_agent.config import Settings

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


@dataclass
class DriveFile:
    id: str
    name: str
    modified_time: datetime


def build_credentials(settings: Settings) -> Credentials:
    missing = [
        var_name
        for var_name, value in (
            ("GOOGLE_OAUTH_CLIENT_ID", settings.google_oauth_client_id),
            ("GOOGLE_OAUTH_CLIENT_SECRET", settings.google_oauth_client_secret),
            ("GOOGLE_OAUTH_REFRESH_TOKEN", settings.google_oauth_refresh_token),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Missing Google OAuth credentials: {', '.join(missing)}. "
            "Set them in backend/.env — see docs/02-spec-google-drive-ingestion.md."
        )

    return Credentials(
        token=None,
        refresh_token=settings.google_oauth_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=[DRIVE_READONLY_SCOPE],
    )


class GoogleDriveClient:
    def __init__(self, service) -> None:
        self._service = service

    def list_new_files(
        self, folder_id: str, modified_after: datetime | None = None
    ) -> list[DriveFile]:
        query = (
            f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
        )
        if modified_after is not None:
            query += f" and modifiedTime > '{modified_after.isoformat()}'"

        files: list[DriveFile] = []
        page_token = None
        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, modifiedTime)",
                    pageToken=page_token,
                )
                .execute()
            )
            files.extend(
                DriveFile(
                    id=item["id"],
                    name=item["name"],
                    modified_time=datetime.fromisoformat(item["modifiedTime"]),
                )
                for item in response.get("files", [])
            )
            page_token = response.get("nextPageToken")
            if page_token is None:
                break

        return files

    def download_file(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()


def build_drive_client(settings: Settings) -> GoogleDriveClient:
    credentials = build_credentials(settings)
    service = build("drive", "v3", credentials=credentials)
    return GoogleDriveClient(service)
