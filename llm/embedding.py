import openai
import json
import os

from setting.base import EMBEDDING_MODEL, EMBEDDING_BASE_URL, EMBEDDING_MODEL_API_KEY

import hashlib
import math
from typing import List

def get_text_embedding(text: str):
    embedding_model = openai.OpenAI(
        base_url=EMBEDDING_BASE_URL,
        api_key=EMBEDDING_MODEL_API_KEY,
    )
    text = text.replace("\n", " ")
    return (
        embedding_model.embeddings.create(input=[text], model=EMBEDDING_MODEL).data[0].embedding
    )


def get_entity_description_embedding(name: str, description: str):
    combined_text = f"{name}: {description}"
    return get_text_embedding(combined_text)


def get_entity_metadata_embedding(metadata: dict):
    combined_text = json.dumps(metadata)
    return get_text_embedding(combined_text)

def text_based_mock_embedding(text: str, dimension: int = 4096) -> List[float]:
    """
    基于文本特征生成模拟嵌入向量，相似文本会有相似向量。
    """
    # 清理文本
    text = text.lower().strip()
    
    # 基于文本长度、字符分布等特征
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    vector = []
    for i in range(dimension):
        # 使用文本hash和位置生成确定性的值
        seed_val = int(text_hash[i % len(text_hash)], 16) + i
        val = math.sin(seed_val) * math.cos(len(text) + i)
        vector.append(val)
    
    # 归一化
    norm = sum(x**2 for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    
    return vector