from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class FriendEntry(BaseModel):
    nick: str
    connected_at: Optional[datetime] = None
    public_key: Optional[str] = ""
    status_message: Optional[str] = ""


class PendingMessageEntry(BaseModel):
    message_id: int
    sender_nick: str
    group_id: Optional[int]
    payload: str
    metadata: Optional[Dict[str, str]]
    media_ids: List[str]
    created_at: datetime
