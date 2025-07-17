# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.
"""文件Manager"""

import base64
import logging
import uuid

import asyncer
from fastapi import UploadFile
from sqlalchemy import func, select

from apps.common.minio import MinioClient
from apps.common.postgres import postgres
from apps.models.conversation import Conversation, ConversationDocument
from apps.models.document import Document
from apps.models.record import Record, RecordDocument
from apps.schemas.record import RecordGroupDocument

from .knowledge_base import KnowledgeBaseService
from .session import SessionManager

logger = logging.getLogger(__name__)


class DocumentManager:
    """文件相关操作"""

    @staticmethod
    def _storage_single_doc_minio(file_id: uuid.UUID, document: UploadFile) -> str:
        """存储单个文件到MinIO"""
        MinioClient.check_bucket("document")
        file = document.file
        # 获取文件MIME
        import magic
        mime = magic.from_buffer(file.read(), mime=True)
        file.seek(0)

        # 上传到MinIO
        MinioClient.upload_file(
            bucket_name="document",
            object_name=str(file_id),
            data=file,
            content_type=mime,
            length=-1,
            part_size=10 * 1024 * 1024,
            metadata={
                "file_name": base64.b64encode(
                    document.filename.encode("utf-8")
                ).decode("ascii") if document.filename else "",
            },
        )
        return mime

    @staticmethod
    async def storage_docs(
        user_sub: str, conversation_id: uuid.UUID, documents: list[UploadFile],
    ) -> list[Document]:
        """存储多个文件"""
        uploaded_files = []

        for document in documents:
            if document.filename is None or document.size is None:
                logger.error("[DocumentManager] 文件名或大小为空: %s, %s", document.filename, document.size)
                continue

            file_id = uuid.uuid4()
            try:
                mime = await asyncer.asyncify(DocumentManager._storage_single_doc_minio)(file_id, document)
            except Exception:
                logger.exception("[DocumentManager] 上传文件失败")
                continue

            # 保存到数据库
            doc_info = Document(
                userSub=user_sub,
                name=document.filename,
                extension=mime,
                size=document.size / 1024.0,
                conversationId=conversation_id,
            )
            uploaded_files.append(doc_info)

        async with postgres.session() as session:
            session.add_all(uploaded_files)
            await session.commit()
        return uploaded_files


    @staticmethod
    async def get_unused_docs(conversation_id: uuid.UUID) -> list[Document]:
        """获取Conversation中未使用的文件"""
        async with postgres.session() as session:
            conv = (await session.scalars(
                select(ConversationDocument).where(
                    ConversationDocument.conversationId == conversation_id,
                    ConversationDocument.isUnused.is_(True),
                ),
            )).all()
            if not conv:
                logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
                return []

            docs_ids = [doc.documentId for doc in conv]
            docs = (await session.scalars(select(Document).where(Document.id.in_(docs_ids)))).all()
        return list(docs)


    @staticmethod
    async def get_used_docs_by_record(record_id: str, doc_type: str | None = None) -> list[Document]:
        """获取RecordGroup关联的文件"""
        if doc_type not in ["question", "answer", None]:
            logger.error("[DocumentManager] 参数错误: %s", doc_type)
            return []

        async with postgres.session() as session:
            record_docs = (await session.scalars(
                select(RecordDocument).where(RecordDocument.recordId == record_id),
            )).all()
            if not list(record_docs):
                logger.info("[DocumentManager] 记录组不存在: %s", record_id)
                return []

            doc_infos: list[Document] = []
            for doc in record_docs:
                doc_info = (await session.scalars(select(Document).where(Document.id == doc.documentId))).one_or_none()
                if doc_info:
                    doc_infos.append(doc_info)
        return doc_infos


    @staticmethod
    async def get_used_docs(
        conversation_id: uuid.UUID, record_num: int | None = 10, doc_type: str | None = None,
    ) -> list[Document]:
        """获取最后n次问答所用到的文件"""
        if doc_type not in ["question", "answer", None]:
            logger.error("[DocumentManager] 参数错误: %s", doc_type)
            return []

        async with postgres.session() as session:
            records = (await session.scalars(
                select(Record).where(
                    Record.conversationId == conversation_id,
                ).order_by(Record.createdAt.desc()).limit(record_num),
            )).all()

            docs = []
            for current_record in records:
                record_docs = (
                    await session.scalars(
                        select(RecordDocument).where(RecordDocument.recordId == current_record.id),
                    )
                ).all()
                if list(record_docs):
                    docs += [doc.documentId for doc in record_docs]

            # 去重
            docs = list(set(docs))
            result = []
            for doc_id in docs:
                doc = (await session.scalars(select(Document).where(Document.id == doc_id))).one_or_none()
                if doc:
                    result.append(doc)
        return result


    @staticmethod
    def _remove_doc_from_minio(doc_id: str) -> None:
        """从MinIO中删除文件"""
        MinioClient.delete_file("document", doc_id)


    @staticmethod
    async def delete_document(user_sub: str, document_list: list[str]) -> bool:
        """从未使用文件列表中删除一个文件"""
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        conv_collection = mongo.get_collection("conversation")
        try:
            async with mongo.get_session() as session, await session.start_transaction():
                for doc in document_list:
                    doc_info = await doc_collection.find_one_and_delete(
                        {"_id": doc, "user_sub": user_sub}, session=session,
                    )
                    # 删除Document表内文件
                    if not doc_info:
                        logger.error("[DocumentManager] 文件不存在: %s", doc)
                        continue

                    # 删除MinIO内文件
                    await asyncer.asyncify(cls._remove_doc_from_minio)(doc)

                    # 删除Conversation内文件
                    conv = await conv_collection.find_one({"_id": doc_info["conversation_id"]}, session=session)
                    if conv:
                        await conv_collection.update_one(
                            {"_id": conv["_id"]},
                            {
                                "$pull": {"unused_docs": doc},
                            },
                            session=session,
                        )
                await session.commit_transaction()
                return True
        except Exception:
            logger.exception("[DocumentManager] 删除文件失败")
            return False


    @staticmethod
    async def delete_document_by_conversation_id(conversation_id: uuid.UUID) -> list[str]:
        """通过ConversationID删除文件"""
        mongo = MongoDB()
        doc_collection = mongo.get_collection("document")
        doc_ids = []

        async with mongo.get_session() as session, await session.start_transaction():
            async for doc in doc_collection.find(
                {"user_sub": user_sub, "conversation_id": conversation_id}, session=session,
            ):
                doc_ids.append(doc["_id"])
                await asyncer.asyncify(cls._remove_doc_from_minio)(doc["_id"])
                await doc_collection.delete_one({"_id": doc["_id"]}, session=session)
            await session.commit_transaction()

        session_id = await SessionManager.get_session_by_user_sub(user_sub)
        if not session_id:
            logger.error("[DocumentManager] Session不存在: %s", user_sub)
            return []
        await KnowledgeBaseService.delete_doc_from_rag(session_id, doc_ids)
        return doc_ids


    @staticmethod
    async def get_doc_count(conversation_id: str) -> int:
        """获取对话文件数量"""
        async with postgres.session() as session:
            return (await session.scalars(
                select(func.count(ConversationDocument.id)).where(
                    ConversationDocument.conversationId == conversation_id,
                ),
            )).one()


    @staticmethod
    async def change_doc_status(user_sub: str, conversation_id: str, record_group_id: str) -> None:
        """文件状态由unused改为used"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")
        conversation_collection = mongo.get_collection("conversation")

        # 查找Conversation中的unused_docs
        conversation = await conversation_collection.find_one({"user_sub": user_sub, "_id": conversation_id})
        if not conversation:
            logger.error("[DocumentManager] 对话不存在: %s", conversation_id)
            return

        # 把unused_docs加入RecordGroup中，并与问题关联
        docs_id = Conversation.model_validate(conversation).unused_docs
        for doc in docs_id:
            doc_info = RecordGroupDocument(_id=doc, associated="question")
            await record_group_collection.update_one(
                {"_id": record_group_id, "user_sub": user_sub},
                {"$push": {"docs": doc_info.model_dump(by_alias=True)}},
            )

        # 把unused_docs从Conversation中删除
        await conversation_collection.update_one({"_id": conversation_id}, {"$set": {"unused_docs": []}})

    @staticmethod
    async def save_answer_doc(user_sub: str, record_group_id: str, doc_infos: list[RecordDocument]) -> None:
        """保存与答案关联的文件"""
        mongo = MongoDB()
        record_group_collection = mongo.get_collection("record_group")

        for doc_info in doc_infos:
            await record_group_collection.update_one(
                {"_id": record_group_id, "user_sub": user_sub},
                {"$push": {"docs": doc_info.model_dump(by_alias=True)}},
            )
