from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, Request, Response, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.rate_limit import client_ip, rate_limiter
from app.repositories.documents import DocumentRepository
from app.schemas.document import (
    DocumentRead,
    DocumentStatusResponse,
    DocumentUploadResponse,
    IngestionJobRead,
)
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    user: CurrentUser,
    session: SessionDep,
    request: Request,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form(max_length=255)] = None,
) -> DocumentUploadResponse:
    await rate_limiter.check(
        action="upload",
        identities=[client_ip(request), str(user.id)],
        limit=settings.upload_rate_limit_per_hour,
        window_seconds=3600,
    )
    return await document_service.upload_document(session, user.id, file, name)


@router.get("/", response_model=list[DocumentRead])
async def list_documents(
    user: CurrentUser,
    session: SessionDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[DocumentRead]:
    documents = await DocumentRepository(session).list_owned(user.id, offset, limit)
    return [DocumentRead.model_validate(document) for document in documents]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: UUID, user: CurrentUser, session: SessionDep) -> DocumentRead:
    document = await document_service.owned_document(session, document_id, user.id)
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID, user: CurrentUser, session: SessionDep
) -> DocumentStatusResponse:
    return await document_service.document_status(session, document_id, user.id)


@router.post("/{document_id}/reprocess", response_model=IngestionJobRead)
async def reprocess_document(
    document_id: UUID, user: CurrentUser, session: SessionDep
) -> IngestionJobRead:
    job = await document_service.reprocess(session, document_id, user.id)
    return IngestionJobRead.model_validate(job)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, user: CurrentUser, session: SessionDep) -> Response:
    await document_service.delete_document(session, document_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
