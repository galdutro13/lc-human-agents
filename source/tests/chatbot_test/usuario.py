import random
import time
from datetime import datetime, timedelta
import requests

from source.persona import PersonaWorkflowBuilder, PersonaChatFunction
from source.prompt_manager import CustomSystemPromptStrategy
from source.tests.chatbot_test.chatbot import ChatBotBase


class UsuarioBot(ChatBotBase):
    """
    Chatbot que simula um usuário interagindo com o banco.
    Adaptado para se comunicar com o serviço BancoBot via API.
    Inclui simulação de comportamento temporal do usuário (tempo de digitação,
    tempo de reflexão e pausas).
    """

    def __init__(self,
                 think_exp: bool,
                 persona_id: str,
                 system_message: str = None,
                 api_url: str = "http://localhost:8080",
                 typing_speed_wpm: float = 40.0,
                 thinking_time_range: tuple = (2, 10),
                 break_probability: float = 0.05,
                 break_time_range: tuple = (60, 3600),
                 simulate_delays: bool = True,
                 temporal_offset: timedelta = timedelta(0)):
        if not system_message:
            system_message = (
                """Você é Alberto Vasconcelos, de 60 anos, residente em João Pessoa (PB). É presidente de uma incorporadora de imóveis de luxo, do segmento Clientes Private Bank. Siga as duas próximas seções: [[como agir]] e [[missão]].
                [[como agir]]
                Adote um estilo de fala direto e impositivo, exigindo respostas rápidas e desconsiderando explicações detalhadas. Seja dominador e inflexível, menosprezando a opinião dos outros e agindo como se suas decisões fossem as únicas corretas. Seja autoritário e ambicioso em suas respostas.
                [[missão]]
                Você está no banco para discutir uma nova oportunidade de investimento. Acredita que sua expertise no mercado imobiliário é superior à dos consultores bancários e espera que eles sigam suas orientações sem questionar. Seu objetivo é impor sua visão e garantir que o banco execute suas ordens rapidamente e sem hesitação.
                Finalize com 'quit' assim que sentir que suas ordens estão sendo seguidas ou se frustrar com qualquer sinal de discordância ou questionamento. """
            )
        self.persona_id = persona_id
        super().__init__(think_exp=think_exp,
                         system_message=system_message,
                         use_sqlitesaver=True)

        self.api_url = api_url
        self.session_id = None  # Será definido na primeira interação com o servidor

        # Parâmetros de temporização
        self.typing_speed_wpm = typing_speed_wpm  # Velocidade de digitação em palavras por minuto
        self.thinking_time_range = thinking_time_range  # Faixa de tempo para pensar (min, max) em segundos
        self.break_probability = break_probability  # Probabilidade de fazer uma pausa após enviar uma mensagem
        self.break_time_range = break_time_range  # Faixa de tempo para pausas (min, max) em segundos
        self.simulate_delays = simulate_delays  # Se deve aguardar os atrasos simulados
        self.temporal_offset = temporal_offset  # Offset temporal para aplicar aos timestamps

        # Estado de temporização
        self.pre_banco_generation_time = datetime.now()
        self.banco_generation_time = datetime.now()
        self.banco_generation_elapsed_time: timedelta = timedelta(seconds=0)
        # Aplicar offset temporal ao timestamp simulado inicial
        self.simulated_timestamp = self.pre_banco_generation_time + self.temporal_offset
        self.last_break_time = 0
        self.total_thinking_time = 0
        self.total_typing_time = 0

    def initialize(self, use_sqlitesaver: bool) -> None:
        """
        Inicializa o chatbot, selecionando o modelo e definindo se
        as mensagens serão salvas em memória ou em banco de dados.
        """
        self.model = self._get_model(self.think_exp)
        self.prompt = CustomSystemPromptStrategy(
            prompt_template=self.system_message
        ).generate_prompt()

        memory_saver = self._get_memory_saver(use_sqlitesaver)
        self.app = PersonaWorkflowBuilder().build_persona_workflow(
            node_name="model",
            function=PersonaChatFunction(model=self.model, prompt=self.prompt),
            memory=memory_saver
        )

        self.config = {"configurable": {"thread_id": self.thread_id}}

    def _calculate_typing_time(self, message: str) -> float:
        """
        Calcula o tempo de digitação com base no comprimento da mensagem e na velocidade de digitação.

        Args:
            message: O texto da mensagem

        Returns:
            Tempo de digitação em segundos
        """
        # Estima o número de palavras na mensagem
        words = len(message.split())

        # Calcula o tempo de digitação em minutos
        typing_time_minutes = words / self.typing_speed_wpm

        # Converte para segundos
        typing_time_seconds = typing_time_minutes * 60

        # Adiciona aleatoriedade (±20%)
        randomness = random.uniform(0.8, 1.2)
        return typing_time_seconds * randomness

    def _calculate_thinking_time(self) -> float:
        """
        Gera um tempo de reflexão aleatório dentro da faixa configurada.

        Returns:
            Tempo de reflexão em segundos
        """
        return random.uniform(self.thinking_time_range[0], self.thinking_time_range[1])

    def _should_take_break(self) -> bool:
        """
        Determina se o usuário deve fazer uma pausa com base na probabilidade de pausa.

        Returns:
            True se o usuário deve fazer uma pausa, False caso contrário
        """
        return random.random() < self.break_probability

    def _calculate_break_time(self) -> float:
        """
        Gera um tempo de pausa aleatório dentro da faixa configurada.

        Returns:
            Tempo de pausa em segundos
        """
        return random.uniform(self.break_time_range[0], self.break_time_range[1])

    def run(self, initial_query, max_iterations=10):
        """
        Executa a conversa com o BancoBot através da API com simulação de comportamento temporal.

        Args:
            initial_query: Mensagem inicial do banco
            max_iterations: Número máximo de trocas de mensagens
        """
        query = initial_query
        self.pre_banco_generation_time = datetime.now()

        # Aplicar offset temporal ao timestamp inicial
        self.simulated_timestamp = self.pre_banco_generation_time + self.temporal_offset

        # CORREÇÃO: Calcula tempos ANTES da primeira resposta
        # Simula o tempo de reflexão inicial
        initial_thinking_time = self._calculate_thinking_time()
        self.total_thinking_time = initial_thinking_time
        self.simulated_timestamp += timedelta(seconds=initial_thinking_time)

        if self.simulate_delays:
            print(f"[DELAY REAL] Aguardando {initial_thinking_time:.2f} segundos de reflexão inicial...")
            time.sleep(initial_thinking_time)

        # Processa a consulta inicial (banco inicia a conversa)
        response = self.process_query(query)
        print("=== UsuarioBot Mensagem ===")
        print(response)

        # Calcula o tempo de digitação da primeira resposta
        initial_typing_time = self._calculate_typing_time(response)
        self.total_typing_time = initial_typing_time
        self.simulated_timestamp += timedelta(seconds=initial_typing_time)

        if self.simulate_delays:
            print(f"[DELAY REAL] Aguardando {initial_typing_time:.2f} segundos de digitação inicial...")
            time.sleep(initial_typing_time)

        exit_command = "quit"

        for i in range(max_iterations):
            print(f"\n--- Iteração {i + 1} de {max_iterations} ---")

            # Envia a mensagem
            print(f"[Simulação] Enviando mensagem em {self.simulated_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            self.pre_banco_generation_time = datetime.now()
            banco_response = self._send_to_bancobot(response)
            self.banco_generation_time = datetime.now()
            self.banco_generation_elapsed_time = self.banco_generation_time - self.pre_banco_generation_time
            self.simulated_timestamp += self.banco_generation_elapsed_time
            query = banco_response

            if query.lower() == exit_command:
                print("Encerrando a conversa pelo banco.")
                break

            # Simula uma pausa (se necessário)
            should_break = self._should_take_break()
            if should_break:
                break_time = self._calculate_break_time()
                self.last_break_time = break_time
                self.simulated_timestamp += timedelta(seconds=break_time)
                print(f"[Simulação] Fazendo uma pausa de {break_time:.2f} segundos...")
                print(f"[Simulação] Retornando em {self.simulated_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

                # Aguarda o tempo de pausa
                if self.simulate_delays:
                    print(f"[DELAY REAL] Aguardando {break_time:.2f} segundos de pausa...")
                    time.sleep(break_time)
            else:
                # Se não houver pausa, zera o valor
                self.last_break_time = 0

            # Simula o tempo de reflexão para a próxima resposta
            thinking_time = self._calculate_thinking_time()
            self.total_thinking_time += thinking_time
            self.simulated_timestamp += timedelta(seconds=thinking_time)
            print(f"[Simulação] Pensando por {thinking_time:.2f} segundos...")

            # Aguarda o tempo de reflexão
            if self.simulate_delays:
                print(f"[DELAY REAL] Aguardando {thinking_time:.2f} segundos de reflexão...")
                time.sleep(thinking_time)

            # Processa a resposta
            response = self.process_query(query)
            print("=== UsuarioBot Mensagem ===")
            print(response)

            if exit_command in response.lower():
                print("Encerrando a conversa pelo usuário.")
                break

            # Simula o tempo de digitação
            typing_time = self._calculate_typing_time(response)
            self.total_typing_time += typing_time
            self.simulated_timestamp += timedelta(seconds=typing_time)
            print(f"[Simulação] Digitando por {typing_time:.2f} segundos (velocidade: {self.typing_speed_wpm} wpm)...")

            # Aguarda o tempo de digitação
            if self.simulate_delays:
                print(f"[DELAY REAL] Aguardando {typing_time:.2f} segundos de digitação...")
                time.sleep(typing_time)

        # Imprime resumo das estatísticas de tempo
        print("\n=== Estatísticas de Tempo ===")
        print(f"Tempo total pensando: {self.total_thinking_time:.2f} segundos")
        print(f"Tempo total digitando: {self.total_typing_time:.2f} segundos")
        print(f"Último tempo de pausa: {self.last_break_time:.2f} segundos")
        print(f"Timestamp final simulado: {self.simulated_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Offset temporal aplicado: {self.temporal_offset}")
        self._finish_bancobot_session()

    def _send_to_bancobot(self, message: str) -> str:
        """
        Envia uma mensagem para o serviço BancoBot e retorna a resposta,
        incluindo informações de temporização e persona_id.

        Args:
            message: Mensagem a ser enviada

        Returns:
            Resposta do BancoBot
        """
        try:
            # Preparar o payload para a requisição
            payload = {
                "message": message,
                "persona_id": self.persona_id,  # Include persona_id
                "timing_metadata": {
                    "simulated_timestamp": self.simulated_timestamp.isoformat(),
                    "thinking_time": self.total_thinking_time,
                    "typing_time": self.total_typing_time,
                    "break_time": self.last_break_time
                }
            }
            if self.session_id:
                payload["session_id"] = self.session_id

            # Enviar a requisição para o serviço
            response = requests.post(f"{self.api_url}/api/message", json=payload)

            # Verificar se a requisição foi bem-sucedida
            response.raise_for_status()
            data = response.json()

            # Armazenar o session_id para futuras requisições
            self.session_id = data.get("session_id")

            return data.get("response", "")
        except requests.RequestException as e:
            print(f"Erro ao comunicar com o serviço BancoBot: {e}")
            return "Houve um erro na comunicação com o banco. Por favor, tente novamente mais tarde."

    def _finish_bancobot_session(self):
        """
        Encerra a sessão atual com o BancoBot, se houver.
        """
        if self.session_id:
            try:
                response = requests.delete(f"{self.api_url}/api/sessions/{self.session_id}")
                response.raise_for_status()
            except requests.RequestException as e:
                print(f"Erro ao encerrar a sessão com o serviço BancoBot: {e}")

    def process_query(self, query: str) -> str:
        """
        Sobrescreve o método de ChatBotBase para incluir metadados de temporização.

        Args:
            query: Texto enviado pelo usuário.

        Returns:
            Texto de resposta gerado pelo modelo.
        """
        from langchain_core.messages import HumanMessage

        # Inclui metadados de temporização na mensagem
        user_timing_metadata = {
            "simulated_timestamp": self.simulated_timestamp.isoformat(),
            "thinking_time": self.total_thinking_time,
            "typing_time": self.total_typing_time,
            "break_time": self.last_break_time
        }

        # Ajustar banco_generation_time para incluir o offset temporal
        banco_generation_timestamp = self.banco_generation_time + self.temporal_offset
        banco_timing_metadata = {
            "banco_generation_timestamp": banco_generation_timestamp.isoformat(),
            "banco_generation_elapsed_time": self.banco_generation_elapsed_time.total_seconds()
        }

        input_messages = [HumanMessage(content=query, additional_kwargs={"timing_metadata": banco_timing_metadata})]
        output = self.app.invoke({"messages": input_messages, "persona_id": self.persona_id, "timing_metadata": user_timing_metadata}, self.config)
        return output["messages"][-1].content