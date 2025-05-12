import os
import time
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests
import json
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

Exemplo de uso:
```
python run_prompts.py \
    --prompts-file ./prompts.json \
    --window-size 6 \
    --passes 10
```
"""

# ---------------------------- Funções utilitárias -----------------------------

def iniciar_usuario(persona_id: str,
                    think_exp: bool,
                    prompt_personalizado: str | None = None,
                    *,
                    api_url: str,
                    typing_speed_wpm: float,
                    thinking_time_range: tuple[float, float],
                    break_probability: float,
                    break_time_range: tuple[float, float],
                    simulate_delays: bool) -> None:
    """Instancia e executa um :class:`UsuarioBot` para a persona fornecida."""
    print(f"[INFO] Iniciando persona '{persona_id}'…")

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
    )

    try:
        usuario_bot.run(
            initial_query="Olá cliente Itaú! Como posso lhe ajudar?",
            max_iterations=10,
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

    # Parâmetros de temporização
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
            prompts: dict[str, str] = json.load(fp)
    except Exception as exc:
        print(f"ERRO: não foi possível ler {args.prompts_file}: {exc}")
        exit(1)

    if not prompts:
        print("ERRO: arquivo de prompts vazio.")
        exit(1)

    print(f"[INFO] {len(prompts)} personas carregadas de {args.prompts_file}.")

    # ---------------------------------------------------------------------
    # Construção da fila de execução
    # ---------------------------------------------------------------------
    persona_items = list(prompts.items())  # (persona_id, prompt)
    run_queue = persona_items * args.passes
    total_runs = len(run_queue)

    print(f"[INFO] Total de execuções planejadas: {total_runs} (passes = {args.passes}).")

    max_parallel = max(1, args.window_size)
    thinking_range = (args.thinking_min, args.thinking_max)
    break_range = (args.break_min, args.break_max)
    use_thinking = True if args.use_thinking else False

    # ---------------------------------------------------------------------
    # Execução
    # ---------------------------------------------------------------------
    if args.sequencial:
        print("[INFO] Modo sequencial ativado…")
        for persona_id, persona_prompt in run_queue:
            iniciar_usuario(
                persona_id,
                use_thinking,
                persona_prompt,
                api_url=args.api_url,
                typing_speed_wpm=args.typing_speed,
                thinking_time_range=thinking_range,
                break_probability=args.break_probability,
                break_time_range=break_range,
                simulate_delays=not args.no_simulate_delays,
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
                    typing_speed_wpm=args.typing_speed,
                    thinking_time_range=thinking_range,
                    break_probability=args.break_probability,
                    break_time_range=break_range,
                    simulate_delays=not args.no_simulate_delays,
                )
                for persona_id, persona_prompt in run_queue
            ]

            # Feedback de progresso opcional
            for _ in as_completed(futures):
                pass  # Aguardamos todas completarem; logs acontecem dentro de iniciar_usuario

    print("[INFO] Todas as execuções concluídas.")
