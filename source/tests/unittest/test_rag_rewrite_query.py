import unittest
from types import SimpleNamespace

from source.rag.config.models import (
    Datasource,
    EmbeddingConfig,
    GlobalPrompts,
    LLMConfig,
    PromptTemplates,
    RAGConfig,
    RetrieverConfig,
    TextSplitterConfig,
    VectorstoreConfig,
)
from source.rag.functions.rewrite_query import RewriteQueryFunction


def build_test_config() -> RAGConfig:
    return RAGConfig(
        version="test",
        datasources=[
            Datasource(
                name="contas",
                display_name="Contas",
                description="Dados de contas correntes.",
                folders=[],
                prompt_templates=PromptTemplates(rag_prompt="Use o contexto para responder."),
                retriever_config=RetrieverConfig(),
            )
        ],
        global_prompts=GlobalPrompts(
            router_prompt="Escolha a melhor datasource.",
            grader_prompt="Responda yes ou no.",
            fallback_prompt="Fallback.",
            rewrite_query_prompt="Rewrite.",
        ),
        embedding_config=EmbeddingConfig(model="test-embedding"),
        vectorstore_config=VectorstoreConfig(provider="test", persist_directory="./tmp"),
        llm_config=LLMConfig(model="test-llm"),
        text_splitter=TextSplitterConfig(),
    )


class RewriteModelStub:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class FailingRewriteModelStub:
    def invoke(self, messages):
        raise RuntimeError("model unavailable")


class RewriteLoggerStub:
    def __init__(self):
        self.rewrites = []
        self.logs = []
        self.errors = []

    def log_query_rewrite(self, original_query, rewrites):
        self.rewrites.append((original_query, rewrites))

    def log_function_start(self, function_name, state):
        self.logs.append(("INFO", f"Starting {function_name}", state))

    def log(self, level, message, data=None):
        self.logs.append((level, message, data))

    def log_error(self, error_type, error_message, traceback=None):
        self.errors.append((error_type, error_message, traceback))


class TestRewriteQueryFunction(unittest.TestCase):
    def test_limits_numbered_rewrites_to_first_three(self):
        model = RewriteModelStub(
            "\n".join(
                [
                    "1. Primeira query",
                    "2. Segunda query",
                    "3. Terceira query",
                    "4. Quarta query",
                    "5. Quinta query",
                ]
            )
        )
        logger = RewriteLoggerStub()
        rewriter = RewriteQueryFunction(build_test_config(), model, logger=logger)

        result = rewriter({"question": "Pergunta original"})

        self.assertEqual(
            result["rewritten_queries"],
            ["Primeira query", "Segunda query", "Terceira query"],
        )
        self.assertTrue(result["has_more_queries"])
        self.assertEqual(result["current_query_index"], 0)
        self.assertEqual(logger.rewrites[0][1], result["rewritten_queries"])
        self.assertLessEqual(len(logger.rewrites[0][1]), 3)

    def test_limits_bullet_rewrites_to_first_three(self):
        model = RewriteModelStub(
            "\n".join(
                [
                    "- Primeira query",
                    "- Segunda query",
                    "- Terceira query",
                    "- Quarta query",
                ]
            )
        )
        rewriter = RewriteQueryFunction(build_test_config(), model)

        result = rewriter({"question": "Pergunta original"})

        self.assertEqual(
            result["rewritten_queries"],
            ["Primeira query", "Segunda query", "Terceira query"],
        )
        self.assertTrue(result["has_more_queries"])
        self.assertEqual(result["current_query_index"], 0)

    def test_no_question_preserves_empty_state_contract(self):
        rewriter = RewriteQueryFunction(build_test_config(), RewriteModelStub("unused"))

        result = rewriter({})

        self.assertEqual(result["original_question"], "")
        self.assertEqual(result["rewritten_queries"], [])
        self.assertEqual(result["current_query_index"], 0)
        self.assertFalse(result["has_more_queries"])

    def test_unstructured_response_falls_back_to_raw_text(self):
        rewriter = RewriteQueryFunction(
            build_test_config(),
            RewriteModelStub("Consulta reformulada sem lista numerada."),
        )

        result = rewriter({"question": "Pergunta original"})

        self.assertEqual(
            result["rewritten_queries"],
            ["Consulta reformulada sem lista numerada."],
        )
        self.assertTrue(result["has_more_queries"])
        self.assertEqual(result["current_query_index"], 0)

    def test_model_error_falls_back_to_original_question(self):
        rewriter = RewriteQueryFunction(build_test_config(), FailingRewriteModelStub())

        result = rewriter({"question": "Pergunta original"})

        self.assertEqual(result["rewritten_queries"], ["Pergunta original"])
        self.assertTrue(result["has_more_queries"])
        self.assertEqual(result["current_query_index"], 0)


if __name__ == "__main__":
    unittest.main()
