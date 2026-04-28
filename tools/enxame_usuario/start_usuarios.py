import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import requests
from dotenv import load_dotenv

from source.simulation_config import carregar_config_v42, gerar_simulacoes
from source.tests.chatbot_test.usuario import UsuarioBot
from tools.enxame_usuario.simulation_projection import resolve_simulation_projection

"""
Script para executar uma suíte de simulações v4.2 contra o BancoBot.

Cada registro do schema v4.2 informa:
- persona_id
- missao_id
- dia_relativo
- offset
- ritmo

O script resolve o prompt final e os envelopes temporais via helper
compartilhado com o exportador de prévia CSV.
"""


def parse_persona_config(simulacao: dict, config: dict, default_args):
    """Converte uma instância simulada no pacote de execução do `UsuarioBot`.

    A função delega o trabalho de projeção para `resolve_simulation_projection`
    e extrai apenas o subconjunto de campos consumido pelo runner:
    prompt final, velocidade de digitação, intervalo de reflexão e
    deslocamento temporal.

    Args:
        simulacao: Registro estatístico já gerado pelo sampler.
        config: Configuração v4.2 usada para resolver persona, missão e tempo.
        default_args: Mantido apenas por compatibilidade com o fluxo atual do
            runner; não participa mais da resolução dos parâmetros.

    Returns:
        Tupla `(prompt, typing_speed_wpm, thinking_time_range, temporal_offset)`.
    """
    del default_args
    projection = resolve_simulation_projection(simulacao, config)

    return (
        projection["prompt"],
        projection["typing_speed_wpm"],
        projection["thinking_time_range"],
        projection["temporal_offset"],
    )


def iniciar_usuario(
    persona_id: str,
    think_exp: bool,
    prompt_personalizado: str | None = None,
    *,
    api_url: str,
    typing_speed_wpm: float,
    thinking_time_range: tuple[float, float],
    break_probability: float,
    break_time_range: tuple[float, float],
    simulate_delays: bool,
    temporal_offset: timedelta = timedelta(0),
) -> None:
    """Instancia e executa um `UsuarioBot` já parametrizado para a simulação.

    O `temporal_offset` desloca a percepção temporal do bot para o instante
    sintético projetado pela simulação. Os demais parâmetros controlam o ritmo
    operacional e o comportamento de pausas durante a conversa.
    """
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
        temporal_offset=temporal_offset,
    )

    try:
        usuario_bot.run(
            initial_query="Olá cliente Itaú, como posso lhe ajudar?",
            max_iterations=15,
        )
        print(f"[INFO] Persona '{persona_id}' concluiu a conversa.")
    except Exception as exc:
        print(f"[ERRO] Falha na execução da persona '{persona_id}': {exc}")


def check_server_availability(api_url: str) -> bool:
    """Verifica se o serviço BancoBot está acessível antes da execução.

    Returns:
        `True` quando o endpoint `/health` responde HTTP 200 dentro do timeout;
        `False` em qualquer erro de conexão ou resposta não saudável.
    """
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException:
        return False


if __name__ == "__main__":
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: variável de ambiente OPENAI_API_KEY não definida.")
        raise SystemExit(1)

    parser = argparse.ArgumentParser(
        description="Executa simulações v4.2 definidas em JSON contra o BancoBot"
    )

    parser.add_argument("--prompts-file", required=True, type=str, help="Arquivo JSON v4.2")
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://localhost:8080",
        help="URL base da API do BancoBot",
    )
    parser.add_argument(
        "--sequencial",
        action="store_true",
        help="Executa as personas uma a uma, sem paralelismo",
    )
    parser.add_argument(
        "--window-size",
        "-w",
        type=int,
        default=4,
        help="Máximo de UsuarioBots simultâneos (padrão: 4)",
    )
    parser.add_argument(
        "--passes",
        "-p",
        type=int,
        default=1,
        help="Número de varreduras completas sobre o arquivo de prompts (padrão: 1)",
    )
    parser.add_argument(
        "--use-thinking",
        "-t",
        action="store_true",
        help="Usa modelos de linguagem de raciocínio",
    )

    parser.add_argument("--typing-speed", type=float, default=40.0)
    parser.add_argument("--thinking-min", type=float, default=2.0)
    parser.add_argument("--thinking-max", type=float, default=10.0)
    parser.add_argument("--break-probability", type=float, default=0.05)
    parser.add_argument("--break-min", type=float, default=60.0)
    parser.add_argument("--break-max", type=float, default=3600.0)
    parser.add_argument(
        "--no-simulate-delays",
        action="store_true",
        help="Ignora atrasos simulados (execução rápida)",
    )

    args = parser.parse_args()

    if args.passes < 1:
        print("ERRO: --passes deve ser >= 1.")
        raise SystemExit(1)

    if not check_server_availability(args.api_url):
        print(f"ERRO: servidor BancoBot indisponível em {args.api_url}")
        raise SystemExit(1)

    try:
        config = carregar_config_v42(args.prompts_file)
        simulacoes = gerar_simulacoes(config)
    except Exception as exc:
        print(f"ERRO: não foi possível ler {args.prompts_file}: {exc}")
        raise SystemExit(1)

    if not simulacoes:
        print("ERRO: arquivo de prompts vazio.")
        raise SystemExit(1)

    print(f"[INFO] {len(simulacoes)} simulações carregadas de {args.prompts_file}.")

    parsed_personas = []
    for simulacao in simulacoes:
        prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
            simulacao,
            config,
            args,
        )
        parsed_personas.append(
            (
                simulacao["persona_id"],
                prompt,
                typing_speed,
                thinking_range,
                temporal_offset,
            )
        )

    run_queue = parsed_personas * args.passes
    total_runs = len(run_queue)

    print(f"[INFO] Total de execuções planejadas: {total_runs} (passes = {args.passes}).")

    max_parallel = max(1, args.window_size)
    break_range = (args.break_min, args.break_max)
    use_thinking = bool(args.use_thinking)

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

            for _ in as_completed(futures):
                pass

    print("[INFO] Todas as execuções concluídas.")
