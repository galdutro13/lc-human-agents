from functools import lru_cache
from typing import Any

from langchain_openai import ChatOpenAI

from source.chat_graph.models import ModelName


@lru_cache(maxsize=4)
def get_openai_llm(model_name: ModelName) -> ChatOpenAI:
    """
    Loads an OpenAI language model.
    :param model_name: Enum with the name of the model to load.
    :return: A ChatOpenAI object configured with the chosen model.
    :raises ValueError: If the model cannot be loaded.
    """
    openai_model: str = model_name.value
    try:
        model = ChatOpenAI(model=openai_model)
        return model
    except Exception as e:
        raise ValueError(f"Error loading the model {model_name}: {e}")
