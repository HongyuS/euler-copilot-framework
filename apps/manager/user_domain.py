# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""用户画像管理"""

import logging

from apps.entities.collection import UserDomainData
from apps.models.mongo import MongoDB

logger = logging.getLogger(__name__)


class UserDomainManager:
    """用户画像管理"""

    @staticmethod
    async def get_user_domain_by_user_sub_and_topk(user_sub: str, topk: int) -> list[str]:
        """根据用户ID，查询用户最常涉及的n个领域"""
        mongo = MongoDB()
        user_collection = mongo.get_collection("user")
        try:
            domains = await user_collection.aggregate(
                [
                    {"$project": {"_id": 1, "domains": 1}},
                    {"$match": {"_id": user_sub}},
                    {"$unwind": "$domains"},
                    {"$sort": {"domain_count": -1}},
                    {"$limit": topk},
                ],
            )

            return [UserDomainData.model_validate(domain).name async for domain in domains]
        except Exception:
            logger.exception("[UserDomainManager] 查询用户最常涉及的%d个领域失败", topk)
        return []

    @staticmethod
    async def update_user_domain_by_user_sub_and_domain_name(user_sub: str, domain_name: str) -> bool:
        """增加特定用户特定领域的频次"""
        mongo = MongoDB()
        domain_collection = mongo.get_collection("domain")
        user_collection = mongo.get_collection("user")
        try:
            # 检查领域是否存在
            domain = await domain_collection.find_one({"_id": domain_name})
            if not domain:
                # 领域不存在，则创建领域
                await domain_collection.insert_one({"_id": domain_name, "domain_description": ""})
            await user_collection.update_one(
                {"_id": user_sub, "domains.name": domain_name}, {"$inc": {"domains.$.count": 1}},
            )
        except Exception:
            logger.exception("[UserDomainManager] 更新用户领域失败")
            return False
        else:
            return True
