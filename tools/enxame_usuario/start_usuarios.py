import os
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests
import json
import random
from datetime import datetime, timedelta
from source.tests.chatbot_test.usuario import UsuarioBot

"""
Script para executar uma suíte de personas definidas em um arquivo JSON (``prompts-file``)
contra o BancoBot.

**Alterações relevantes desta versão**
1. **Parâmetro ``--window-size``** – define o grau máximo de paralelismo.
2. **Parâmetro ``--passes``** – repete a lista de personas quantas vezes for
   necessário para gerar alta carga de teste (``total_runs = len(prompts) * passes``).
3. **Paralelismo dinâmico** – utilização de ``ThreadPoolExecutor`` garante que,
   enquanto houver personas na fila, sempre permanecerão ``window-size``
   execuções ativas; assim que um ``UsuarioBot`` termina, o próximo é iniciado
   automaticamente.
4. **Identificadores de persona genéricos** – chaves no JSON podem ser strings
   arbitrárias.
5. **Sem ``--num-usuarios``** – número total de execuções derivado de ``passes``.
6. **Suporte a configurações de temporização via JSON** – cada persona pode ter
   configurações individuais de duração e offset temporal.

Exemplo de uso:
```
python run_prompts.py \
    --prompts-file ./prompts.json \
    --window-size 6 \
    --passes 10
```
"""


# ---------------------------- Funções utilitárias -----------------------------

def calculate_temporal_offset(offset_type: str, max_days: int = 30) -> timedelta:
    """
    Calcula um offset temporal aleatório baseado no tipo especificado,
    podendo ser de até 30 dias no futuro.

    Args:
        offset_type: Tipo de offset ("manhã", "tarde", "noite", "horario-comercial")
        max_days: Número máximo de dias para o offset (padrão: 30)

    Returns:
        timedelta representando o offset a ser aplicado
    """
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_second = now.second

    # Define os intervalos para cada período
    time_ranges = {
        "manhã": (7, 11),
        "tarde": (12, 17),
        "noite": (18, 6),  # Noite atravessa meia-noite
        "horario-comercial": (8, 17)
    }

    if offset_type not in time_ranges:
        return timedelta(0)  # Sem offset se tipo inválido

    start_hour, end_hour = time_ranges[offset_type]

    # Primeiro, sorteia quantos dias no futuro (0 a max_days)
    days_offset = random.randint(0, max_days)

    # Tratamento especial para "noite" que atravessa meia-noite
    if offset_type == "noite":
        # Para noite, precisamos considerar dois intervalos: 18-23:59 e 0-5:59
        if random.random() < 0.7:  # 70% de chance de ser no período noturno (18h-23:59)
            target_hour = random.randint(18, 23)
        else:  # 30% de chance de ser na madrugada (0h-5:59)
            target_hour = random.randint(0, 5)
    else:
        # Para outros períodos, escolher hora aleatória no intervalo
        target_hour = random.randint(start_hour, end_hour)

    # Adicionar minutos e segundos aleatórios para maior realismo
    target_minute = random.randint(0, 59)
    target_second = random.randint(0, 59)

    # Calcular o datetime alvo
    target_datetime = now.replace(
        hour=target_hour,
        minute=target_minute,
        second=target_second,
        microsecond=0
    ) + timedelta(days=days_offset)

    # Se o horário alvo for antes do horário atual (pode acontecer com days_offset=0),
    # adicionar um dia
    if days_offset == 0 and target_datetime <= now:
        target_datetime += timedelta(days=1)

    # Calcular o offset final
    offset = target_datetime - now

    # Log para debug (opcional)
    print(f"[Offset Temporal] Tipo: {offset_type}")
    print(f"  - Hora atual: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  - Alvo: {target_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  - Offset: {offset.days} dias, {offset.seconds // 3600} horas, {(offset.seconds % 3600) // 60} minutos")

    return offset


