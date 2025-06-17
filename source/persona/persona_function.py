# source/persona/persona_function.py
import random
from typing import Any, Dict
from langchain_core.messages import AIMessage
from source.chat_graph.chat_function import ChatFunction
from source.persona.persona_state import PersonaState


class PersonaChatFunction(ChatFunction):
    """
    Persona implementation of a ChatFunction using a prompt and a model.
    Corretamente preserva metadata no additional_kwargs e calcula tempo de digitação.
    """

    def __init__(self, prompt: Any, model: Any):
        self._prompt = prompt
        self._model = model

    def _calculate_typing_time(self, message: str, typing_speed_wpm: float = 40.0) -> float:
        """
        Calcula o tempo de digitação com base no comprimento da mensagem e na velocidade de digitação.

        Args:
            message: O texto da mensagem
            typing_speed_wpm: Velocidade de digitação em palavras por minuto

        Returns:
            Tempo de digitação em segundos
        """
        # Estima o número de palavras na mensagem
        words = len(message.split())

        # Calcula o tempo de digitação em minutos
        typing_time_minutes = words / typing_speed_wpm

        # Converte para segundos
        typing_time_seconds = typing_time_minutes * 60

        # Adiciona aleatoriedade (±20%)
        randomness = random.uniform(0.8, 1.2)
        return typing_time_seconds * randomness

    def __call__(self, state: PersonaState) -> Dict[str, Any]:
        """
        Processa o estado e garante que metadata seja preservada no AIMessage.
        Calcula o tempo de digitação após gerar a mensagem.

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
                metadata_to_preserve['timing_metadata'] = state['timing_metadata'].copy()
            if 'persona_id' in state:
                metadata_to_preserve['persona_id'] = state['persona_id']
            # Extrai typing_speed_wpm se existir
            typing_speed_wpm = state.get('typing_speed_wpm', 40.0)
        else:
            if hasattr(state, 'timing_metadata') and state.timing_metadata:
                metadata_to_preserve['timing_metadata'] = state.timing_metadata.copy()
            # Extrai persona_id se existir
            if hasattr(state, 'persona_id') and state.persona_id:
                metadata_to_preserve['persona_id'] = state.persona_id
            # Extrai typing_speed_wpm se existir
            typing_speed_wpm = getattr(state, 'typing_speed_wpm', 40.0)

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

        # PASSO 4: Calcula o tempo de digitação baseado na resposta gerada
        response_content = ai_response.content if isinstance(ai_response, AIMessage) else str(ai_response)
        typing_time = self._calculate_typing_time(response_content, typing_speed_wpm)

        # Atualiza o timing_metadata com o tempo de digitação calculado
        if 'timing_metadata' not in metadata_to_preserve:
            metadata_to_preserve['timing_metadata'] = {}
        metadata_to_preserve['timing_metadata']['typing_time'] = typing_time
        # Somar o tempo de digitação ao simulated_timestamp se existir
        if 'simulated_timestamp' in metadata_to_preserve['timing_metadata']:
            simulated_timestamp = metadata_to_preserve['timing_metadata']['simulated_timestamp']
            # Converte para datetime se necessário (assumindo que é uma string ISO 8601)
            from datetime import datetime, timedelta
            timestamp_dt = datetime.fromisoformat(simulated_timestamp)
            # Adiciona o tempo de digitação
            updated_timestamp = timestamp_dt + timedelta(seconds=typing_time)
            metadata_to_preserve['timing_metadata']['simulated_timestamp'] = updated_timestamp.isoformat()

        # PASSO 5: Cria NOVA instância de AIMessage com metadata
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

    # Simula um estado com metadata e typing_speed_wpm
    state_dict = {
        "timing_metadata": {
            "simulated_timestamp": "2025-05-26T13:24:55.310343",
            "thinking_time": 32.749,
            "break_time": 0
        },
        "persona_id": "persona_pc1",
        "input": "Olá, teste de metadata!",
        "typing_speed_wpm": 50.0,  # Velocidade de digitação personalizada
        "messages": [
            HumanMessage(content="Teste", additional_kwargs={"session_id": "abc123"})
        ]
    }

    # Testa
    print("=== TESTE COM CÁLCULO DE TYPING TIME ===")
    result = chat_function(state_dict)

    # Verifica resultados
    ai_msg = result["messages"]
    print(f"Tipo: {type(ai_msg)}")
    print(f"Content: {ai_msg.content[:50]}...")
    print(f"Additional kwargs: {ai_msg.additional_kwargs}")
    print(f"Tem timing_metadata? {'timing_metadata' in ai_msg.additional_kwargs}")
    print(f"Tem typing_time? {'typing_time' in ai_msg.additional_kwargs.get('timing_metadata', {})}")

    if 'timing_metadata' in ai_msg.additional_kwargs:
        typing_time = ai_msg.additional_kwargs['timing_metadata'].get('typing_time', 'N/A')
        print(f"Typing time calculado: {typing_time:.2f} segundos")

    # Assertions
    assert isinstance(ai_msg, AIMessage), "Deve ser AIMessage"
    assert "timing_metadata" in ai_msg.additional_kwargs, "Deve ter timing_metadata"
    assert "typing_time" in ai_msg.additional_kwargs["timing_metadata"], "Deve ter typing_time calculado"

    print("\n✅ TODOS OS TESTES PASSARAM!")