import argparse
import os
import secrets
from contextlib import closing
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from source.simulation_config import carregar_config_v44, gerar_simulacoes
from source.tests.chatbot_test.usuario import UsuarioBot
from tools.enxame_usuario import resume_state
from tools.enxame_usuario.simulation_projection import resolve_simulation_projection

QUEUE_ABORT_CLASS_NAMES = {
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AuthenticationError",
    "RateLimitError",
}

QUEUE_ABORT_STATUS_CODES = {401, 429, 502, 503, 504}

QUEUE_ABORT_TEXT_MARKERS = (
    "incorrect api key",
    "invalid_api_key",
    "insufficient_quota",
    "rate limit",
    "quota",
    "billing",
    "429",
)


class QueueAbortError(RuntimeError):
    """Sinaliza uma falha sistemica que deve interromper a fila."""

    def __init__(self, original: BaseException):
        self.original = original
        super().__init__(str(original))


def _iter_exception_chain(exc: BaseException):
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _response_text(response) -> str:
    if response is None:
        return ""
    try:
        return response.text or ""
    except Exception:
        return ""


def is_queue_abort_error(exc: BaseException) -> bool:
    """Classifica falhas que indicam indisponibilidade sistemica da fila."""
    for current in _iter_exception_chain(exc):
        if isinstance(current, (requests.ConnectionError, requests.Timeout)):
            return True

        class_name = type(current).__name__
        if class_name in QUEUE_ABORT_CLASS_NAMES:
            return True

        response = getattr(current, "response", None)
        status_code = getattr(response, "status_code", None)
        status_code = status_code or getattr(current, "status_code", None)

        if isinstance(current, requests.HTTPError) and status_code in QUEUE_ABORT_STATUS_CODES:
            return True

        response_text = _response_text(response).lower()
        if response_text and any(marker in response_text for marker in QUEUE_ABORT_TEXT_MARKERS):
            return True

        exception_text = str(current).lower()
        invalid_key_error = "invalid_api_key" in exception_text or "incorrect api key" in exception_text
        if invalid_key_error and ("401" in exception_text or class_name == "AuthenticationError"):
            return True

    return False


def _queue_abort_message(exc: QueueAbortError | BaseException) -> str:
    original = getattr(exc, "original", exc)
    return str(original) or type(original).__name__


def print_queue_abort_resume_hint(args, pending_count: int, exc: QueueAbortError) -> None:
    prompts_file = getattr(args, "prompts_file", "<mesmo arquivo de prompts>")
    passes = getattr(args, "passes", "<mesmo valor de passes>")
    print(f"[ERRO] Falha sistemica detectada; fila interrompida: {_queue_abort_message(exc)}")
    print(f"[INFO] {pending_count} instancia(s) ainda pendente(s) foram preservadas para retomada.")
    print(
        "[INFO] Retome quando a situacao normalizar com: "
        f"python tools/enxame_usuario/start_usuarios.py --prompts-file {prompts_file} "
        f"--passes {passes} --resume"
    )