# Exemplo de uso estendido com controle de dias máximos
def calculate_temporal_offset_with_distribution(offset_type: str,
                                                distribution: str = "uniform",
                                                max_days: int = 30) -> timedelta:
    """
    Versão estendida que permite diferentes distribuições de probabilidade
    para o sorteio dos dias.

    Args:
        offset_type: Tipo de offset ("manhã", "tarde", "noite", "horario-comercial")
        distribution: Tipo de distribuição ("uniform", "exponential", "weighted")
        max_days: Número máximo de dias para o offset

    Returns:
        timedelta representando o offset a ser aplicado
    """
    now = datetime.now()

    # Define os intervalos para cada período
    time_ranges = {
        "manhã": (7, 11),
        "tarde": (12, 17),
        "noite": (18, 6),
        "horario-comercial": (8, 17)
    }

    if offset_type not in time_ranges:
        return timedelta(0)

    # Sortear dias com base na distribuição escolhida
    if distribution == "exponential":
        # Distribuição exponencial: mais provável escolher dias próximos
        # Lambda = 0.1 significa ~63% de chance nos primeiros 10 dias
        days_offset = min(int(random.expovariate(0.1)), max_days)
    elif distribution == "weighted":
        # Distribuição com pesos: primeiros dias mais prováveis
        weights = [1 / (i + 1) for i in range(max_days + 1)]
        days_offset = random.choices(range(max_days + 1), weights=weights)[0]
    else:  # uniform
        # Distribuição uniforme: todos os dias têm a mesma probabilidade
        days_offset = random.randint(0, max_days)

    start_hour, end_hour = time_ranges[offset_type]

    # Tratamento especial para "noite"
    if offset_type == "noite":
        if random.random() < 0.7:
            target_hour = random.randint(18, 23)
        else:
            target_hour = random.randint(0, 5)
    else:
        target_hour = random.randint(start_hour, end_hour)

    # Adicionar variação realista
    target_minute = random.randint(0, 59)
    target_second = random.randint(0, 59)

    # Criar datetime alvo
    target_datetime = now.replace(
        hour=target_hour,
        minute=target_minute,
        second=target_second,
        microsecond=0
    ) + timedelta(days=days_offset)

    # Garantir que é no futuro
    if days_offset == 0 and target_datetime <= now:
        target_datetime += timedelta(days=1)

    return target_datetime - now


# Função auxiliar para validar e limitar o offset
def calculate_temporal_offset_safe(offset_type: str,
                                   max_days: int = 30,
                                   min_hours: int = 1) -> timedelta:
    """
    Versão segura que garante um offset mínimo e máximo.

    Args:
        offset_type: Tipo de offset
        max_days: Número máximo de dias
        min_hours: Número mínimo de horas no futuro

    Returns:
        timedelta com validações aplicadas
    """
    offset = calculate_temporal_offset(offset_type, max_days)

    # Garantir offset mínimo
    if offset < timedelta(hours=min_hours):
        offset = timedelta(hours=min_hours)

    # Garantir offset máximo
    if offset > timedelta(days=max_days):
        offset = timedelta(days=max_days)

    return offset


def get_duration_parameters(duration_type: str) -> dict:
    """
    Retorna os parâmetros de temporização baseados no tipo de duração.

    Args:
        duration_type: Tipo de duração ("lenta", "media", "rapida")

    Returns:
        Dicionário com typing_speed, thinking_min e thinking_max
    """
    duration_configs = {
        "lenta": {
            "typing_speed": random.uniform(10, 24),
            "thinking_min": 8.0,
            "thinking_max": 35.0
        },
        "media": {
            "typing_speed": random.uniform(25, 54),
            "thinking_min": 2.0,
            "thinking_max": 12.0
        },
        "rapida": {
            "typing_speed": random.uniform(55, 90),
            "thinking_min": 2.0,
            "thinking_max": 7.0
        }
    }

    # Se tipo inválido, retorna configuração média como padrão
    return duration_configs.get(duration_type, duration_configs["media"])


