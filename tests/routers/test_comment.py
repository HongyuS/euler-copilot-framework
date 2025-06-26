# Copyright (c) Huawei Technologies Co., Ltd. 2023-2025. All rights reserved.

import secrets
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.requests import HTTPConnection

from apps.db.mysql import User
from apps.dependency import get_current_user, verify_csrf_token
from apps.routers.comment import router


def mock_csrf_token(request: HTTPConnection):
    return


def mock_get_user(request: Request):
    return User(user_sub="1", organization="openEuler")


class TestCommentRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[verify_csrf_token] = mock_csrf_token
        app.dependency_overrides[get_current_user] = mock_get_user
        cls.client = TestClient(app)

    @patch('apps.routers.comment.QaManager.query_encrypted_qa_pair_by_qa_record_id')
    @patch('apps.routers.comment.UserQaRecordManager.get_user_qa_record_by_session_id')
    @patch('apps.routers.comment.CommentManager.add_comment')
    def test_add_comment_success(self, mock_add_comment, mock_get_user_qa_record_by_session_id,
                                 mock_query_encrypted_qa_pair_by_qa_record_id):
        mock_query_encrypted_qa_pair_by_qa_record_id.return_value = MagicMock()

        cur_user_qa_record = MagicMock()
        cur_user_qa_record.user_sub = "1"
        mock_get_user_qa_record_by_session_id.return_value = cur_user_qa_record
        response = self.client.post("/comment", json={"qa_record_id": secrets.token_hex(nbytes=16),
                                                      "is_like": 1, "dislike_reason": "reason",
                                                      "reason_link": "link", "reason_description": "description"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "code": 200,
            "message": "success",
            "result": {}
        })
        self.assertEqual(mock_add_comment.call_count, 1)

    @patch('apps.routers.comment.QaManager.query_encrypted_qa_pair_by_qa_record_id')
    def test_add_comment_qa_record_not_found(self, mock_query_encrypted_qa_pair_by_qa_record_id):
        mock_query_encrypted_qa_pair_by_qa_record_id.return_value = None

        response = self.client.post("/comment", json={"qa_record_id": secrets.token_hex(nbytes=16),
                                                      "is_like": 1, "dislike_reason": "reason",
                                                      "reason_link": "link", "reason_description": "description"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")

    @patch('apps.routers.comment.QaManager.query_encrypted_qa_pair_by_qa_record_id')
    @patch('apps.routers.comment.UserQaRecordManager.get_user_qa_record_by_session_id')
    def test_add_comment_session_id_not_found(self, mock_get_user_qa_record_by_session_id,
                                              mock_query_encrypted_qa_pair_by_qa_record_id):
        mock_query_encrypted_qa_pair_by_qa_record_id.return_value = MagicMock()
        mock_get_user_qa_record_by_session_id.return_value = None

        response = self.client.post("/comment", json={"qa_record_id": secrets.token_hex(nbytes=16),
                                                      "is_like": 1, "dislike_reason": "reason",
                                                      "reason_link": "link", "reason_description": "description"})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.text, "")


if __name__ == '__main__':
    unittest.main()
