"""
Pydantic request/response models for the Router API.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User email address")
    message: str = Field(..., description="User text for this turn")
    session_id: Optional[str] = Field(None, description="Omit to auto-generate")
    predefined_intent: Optional[str] = Field(
        None, description="Fast-path intent; skip LLM if truthy"
    )


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    user_info: Optional[Dict[str, Any]] = None
    backend_data: Optional[Any] = None