def parse_persona_config(persona_data, default_args):
    """
    Analisa a configuração da persona, suportando tanto formato antigo (string)
    quanto novo formato (objeto com persona, duração e offset).

    Args:
        persona_data: String ou dicionário com dados da persona
        default_args: Argumentos padrão da CLI

    Returns:
        Tupla (prompt, typing_speed, thinking_range, temporal_offset)
    """
    # Formato antigo: string direta
    if isinstance(persona_data, str):
        return (
            persona_data,
            default_args.typing_speed,
            (default_args.thinking_min, default_args.thinking_max),
            timedelta(0)  # Sem offset temporal
        )

    # Formato novo: objeto com campos
    if isinstance(persona_data, dict):
        prompt = persona_data.get("persona", "")

        # Obter parâmetros de duração
        duration_type = persona_data.get("duração", None)
        if duration_type:
            duration_params = get_duration_parameters(duration_type)
            typing_speed = duration_params["typing_speed"]
            thinking_range = (duration_params["thinking_min"], duration_params["thinking_max"])
        else:
            # Usar valores padrão da CLI
            typing_speed = default_args.typing_speed
            thinking_range = (default_args.thinking_min, default_args.thinking_max)

        # Calcular offset temporal
        offset_type = persona_data.get("offset", None)
        temporal_offset = calculate_temporal_offset(offset_type) if offset_type else timedelta(0)

        return prompt, typing_speed, thinking_range, temporal_offset

    # Formato desconhecido, retornar valores padrão
    return "", default_args.typing_speed, (default_args.thinking_min, default_args.thinking_max), timedelta(0)


def iniciar_usuario(persona_id: str,
                    think_exp: bool,
                    prompt_personalizado: str | None = None,
                    *,
                    api_url: str,
                    typing_speed_wpm: float,
                    thinking_time_range: tuple[float, float],
                    break_probability: float,
                    break_time_range: tuple[float, float],
                    simulate_delays: bool,
                    temporal_offset: timedelta = timedelta(0)) -> None:
    """Instancia e executa um :class:`UsuarioBot` para a persona fornecida."""
    print(f"[INFO] Iniciando persona '{persona_id}'…")

    if temporal_offset != timedelta(0):
        print(f"[INFO] Persona '{persona_id}' aplicando offset temporal de {temporal_offset}")

    usuario_bot = UsuarioBot(
        think_exp=think_exp,
        persona_id=f"persona_{persona_id}",
        system_message=prompt_personalizado,
        api_url=api_url,
        typing_speed_wpm=typing_speed_wpm,
        thinking_time_range=thinking_time_range,
        break_probability=break_probability,
        break_time_range=break_time_range,
        simulate_delays=simulate_delays,
        temporal_offset=temporal_offset,  # Novo parâmetro
    )

    try:
        usuario_bot.run(
            initial_query="Olá cliente, como posso lhe ajudar?",
            max_iterations=15,
        )
        print(f"[INFO] Persona '{persona_id}' concluiu a conversa.")
    except Exception as exc:
        print(f"[ERRO] Falha na execução da persona '{persona_id}': {exc}")


