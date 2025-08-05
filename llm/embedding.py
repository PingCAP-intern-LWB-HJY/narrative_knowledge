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
    Generate simulated embedding vectors based on text features, similar texts will have similar vectors.
    """
    # Clean text
    text = text.lower().strip()
    
    # Based on text length, character distribution and other features
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    vector = []
    for i in range(dimension):
        # Use text hash and position to generate deterministic values
        seed_val = int(text_hash[i % len(text_hash)], 16) + i
        val = math.sin(seed_val) * math.cos(len(text) + i)
        vector.append(val)
    
    # Normalize
    norm = sum(x**2 for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    
    return vector