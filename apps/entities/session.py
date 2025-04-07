"""Session相关数据结构"""

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    """
    Session

    collection: session
    """

    id: str = Field(alias="_id")
    ip: str
    user_sub: str | None = None
    nonce: str | None = None
    expired_at: datetime
