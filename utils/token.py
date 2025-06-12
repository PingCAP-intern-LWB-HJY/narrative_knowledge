import tiktoken
from typing import List


def calculate_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Count the number of tokens in a text string.

    :param text: The text to count tokens for
    :param model: The model name to use for token counting (default: gpt-4o)
    :return: Number of tokens
    """
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


def encode_text(text: str, model: str = "gpt-4o") -> List[int]:
    """
    Encode a text string into a token string.

    :param text: The text to encode
    :param model: The model name to use for encoding (default: gpt-4o)
    :return: Token string
    """
    encoding = tiktoken.encoding_for_model(model)
    return encoding.encode(text)


def decode_tokens(tokens: List[int], model: str = "gpt-4o") -> str:
    """
    Decode a token list into a text string.

    :param tokens: The token list to decode
    :param model: The model name to use for decoding (default: gpt-4o)
    :return: Text string
    """
    encoding = tiktoken.encoding_for_model(model)
    return encoding.decode(tokens)
