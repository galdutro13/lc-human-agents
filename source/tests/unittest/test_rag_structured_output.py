import unittest

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

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
from source.rag.functions.grader import GraderFunction
from source.rag.functions.router import RouterFunction


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


class StructuredOutputModelStub:
    def __init__(self, responses: list[dict[str, str]]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def with_structured_output(self, schema, **kwargs):
        self.calls.append({"schema": schema, "kwargs": kwargs})

        def produce_result(_input):
            response = self._responses.pop(0)
            return schema(**response)

        return RunnableLambda(produce_result)


class TestRouterStructuredOutput(unittest.TestCase):
    def test_router_uses_function_calling_and_preserves_state_contract(self):
        model = StructuredOutputModelStub([{"datasource": "contas"}])
        router = RouterFunction(
            config=build_test_config(),
            datasource_names=["contas"],
            model=model,
        )

        result = router({"question": "Qual o saldo da conta?"})

        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0]["kwargs"].get("method"), "function_calling")
        self.assertEqual(result["datasource"], "contas")
        self.assertEqual(len(result["messages"]), 1)
        self.assertIsInstance(result["messages"][0], HumanMessage)
        self.assertEqual(result["messages"][0].content, "Qual o saldo da conta?")


class TestGraderStructuredOutput(unittest.TestCase):
    def test_grader_uses_function_calling_and_filters_relevant_documents(self):
        model = StructuredOutputModelStub(
            [{"binary_score": "yes"}, {"binary_score": "no"}, {"binary_score": "yes"}]
        )
        grader = GraderFunction(config=build_test_config(), model=model)
        context = [
            "Saldo atual da conta corrente.",
            "Oferta de cartao de credito.",
            "Movimentacoes dos ultimos tres dias.",
        ]

        result = grader(
            {
                "question": "Preciso do saldo e das movimentacoes recentes.",
                "context": context,
            }
        )

        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0]["kwargs"].get("method"), "function_calling")
        self.assertTrue(result["documents_relevant"])
        self.assertEqual(
            result["relevant_context"],
            [
                "Saldo atual da conta corrente.",
                "Movimentacoes dos ultimos tres dias.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
