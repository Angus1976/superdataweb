"""File storage service for uploaded files.

Stores files on local disk under /app/uploads (in container)
or ./uploads (local dev). Metadata is tracked in PostgreSQL.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads"))

# All supported upload file extensions grouped by category
FILE_CATEGORIES: dict[str, set[str]] = {
    "document": {"docx", "xlsx", "pdf", "pptx", "ppt", "csv", "txt", "md", "json", "xml", "html", "rtf"},
    "image": {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "tiff", "ico"},
    "video": {"mp4", "avi", "mov", "mkv", "wmv", "flv", "webm", "m4v", "mpeg", "mpg", "3gp"},
    "audio": {"mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "opus", "amr"},
    "archive": {"zip", "rar", "7z", "tar", "gz", "bz2"},
}

SUPPORTED_EXTENSIONS: set[str] = set()
for exts in FILE_CATEGORIES.values():
    SUPPORTED_EXTENSIONS |= exts


def get_category(ext: str) -> str:
    """Return the category for a file extension."""
    for cat, exts in FILE_CATEGORIES.items():
        if ext in exts:
            return cat
    return "other"


@dataclass
class StoredFile:
    """Metadata for a stored file."""
    id: str
    original_name: str
    stored_path: str
    size_bytes: int
    extension: str
    category: str
    content_type: str
    uploaded_by: str  # user email or tenant_id
    tenant_id: str
    created_at: datetime


class FileStorageService:
    """Handles saving and retrieving uploaded files."""

    def __init__(self) -> None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        content: bytes,
        original_name: str,
        ext: str,
        tenant_id: str,
        uploaded_by: str = "",
        content_type: str = "",
    ) -> StoredFile:
        """Save file to disk and return metadata."""
        file_id = uuid.uuid4().hex
        category = get_category(ext)

        # Organize by tenant/category
        rel_dir = Path(tenant_id) / category
        (UPLOAD_DIR / rel_dir).mkdir(parents=True, exist_ok=True)

        stored_name = f"{file_id}.{ext}"
        stored_path = str(rel_dir / stored_name)
        full_path = UPLOAD_DIR / stored_path

        full_path.write_bytes(content)

        return StoredFile(
            id=file_id,
            original_name=original_name,
            stored_path=stored_path,
            size_bytes=len(content),
            extension=ext,
            category=category,
            content_type=content_type or f"application/{ext}",
            uploaded_by=uploaded_by,
            tenant_id=tenant_id,
            created_at=datetime.now(timezone.utc),
        )

    def get_file_path(self, stored_path: str) -> Path | None:
        """Return the full path to a stored file, or None if not found."""
        full = UPLOAD_DIR / stored_path
        return full if full.exists() else None

    def delete_file(self, stored_path: str) -> bool:
        """Delete a stored file. Returns True if deleted."""
        full = UPLOAD_DIR / stored_path
        if full.exists():
            full.unlink()
            return True
        return False
