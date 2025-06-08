# source/persona/persona_function.py
from typing import Any, Dict
from langchain_core.messages import AIMessage
from source.chat_graph.chat_function import ChatFunction
from source.persona.persona_state import PersonaState


class PersonaChatFunction(ChatFunction):
    """
    Persona implementation of a ChatFunction using a prompt and a model.
    Corretamente preserva metadata no additional_kwargs.
    """

    def __init__(self, prompt: Any, model: Any):
        self._prompt = prompt
        self._model = model

    def __call__(self, state: PersonaState) -> Dict[str, Any]:
        """
        Processa o estado e garante que metadata seja preservada no AIMessage.

        Args:
            state: Estado da persona com mensagens e metadata

        Returns:
            Dict com lista de mensagens (formato esperado pelo LangGraph)
        """
        # PASSO 1: Coleta toda metadata ANTES de invocar o modelo
        metadata_to_preserve = {}

        # Extrai timing_metadata se existir
        if isinstance(state, dict):
            if 'timing_metadata' in state:
                metadata_to_preserve['timing_metadata'] = state['timing_metadata']
            if 'persona_id' in state:
                metadata_to_preserve['persona_id'] = state['persona_id']
        else:
            if hasattr(state, 'timing_metadata') and state.timing_metadata:
                metadata_to_preserve['timing_metadata'] = state.timing_metadata
            # Extrai persona_id se existir
            if hasattr(state, 'persona_id') and state.persona_id:
                metadata_to_preserve['persona_id'] = state.persona_id

        # PASSO 2: Converte estado para dicionário para o LangChain
        # O LangChain espera um dicionário, não um objeto
        if isinstance(state, dict):
            state_dict = state
        else:
            # Converte objeto para dicionário
            state_dict = {}
            # Adiciona todos os atributos relevantes
            for attr in dir(state):
                if not attr.startswith('_'):
                    value = getattr(state, attr, None)
                    if value is not None and not callable(value):
                        state_dict[attr] = value

        # PASSO 3: Invoca o modelo
        chain = self._prompt | self._model
        ai_response = chain.invoke(state_dict)

        # PASSO 3: Cria NOVA instância de AIMessage com metadata
        # (Não modifica a existente pois pode ser imutável no LangGraph)
        if isinstance(ai_response, AIMessage):
            # Preserva todos os campos originais e adiciona metadata
            enhanced_message = AIMessage(
                content=ai_response.content,
                # Combina additional_kwargs existentes com nossa metadata
                additional_kwargs={
                    **ai_response.additional_kwargs,
                    **metadata_to_preserve
                },
                # Preserva outros campos importantes
                response_metadata=getattr(ai_response, 'response_metadata', {}),
                tool_calls=getattr(ai_response, 'tool_calls', []),
                invalid_tool_calls=getattr(ai_response, 'invalid_tool_calls', []),
                usage_metadata=getattr(ai_response, 'usage_metadata', None),
                # Preserva o ID se existir
                id=getattr(ai_response, 'id', None)
            )
        else:
            # Fallback: cria AIMessage do zero se resposta não for AIMessage
            enhanced_message = AIMessage(
                content=str(ai_response),
                additional_kwargs=metadata_to_preserve
            )

        return {"messages": enhanced_message}

    @property
    def prompt(self) -> Any:
        return self._prompt

    @property
    def model(self) -> Any:
        return self._model


# CÓDIGO DE TESTE para verificar se funciona
if __name__ == "__main__":
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    from dotenv import load_dotenv
    load_dotenv()

    # Setup de teste
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Você é um assistente útil. Persona: {persona_id}"),
        ("human", "{input}")
    ])
    model = ChatOpenAI(model="gpt-3.5-turbo")

    # Cria a função
    chat_function = PersonaChatFunction(prompt, model)


    # Simula um estado com metadata - duas opções:

    # Opção 1: Usar um objeto (a função irá converter para dict)
    class TestState:
        def __init__(self):
            self.timing_metadata = {
                "simulated_timestamp": "2025-05-26T13:24:55.310343",
                "thinking_time": 32.749,
                "typing_time": 185.845,
                "break_time": 0
            }
            self.persona_id = "persona_pc1"
            self.input = "Olá, teste de metadata!"
            self.messages = [
                HumanMessage(content="Teste", additional_kwargs={"session_id": "abc123"})
            ]


    # Opção 2: Usar diretamente um dicionário (mais simples para teste)
    state_dict = {
        "timing_metadata": {
            "simulated_timestamp": "2025-05-26T13:24:55.310343",
            "thinking_time": 32.749,
            "typing_time": 185.845,
            "break_time": 0
        },
        "persona_id": "persona_pc1",
        "input": "Olá, teste de metadata!",
        "messages": [
            HumanMessage(content="Teste", additional_kwargs={"session_id": "abc123"})
        ]
    }

    # Testa com objeto (será convertido internamente)
    print("=== TESTE COM OBJETO ===")
    state_obj = TestState()
    result1 = chat_function(state_obj)

    # Testa com dicionário
    print("\n=== TESTE COM DICIONÁRIO ===")
    result2 = chat_function(state_dict)

    # Verifica resultados
    for i, result in enumerate([result1, result2], 1):
        print(f"\n=== VERIFICAÇÃO RESULTADO {i} ===")
        ai_msg = result["messages"]
        print(f"Tipo: {type(ai_msg)}")
        print(f"Content: {ai_msg.content[:50]}...")
        print(f"Additional kwargs: {ai_msg.additional_kwargs}")
        print(f"Tem timing_metadata? {'timing_metadata' in ai_msg.additional_kwargs}")
        print(f"Tem persona_id? {'persona_id' in ai_msg.additional_kwargs}")

        # Assertions
        # assert isinstance(result["messages"], list), "Deve retornar lista de mensagens"
        # assert len(result["messages"]) == 1, "Deve ter exatamente uma mensagem"
        assert isinstance(ai_msg, AIMessage), "Deve ser AIMessage"
        assert "timing_metadata" in ai_msg.additional_kwargs, "Deve ter timing_metadata"
        assert "persona_id" in ai_msg.additional_kwargs, "Deve ter persona_id"

    print("\n✅ TODOS OS TESTES PASSARAM!")