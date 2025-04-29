"""Embedding模型"""

import httpx

from apps.common.config import Config


class Embedding:
    """Embedding模型"""

    # TODO: 应当自动检测向量维度
    @classmethod
    async def _get_embedding_dimension(cls) -> int:
        """获取Embedding的维度"""
        embedding = await cls.get_embedding(["测试文本"])
        return len(embedding[0])


    @classmethod
    async def _get_openai_embedding(cls, text: list[str]) -> list[list[float]]:
        """访问OpenAI兼容的Embedding API，获得向量化数据"""
        api = Config().get_config().embedding.endpoint + "/embeddings"
        data = {
            "input": text,
            "model": Config().get_config().embedding.model,
            "encoding_format": "float",
        }

        headers = {
            "Content-Type": "application/json",
        }
        if Config().get_config().embedding.api_key:
            headers["Authorization"] = f"Bearer {Config().get_config().embedding.api_key}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                api,
                json=data,
                headers=headers,
                timeout=60.0,
            )
            json = response.json()
            return [item["embedding"] for item in json["data"]]

    @classmethod
    async def _get_tei_embedding(cls, text: list[str]) -> list[list[float]]:
        """访问TEI兼容的Embedding API，获得向量化数据"""
        api = Config().get_config().embedding.endpoint + "/embed"
        headers = {
            "Content-Type": "application/json",
        }
        if Config().get_config().embedding.api_key:
            headers["Authorization"] = f"Bearer {Config().get_config().embedding.api_key}"

        async with httpx.AsyncClient() as client:
            result = []
            for single_text in text:
                data = {
                    "inputs": single_text,
                    "normalize": True,
                }
                response = await client.post(
                    api, json=data, headers=headers, timeout=60.0,
                )
                json = response.json()
                result.append(json[0])

            return result

    @classmethod
    async def get_embedding(cls, text: list[str]) -> list[list[float]]:
        """
        访问OpenAI兼容的Embedding API，获得向量化数据

        :param text: 待向量化文本（多条文本组成List）
        :return: 文本对应的向量（顺序与text一致，也为List）
        """
        if Config().get_config().embedding.type == "openai":
            return await cls._get_openai_embedding(text)
        if Config().get_config().embedding.type == "mindie":
            return await cls._get_tei_embedding(text)

        err = f"不支持的Embedding API类型: {Config().get_config().embedding.type}"
        raise ValueError(err)
