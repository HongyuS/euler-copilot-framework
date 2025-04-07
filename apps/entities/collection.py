"""
MongoDB中的数据结构

Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from apps.constants import NEW_CHAT


class Blacklist(BaseModel):
    """
    黑名单

    Collection: blacklist
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    question: str
    answer: str
    is_audited: bool = False
    reason_type: list[str] = []
    reason: str | None = None
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class UserDomainData(BaseModel):
    """用户领域数据"""

    name: str
    count: int


class AppUsageData(BaseModel):
    """User表子项：应用使用情况数据"""

    count: int = 0
    last_used: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))


class User(BaseModel):
    """
    用户信息

    Collection: user
    外键：user - conversation
    """

    id: str = Field(alias="_id")
    last_login: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
    is_active: bool = False
    is_whitelisted: bool = False
    credit: int = 100
    api_key: str | None = None
    kb_id: str | None = None
    conversations: list[str] = []
    domains: list[UserDomainData] = []
    app_usage: dict[str, AppUsageData] = {}
    fav_apps: list[str] = []
    fav_services: list[str] = []


class Conversation(BaseModel):
    """
    对话信息

    Collection: conversation
    外键：conversation - task, document, record_group
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    title: str = NEW_CHAT
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
    app_id: str | None = Field(default="")
    tasks: list[str] = []
    unused_docs: list[str] = []
    record_groups: list[str] = []
    debug : bool = Field(default=False)


class Document(BaseModel):
    """
    文件信息

    Collection: document
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str
    name: str
    type: str
    size: float
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
    conversation_id: str


class Audit(BaseModel):
    """
    审计日志

    Collection: audit
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    user_sub: str | None = None
    http_method: str
    created_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
    module: str
    client_ip: str | None = None
    message: str


class Domain(BaseModel):
    """
    领域信息

    Collection: domain
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")
    name: str
    definition: str
    updated_at: float = Field(default_factory=lambda: round(datetime.now(tz=UTC).timestamp(), 3))
