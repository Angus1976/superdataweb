"""Unified FastAPI Router for the interview module.

Provides JWT authentication dependency injection, tenant access verification,
unified exception handlers, and ErrorResponse model for all interview APIs.
"""

from __future__ import annotations

import uuid
from typing import Any

import json

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from src.interview.models import IndustryTemplateRequest, ProjectCreateRequest
from src.interview.session_models import InterviewMessage
from src.interview.security import InterviewSecurity
from src.interview.system import InterviewSystem, SessionManager, _sessions, _messages, _projects
from src.interview.llm_client import LLMClient
from src.interview.llm_models import LLMNotConfiguredError, LLMServiceError
from src.interview.entity_extractor import InterviewEntityExtractor, SUPPORTED_FILE_TYPES
from src.interview.audio_transcriber import AudioTranscriber, SUPPORTED_AUDIO_FORMATS
from src.interview import templates as tmpl_store

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/interview", tags=["interview"])

# ---------------------------------------------------------------------------
# Shared instances
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
_security = InterviewSecurity()
_system = InterviewSystem()
_extractor = InterviewEntityExtractor()
_transcriber = AudioTranscriber(model_name="base")
_session_mgr = SessionManager(security=_security)


# ---------------------------------------------------------------------------
# Error response model
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standardised error payload returned by all interview endpoints."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error description")
    details: dict[str, Any] = Field(default_factory=dict, description="Extra details")
    request_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="Request trace ID",
    )


# ---------------------------------------------------------------------------
# Dependency injection – JWT authentication
# ---------------------------------------------------------------------------


async def get_current_tenant(token: str = Depends(oauth2_scheme)) -> str:
    """Extract tenant_id from JWT token.

    Raises HTTP 401 when the token is invalid or missing the tenant_id claim.
    """
    return _security.get_current_tenant(token)


# ---------------------------------------------------------------------------
# Dependency injection – tenant access verification
# ---------------------------------------------------------------------------


async def verify_project_access(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant),
) -> str:
    """Verify the current tenant has access to *project_id*.

    Returns the validated *tenant_id* on success.
    Raises HTTP 403 when the tenant does not own the project.
    """
    has_access = await _security.verify_tenant_access(tenant_id, project_id)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project",
        )
    return tenant_id


# ---------------------------------------------------------------------------
# Exception handlers (register on the FastAPI app via install_exception_handlers)
# ---------------------------------------------------------------------------


def _build_error_response(
    status_code: int,
    error: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=error,
        message=message,
        details=details or {},
        request_id=request_id or uuid.uuid4().hex,
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


# Mapping of HTTP status codes to error type identifiers
_STATUS_ERROR_MAP: dict[int, str] = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    400: "bad_request",
    409: "conflict",
    422: "validation_error",
    502: "bad_gateway",
    504: "gateway_timeout",
}


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException into a standardised ErrorResponse."""
    error_type = _STATUS_ERROR_MAP.get(exc.status_code, "error")
    return _build_error_response(
        status_code=exc.status_code,
        error=error_type,
        message=str(exc.detail),
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert Pydantic / FastAPI validation errors into HTTP 422 + ErrorResponse."""
    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="validation_error",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )


def install_exception_handlers(app: Any) -> None:
    """Register unified exception handlers on a FastAPI application instance."""
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------


@router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Industry template endpoints
# ---------------------------------------------------------------------------


@router.get("/templates")
async def list_templates(industry: str | None = None):
    """List industry templates, optionally filtered by industry."""
    return tmpl_store.list_templates(industry)


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(req: IndustryTemplateRequest):
    """Create a new industry template."""
    return tmpl_store.create_template(req)


@router.put("/templates/{template_id}")
async def update_template(template_id: str, req: IndustryTemplateRequest):
    """Update an existing industry template."""
    result = tmpl_store.update_template(template_id, req)
    if result is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


# ---------------------------------------------------------------------------
# Project management endpoints
# ---------------------------------------------------------------------------


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    tenant_id: str = Depends(get_current_tenant),
):
    """Create a new project for the current tenant."""
    return await _system.create_project(tenant_id, req)


@router.get("/projects")
async def list_projects(tenant_id: str = Depends(get_current_tenant)):
    """List all projects for the current tenant (tenant-isolated)."""
    return await _system.list_projects(tenant_id)



# ---------------------------------------------------------------------------
# Document upload endpoint
# ---------------------------------------------------------------------------


@router.post("/{project_id}/upload-document")
async def upload_document(
    project_id: str,
    file: UploadFile,
    tenant_id: str = Depends(get_current_tenant),
):
    """Upload a requirement document and extract entities."""
    # Determine file type from extension
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format: .{ext}. Supported: {', '.join(sorted(SUPPORTED_FILE_TYPES))}",
        )

    content = await file.read()
    try:
        result = await _extractor.extract_from_document(content, ext)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    return {
        "project_id": project_id,
        "file_name": filename,
        "extraction_result": result.model_dump(),
    }



# ---------------------------------------------------------------------------
# Audio upload & ASR transcription endpoints
# ---------------------------------------------------------------------------