"""
Script para executar uma suíte de simulações v4.4 contra o BancoBot.

Cada registro do schema v4.4 informa:
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
        config: Configuração v4.4 usada para resolver persona, missão e tempo.
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
    run_id: str,
    instance_key: str,
    db_path: str,
    temporal_offset: timedelta = timedelta(0),
) -> bool:
    """Instancia e executa um `UsuarioBot` já parametrizado para a simulação.

    O `temporal_offset` desloca a percepção temporal do bot para o instante
    sintético projetado pela simulação. Os demais parâmetros controlam o ritmo
    operacional e o comportamento de pausas durante a conversa.
    """
    print(f"[INFO] Iniciando persona '{persona_id}'…")

    if temporal_offset != timedelta(0):
        print(f"[INFO] Persona '{persona_id}' aplicando offset temporal de {temporal_offset}")

    thread_id = secrets.token_hex(8)
    with closing(resume_state.connect(db_path)) as conn:
        resume_state.mark_instance_running(
            conn,
            run_id=run_id,
            instance_key=instance_key,
            thread_id=thread_id,
        )

    try:
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
            thread_id=thread_id,
        )
        usuario_bot.run(
            initial_query="Olá cliente Itaú, como posso lhe ajudar?",
            max_iterations=15,
        )
        with closing(resume_state.connect(db_path)) as conn:
            resume_state.mark_instance_completed(conn, run_id=run_id, instance_key=instance_key)
        print(f"[INFO] Persona '{persona_id}' concluiu a conversa.")
        return True
    except Exception as exc:
        abort_queue = is_queue_abort_error(exc)
        error = f"QUEUE_ABORT: {exc}" if abort_queue else str(exc)
        with closing(resume_state.connect(db_path)) as conn:
            resume_state.mark_instance_not_finished(
                conn,
                run_id=run_id,
                instance_key=instance_key,
                error=error,
            )
        print(f"[ERRO] Falha na execução da persona '{persona_id}': {exc}")
        if abort_queue:
            raise QueueAbortError(exc) from exc
        return False


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


def build_run_queue(simulacoes: list[dict], config: dict, args) -> list[dict]:
    """Materializa a fila determinística de instâncias executáveis."""
    run_queue = []
    queue_index = 0
    for pass_index in range(1, args.passes + 1):
        for simulacao in simulacoes:
            prompt, typing_speed, thinking_range, temporal_offset = parse_persona_config(
                simulacao,
                config,
                args,
            )
            queue_index += 1
            run_queue.append(
                {
                    "instance_key": f"pass-{pass_index:04d}:simulation-{int(simulacao['id']):06d}",
                    "simulation_id": int(simulacao["id"]),
                    "pass_index": pass_index,
                    "queue_index": queue_index,
                    "persona_id": simulacao["persona_id"],
                    "prompt": prompt,
                    "typing_speed_wpm": typing_speed,
                    "thinking_time_range": thinking_range,
                    "temporal_offset": temporal_offset,
                }
            )
    return run_queue


def execution_args_snapshot(args) -> dict:
    """Registra a linha de comando operacional sem incluir dados sensíveis."""
    return {
        "prompts_file": str(Path(args.prompts_file).resolve()),
        "passes": args.passes,
        "sequencial": bool(args.sequencial),
        "window_size": args.window_size,
        "api_url": args.api_url,
        "use_thinking": bool(args.use_thinking),
        "break_probability": args.break_probability,
        "break_min": args.break_min,
        "break_max": args.break_max,
        "no_simulate_delays": bool(args.no_simulate_delays),
    }


def submit_usuario(executor, item: dict, *, args, run_id: str, db_path: str, break_range, use_thinking: bool):
    return executor.submit(
        iniciar_usuario,
        item["persona_id"],
        use_thinking,
        item["prompt"],
        api_url=args.api_url,
        typing_speed_wpm=item["typing_speed_wpm"],
        thinking_time_range=item["thinking_time_range"],
        break_probability=args.break_probability,
        break_time_range=break_range,
        simulate_delays=not args.no_simulate_delays,
        temporal_offset=item["temporal_offset"],
        run_id=run_id,
        instance_key=item["instance_key"],
        db_path=db_path,
    )


def run_sequential(run_queue: list[dict], *, args, run_id: str, db_path: str, break_range, use_thinking: bool) -> None:
    for item in run_queue:
        iniciar_usuario(
            item["persona_id"],
            use_thinking,
            item["prompt"],
            api_url=args.api_url,
            typing_speed_wpm=item["typing_speed_wpm"],
            thinking_time_range=item["thinking_time_range"],
            break_probability=args.break_probability,
            break_time_range=break_range,
            simulate_delays=not args.no_simulate_delays,
            temporal_offset=item["temporal_offset"],
            run_id=run_id,
            instance_key=item["instance_key"],
            db_path=db_path,
        )


def run_parallel_bounded(run_queue: list[dict], *, args, run_id: str, db_path: str, break_range, use_thinking: bool) -> None:
    max_parallel = max(1, args.window_size)
    print(f"[INFO] Executando em paralelo com até {max_parallel} threads…")

    pending_iter = iter(run_queue)
    active = {}

    executor = ThreadPoolExecutor(max_workers=max_parallel)
    try:
        while len(active) < max_parallel:
            try:
                item = next(pending_iter)
            except StopIteration:
                break
            active[submit_usuario(
                executor,
                item,
                args=args,
                run_id=run_id,
                db_path=db_path,
                break_range=break_range,
                use_thinking=use_thinking,
            )] = item

        while active:
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                active.pop(future)
                future.result()
                try:
                    item = next(pending_iter)
                except StopIteration:
                    continue
                active[submit_usuario(
                    executor,
                    item,
                    args=args,
                    run_id=run_id,
                    db_path=db_path,
                    break_range=break_range,
                    use_thinking=use_thinking,
                )] = item
    except KeyboardInterrupt:
        for future in active:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        with closing(resume_state.connect(db_path)) as conn:
            changed = resume_state.interrupt_run(conn, run_id)
        print(f"\n[INFO] Interrupção recebida; {changed} instância(s) marcadas como não finalizadas.")
        raise SystemExit(130)
    except QueueAbortError:
        for future in active:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)


def finalize_run_after_invocation(db_path: str, run_id: str, *, run_interrupted: bool) -> bool | None:
    if run_interrupted:
        print("[INFO] Run interrompida preservada para possível retomada.")
        return None

    with closing(resume_state.connect(db_path)) as conn:
        completed = resume_state.finalize_run_if_no_pending(conn, run_id)
    if not completed:
        print("[INFO] Run ainda possui instâncias pendentes para possível retomada.")
    return completed


if __name__ == "__main__":
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: variável de ambiente OPENAI_API_KEY não definida.")
        raise SystemExit(1)

    parser = argparse.ArgumentParser(
        description="Executa simulações v4.4 definidas em JSON contra o BancoBot"
    )

    parser.add_argument("--prompts-file", required=True, type=str, help="Arquivo JSON v4.4")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Retoma a run incompleta compatível mais recente",
    )
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
        config = carregar_config_v44(args.prompts_file)
        simulacoes = gerar_simulacoes(config)
    except Exception as exc:
        print(f"ERRO: não foi possível ler {args.prompts_file}: {exc}")
        raise SystemExit(1)

    if not simulacoes:
        print("ERRO: arquivo de prompts vazio.")
        raise SystemExit(1)

    prompts_file_hash = resume_state.calculate_file_hash(args.prompts_file)
    full_run_queue = build_run_queue(simulacoes, config, args)
    queue_by_key = {item["instance_key"]: item for item in full_run_queue}
    total_runs = len(full_run_queue)

    print(f"[INFO] {len(simulacoes)} simulações carregadas de {args.prompts_file}.")
    print(f"[INFO] Total de execuções planejadas: {total_runs} (passes = {args.passes}).")

    db_path = resume_state.DATABASE_PATH
    prompts_file_path = str(Path(args.prompts_file).resolve())

    with closing(resume_state.connect(db_path)) as conn:
        resume_state.ensure_schema(conn)
        if args.resume:
            run = resume_state.find_resume_run(
                conn,
                prompts_file_hash=prompts_file_hash,
                passes=args.passes,
            )
            if run is None:
                print("ERRO: nenhuma run incompleta compatível encontrada para retomar.")
                raise SystemExit(1)
            run_id = run["run_id"]
            stale_count = resume_state.mark_stale_running_instances_not_finished(conn, run_id)
            if stale_count:
                print(f"[INFO] {stale_count} instância(s) em execução antiga marcadas como não finalizadas.")
            pending_rows = resume_state.get_pending_instances(conn, run_id)
            run_queue = [queue_by_key[row["instance_key"]] for row in pending_rows]
            print(f"[INFO] Retomando run {run_id}; {len(run_queue)} instância(s) ainda não iniciada(s).")
        else:
            active_count = resume_state.count_active_compatible_runs(
                conn,
                prompts_file_hash=prompts_file_hash,
                passes=args.passes,
            )
            if active_count:
                print(
                    "ERRO: já existe run incompleta compatível. "
                    "Use --resume para continuar ou finalize/remova o estado anterior."
                )
                raise SystemExit(1)
            run_id = resume_state.create_run(
                conn,
                prompts_file_hash=prompts_file_hash,
                prompts_file_path=prompts_file_path,
                passes=args.passes,
                instances=full_run_queue,
                args=execution_args_snapshot(args),
            )
            run_queue = full_run_queue
            print(f"[INFO] Nova run criada: {run_id}.")

    if not run_queue:
        with closing(resume_state.connect(db_path)) as conn:
            resume_state.finalize_run_if_no_pending(conn, run_id)
        print("[INFO] Não há instâncias pendentes para executar.")
        raise SystemExit(0)

    total_runs = len(run_queue)
    print(f"[INFO] Execuções desta invocação: {total_runs}.")

    break_range = (args.break_min, args.break_max)
    use_thinking = bool(args.use_thinking)
    run_interrupted = False

    try:
        if args.sequencial:
            print("[INFO] Modo sequencial ativado…")
            run_sequential(
                run_queue,
                args=args,
                run_id=run_id,
                db_path=db_path,
                break_range=break_range,
                use_thinking=use_thinking,
            )
        else:
            run_parallel_bounded(
                run_queue,
                args=args,
                run_id=run_id,
                db_path=db_path,
                break_range=break_range,
                use_thinking=use_thinking,
            )
    except KeyboardInterrupt:
        run_interrupted = True
        with closing(resume_state.connect(db_path)) as conn:
            changed = resume_state.interrupt_run(conn, run_id)
        print(f"\n[INFO] Interrupção recebida; {changed} instância(s) marcadas como não finalizadas.")
        raise SystemExit(130)
    except QueueAbortError as exc:
        run_interrupted = True
        with closing(resume_state.connect(db_path)) as conn:
            resume_state.interrupt_run(conn, run_id)
            pending_count = len(resume_state.get_pending_instances(conn, run_id))
        print_queue_abort_resume_hint(args, pending_count, exc)
        raise SystemExit(75)
    finally:
        finalize_run_after_invocation(db_path, run_id, run_interrupted=run_interrupted)

    print("[INFO] Todas as execuções concluídas.")
