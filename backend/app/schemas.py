from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime
    document_count: int = 0


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    filename: str
    doc_type: str
    status: str
    progress: str
    error: str | None
    page_count: int | None
    vision_enrichment: bool
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_ids: list[str]
    updated_at: datetime


class SourceRef(BaseModel):
    document_id: str
    filename: str
    doc_type: str = ""
    page: int | None = None
    section: str = ""


class ToolCallOut(BaseModel):
    name: str
    args: dict


class MessageOut(BaseModel):
    role: str  # user | assistant
    content: str
    tool_calls: list[ToolCallOut] = []
    sources: list[SourceRef] = []


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    source_ids: list[str] = []