@router.post("/temp-project/upload-audio")
async def upload_audio_temp(
    file: UploadFile,
    language: str | None = None,
):
    """Upload audio for transcription without a project (used on create page)."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频格式: .{ext}。支持格式: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}",
        )

    content = await file.read()
    try:
        result = await _transcriber.transcribe(content, ext, language=language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"音频转写失败: {str(exc)}",
        )

    return {
        "file_name": filename,
        "transcription": {
            "text": result.text,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "segments": result.segments,
        },
    }


@router.post("/{project_id}/upload-audio")
async def upload_audio(
    project_id: str,
    file: UploadFile,
    language: str | None = None,
    tenant_id: str = Depends(get_current_tenant),
):
    """Upload an audio file and transcribe it using Whisper ASR.

    Supports: mp3, wav, flac, ogg, m4a, aac, wma, opus, webm, amr, mp4, mpeg.
    Optional query param `language` for language hint (e.g. "zh", "en").
    """
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频格式: .{ext}。支持格式: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}",
        )

    content = await file.read()
    try:
        result = await _transcriber.transcribe(content, ext, language=language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"音频转写失败: {str(exc)}",
        )

    return {
        "project_id": project_id,
        "file_name": filename,
        "transcription": {
            "text": result.text,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "segments": result.segments,
        },
    }


# ---------------------------------------------------------------------------
# Session management endpoints (intelligent-interview)
# ---------------------------------------------------------------------------


@router.post("/{project_id}/sessions", status_code=status.HTTP_201_CREATED)
async def start_session(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Start a new interview session for a project."""
    return await _session_mgr.start_session(project_id, tenant_id)


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    msg: InterviewMessage,
    tenant_id: str = Depends(get_current_tenant),
):
    """Send a message in an interview session."""
    return await _session_mgr.send_message(session_id, tenant_id, msg.content)


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    msg: InterviewMessage,
    tenant_id: str = Depends(get_current_tenant),
):
    """SSE 流式端点：逐块返回 AI 响应。"""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "active":
        raise HTTPException(status_code=409, detail="Session already ended")

    llm_client = _session_mgr._llm_client

    # Build message list: system + history + current user
    project = _projects.get(session.get("project_id", ""))
    system_prompt = ""
    if project:
        tmpl = tmpl_store.get_template_by_industry(project.get("industry", ""))
        if tmpl:
            system_prompt = tmpl.system_prompt

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in _messages.get(session_id, [])
    ]
    messages = LLMClient.build_messages(system_prompt, history, msg.content)

    async def event_generator():
        full_response = ""
        try:
            if llm_client is None:
                raise LLMNotConfiguredError()

            async for chunk in llm_client.chat_completion_stream(
                session["tenant_id"], messages
            ):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            yield "data: [DONE]\n\n"

            # Store user message + complete AI response to history
            current_round = session["current_round"]
            session["current_round"] = current_round + 1

            sanitized = msg.content
            if _session_mgr._security:
                sanitized = _session_mgr._security.sanitize_content(msg.content)

            _messages.setdefault(session_id, []).append({
                "role": "user",
                "content": msg.content,
                "sanitized_content": sanitized,
                "round_number": current_round + 1,
            })
            _messages[session_id].append({
                "role": "assistant",
                "content": full_response,
                "sanitized_content": full_response,
                "round_number": current_round + 1,
            })

        except (LLMNotConfiguredError, LLMServiceError):
            yield f'data: {json.dumps({"error": "AI 响应中断，请重试"}, ensure_ascii=False)}\n\n'
        except Exception:
            yield f'data: {json.dumps({"error": "AI 响应中断，请重试"}, ensure_ascii=False)}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """End an interview session and generate summary."""
    return await _session_mgr.end_session(session_id, tenant_id)


@router.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get the current status of an interview session."""
    return await _session_mgr.get_session_status(session_id)


@router.post("/sessions/{session_id}/completions")
async def generate_completions(session_id: str):
    """Generate 5 completion suggestions for the session."""
    return {"suggestions": await _session_mgr.generate_completions(session_id)}



# ---------------------------------------------------------------------------
# Label construction endpoints
# ---------------------------------------------------------------------------

from src.interview.label_constructor import LabelConstructor
from src.interview.offline_importer import OfflineImporter, SUPPORTED_IMPORT_TYPES

_label_constructor = LabelConstructor()
_offline_importer = OfflineImporter()


@router.post("/{project_id}/generate-labels")
async def generate_labels(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Generate AI-friendly labels for a project (async task)."""
    import uuid as _uuid
    task_id = _uuid.uuid4().hex
    return {
        "task_id": task_id,
        "status": "processing",
        "message": "标签生成任务已提交",
    }


@router.post("/{project_id}/import-offline")
async def import_offline(
    project_id: str,
    file: UploadFile,
    tenant_id: str = Depends(get_current_tenant),
):
    """Import offline interview data (Excel/JSON)."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    validation = _offline_importer.validate_file(filename, ext)
    if not validation.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.errors[0],
        )

    content = await file.read()
    try:
        import_result = await _offline_importer.import_file(content, ext, filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    merged = await _offline_importer.merge_with_online(project_id, import_result)

    return {
        "file_name": filename,
        "parsed_entities": len(import_result.entities),
        "parsed_rules": len(import_result.rules),
        "parsed_relations": len(import_result.relations),
        "merged_data": {
            "total_entities": len(merged.entities),
            "total_rules": len(merged.rules),
            "total_relations": len(merged.relations),
        },
    }


@router.post("/{project_id}/sync-to-label-studio")
async def sync_to_label_studio(
    project_id: str,
    tenant_id: str = Depends(get_current_tenant),
):
    """Sync labels to Label Studio."""
    from src.interview.label_studio_connector import LabelStudioConnector

    connector = LabelStudioConnector()
    connected = await connector.check_connection()
    if not connected:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cannot connect to Label Studio",
        )

    # In production: load label from DB and sync
    return {"sync_result": {"task_ids": [], "success_count": 0, "error_count": 0, "has_predictions": False}}