def check_server_availability(api_url: str) -> bool:
    """Retorna *True* se `api_url/health` responder *HTTP 200* em até 5 s."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


# ---------------------------------- Main -------------------------------------

if __name__ == "__main__":
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: variável de ambiente OPENAI_API_KEY não definida.")
        exit(1)

    parser = argparse.ArgumentParser(
        description="Executa personas definidas em JSON contra o BancoBot")

    # Execução geral
    parser.add_argument("--prompts-file", required=True, type=str,
                        help="Arquivo JSON com os prompts das personas")
    parser.add_argument("--api-url", type=str, default="http://localhost:8080",
                        help="URL base da API do BancoBot")
    parser.add_argument("--sequencial", action="store_true",
                        help="Executa as personas uma a uma, sem paralelismo")
    parser.add_argument("--window-size", "-w", type=int, default=4,
                        help="Máximo de UsuarioBots simultâneos (padrão: 4)")
    parser.add_argument("--passes", "-p", type=int, default=1,
                        help="Número de varreduras completas sobre o arquivo de prompts (padrão: 1)")
    parser.add_argument("--use-thinking", "-t", action="store_true",
                        help="Usa modelos mde linguagem de raciocínio")

    # Parâmetros de temporização (valores padrão)
    parser.add_argument("--typing-speed", type=float, default=40.0,
                        help="Velocidade média de digitação (palavras/minuto)")
    parser.add_argument("--thinking-min", type=float, default=2.0,
                        help="Tempo mínimo de reflexão (s)")
    parser.add_argument("--thinking-max", type=float, default=10.0,
                        help="Tempo máximo de reflexão (s)")
    parser.add_argument("--break-probability", type=float, default=0.05,
                        help="Probabilidade de pausa após uma mensagem")
    parser.add_argument("--break-min", type=float, default=60.0,
                        help="Pausa mínima (s)")
    parser.add_argument("--break-max", type=float, default=3600.0,
                        help="Pausa máxima (s)")
    parser.add_argument("--no-simulate-delays", action="store_true",
                        help="Ignora atrasos simulados (execução rápida)")

    args = parser.parse_args()

    # ---------------------------------------------------------------------
    # Pré-validações
    # ---------------------------------------------------------------------
    if args.passes < 1:
        print("ERRO: --passes deve ser >= 1.")
        exit(1)

    if not check_server_availability(args.api_url):
        print(f"ERRO: servidor BancoBot indisponível em {args.api_url}")
        exit(1)

    try:
        with open(args.prompts_file, "r", encoding="utf-8") as fp:
            prompts: dict = json.load(fp)
    except Exception as exc:
        print(f"ERRO: não foi possível ler {args.prompts_file}: {exc}")
        exit(1)

    if not prompts:
        print("ERRO: arquivo de prompts vazio.")
        exit(1)

    print(f"[INFO] {len(prompts)} personas carregadas de {args.prompts_file}.")

    # ---------------------------------------------------------------------
    # Construção da fila de execução com parsing das configurações
    # ---------------------------------------------------------------------
    parsed_personas = []
    for persona_id, persona_data in prompts.items():
        prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
            persona_data, args
        )
        parsed_personas.append((persona_id, prompt, typing_speed, thinking_range, temporal_offset))

    # Repetir conforme número de passes
    run_queue = parsed_personas * args.passes
    total_runs = len(run_queue)

    print(f"[INFO] Total de execuções planejadas: {total_runs} (passes = {args.passes}).")

    max_parallel = max(1, args.window_size)
    break_range = (args.break_min, args.break_max)
    use_thinking = True if args.use_thinking else False

    # ---------------------------------------------------------------------
    # Execução
    # ---------------------------------------------------------------------
    if args.sequencial:
        print("[INFO] Modo sequencial ativado…")
        for persona_id, persona_prompt, typing_speed, thinking_range, temporal_offset in run_queue:
            iniciar_usuario(
                persona_id,
                use_thinking,
                persona_prompt,
                api_url=args.api_url,
                typing_speed_wpm=typing_speed,
                thinking_time_range=thinking_range,
                break_probability=args.break_probability,
                break_time_range=break_range,
                simulate_delays=not args.no_simulate_delays,
                temporal_offset=temporal_offset,
            )
    else:
        print(f"[INFO] Executando em paralelo com até {max_parallel} threads…")
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = [
                executor.submit(
                    iniciar_usuario,
                    persona_id,
                    use_thinking,
                    persona_prompt,
                    api_url=args.api_url,
                    typing_speed_wpm=typing_speed,
                    thinking_time_range=thinking_range,
                    break_probability=args.break_probability,
                    break_time_range=break_range,
                    simulate_delays=not args.no_simulate_delays,
                    temporal_offset=temporal_offset,
                )
                for persona_id, persona_prompt, typing_speed, thinking_range, temporal_offset in run_queue
            ]

            # Feedback de progresso opcional
            for _ in as_completed(futures):
                pass  # Aguardamos todas completarem; logs acontecem dentro de iniciar_usuario

    print("[INFO] Todas as execuções concluídas.")