# source/rag/logging/rag_logger.py (FIXED)
import os
import json
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, IO
from io import StringIO
import threading
from contextlib import contextmanager

# Import LangChain message types for proper handling
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


class RAGLogger:
    """
    Logger específico para o sistema RAG que mantém logs separados por mensagem
    e gera arquivos ZIP com os logs de uma sessão completa.
    """

    def __init__(self,
                 thread_id: str,
                 persona_id: str = "unknown",
                 log_dir: str = "./rag_logs"):
        """
        Inicializa o RAGLogger.

        Args:
            thread_id: ID da thread/sessão
            persona_id: ID da persona (usuário)
            log_dir: Diretório para armazenar logs temporários
        """
        self.thread_id = thread_id
        self.persona_id = persona_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Buffers de log por mensagem
        self.message_buffers: Dict[int, StringIO] = {}
        self.current_message_index = 0

        # Formatador de log
        self.formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S.%f'
        )

        # Lock para thread safety
        self.lock = threading.Lock()

        # Metadados da sessão
        self.session_metadata = {
            "thread_id": thread_id,
            "persona_id": persona_id,
            "start_time": datetime.now().isoformat(),
            "messages": []
        }

    def start_new_message(self, query: str) -> int:
        """
        Inicia o logging para uma nova mensagem do usuário.

        Args:
            query: A query/mensagem do usuário

        Returns:
            O índice da mensagem
        """
        with self.lock:
            self.current_message_index += 1

            # Cria novo buffer para esta mensagem
            self.message_buffers[self.current_message_index] = StringIO()

            # Registra metadados da mensagem
            message_metadata = {
                "index": self.current_message_index,
                "query": query,
                "start_time": datetime.now().isoformat(),
                "logs": []
            }
            self.session_metadata["messages"].append(message_metadata)

            # Log inicial
            self._write_to_current_buffer(
                "INFO",
                f"Starting processing for message {self.current_message_index}",
                {"query": query}
            )

            return self.current_message_index

    def log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Registra uma mensagem de log no buffer da mensagem atual.

        Args:
            level: Nível do log (INFO, DEBUG, WARNING, ERROR)
            message: Mensagem de log
            data: Dados adicionais para incluir no log
        """
        with self.lock:
            if self.current_message_index in self.message_buffers:
                self._write_to_current_buffer(level, message, data)

    def log_function_start(self, function_name: str, state_snapshot: Dict[str, Any]):
        """
        Registra o início de uma função RAG.

        Args:
            function_name: Nome da função
            state_snapshot: Snapshot do estado atual
        """
        self.log("INFO", f"Starting {function_name}", {
            "function": function_name,
            "state": self._sanitize_state(state_snapshot)
        })

    def log_function_end(self, function_name: str, result: Dict[str, Any], duration_ms: float):
        """
        Registra o fim de uma função RAG.

        Args:
            function_name: Nome da função
            result: Resultado da função
            duration_ms: Duração em milissegundos
        """
        self.log("INFO", f"Completed {function_name}", {
            "function": function_name,
            "result": self._sanitize_state(result),
            "duration_ms": duration_ms
        })

    def log_retrieval(self, datasource: str, query: str, num_docs: int, docs_preview: List[str]):
        """
        Registra informações de recuperação de documentos.

        Args:
            datasource: Nome da fonte de dados
            query: Query usada para recuperação
            num_docs: Número de documentos recuperados
            docs_preview: Preview dos documentos (primeiros 200 chars)
        """
        self.log("INFO", "Document retrieval", {
            "datasource": datasource,
            "query": query,
            "num_documents": num_docs,
            "documents_preview": docs_preview
        })

    def log_grading(self, document_grades: List[Dict[str, Any]]):
        """
        Registra resultados da avaliação de documentos.

        Args:
            document_grades: Lista com avaliação de cada documento
        """
        self.log("INFO", "Document grading completed", {
            "total_documents": len(document_grades),
            "relevant_count": sum(1 for g in document_grades if g.get("relevant", False)),
            "grades": document_grades
        })

    def log_routing_decision(self, datasource: str, confidence: Optional[float] = None):
        """
        Registra decisão de roteamento.

        Args:
            datasource: Datasource selecionado
            confidence: Confiança na decisão (se disponível)
        """
        self.log("INFO", "Routing decision", {
            "selected_datasource": datasource,
            "confidence": confidence
        })

    def log_query_rewrite(self, original: str, rewrites: List[str]):
        """
        Registra reescrita de query.

        Args:
            original: Query original
            rewrites: Queries reescritas
        """
        self.log("INFO", "Query rewriting", {
            "original_query": original,
            "rewritten_queries": rewrites,
            "num_rewrites": len(rewrites)
        })

    def log_final_response(self, response: str, response_type: str):
        """
        Registra a resposta final.

        Args:
            response: Resposta gerada
            response_type: Tipo da resposta (relevant/fallback)
        """
        self.log("INFO", "Final response generated", {
            "response_type": response_type,
            "response_length": len(response),
            "response_preview": response[:500] + "..." if len(response) > 500 else response
        })

    def log_error(self, error_type: str, error_message: str, traceback: Optional[str] = None):
        """
        Registra um erro.

        Args:
            error_type: Tipo do erro
            error_message: Mensagem de erro
            traceback: Traceback completo (opcional)
        """
        self.log("ERROR", f"Error occurred: {error_type}", {
            "error_type": error_type,
            "error_message": error_message,
            "traceback": traceback
        })

    def generate_zip(self, output_path: Optional[str] = None) -> str:
        """
        Gera um arquivo ZIP com todos os logs da sessão.

        Args:
            output_path: Caminho para salvar o ZIP (opcional)

        Returns:
            Caminho do arquivo ZIP gerado
        """
        with self.lock:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = self.log_dir / f"rag_logs_{self.persona_id}_{self.thread_id}_{timestamp}.zip"

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Adiciona logs de cada mensagem
                for msg_index, buffer in self.message_buffers.items():
                    filename = f"{msg_index:03d}_{self.persona_id}_{self.thread_id}.log"
                    zipf.writestr(filename, buffer.getvalue())

                # Adiciona metadados da sessão
                self.session_metadata["end_time"] = datetime.now().isoformat()
                metadata_filename = f"session_metadata_{self.persona_id}_{self.thread_id}.json"
                zipf.writestr(metadata_filename, json.dumps(self.session_metadata, indent=2))

                # Adiciona um resumo
                summary = self._generate_session_summary()
                summary_filename = f"session_summary_{self.persona_id}_{self.thread_id}.txt"
                zipf.writestr(summary_filename, summary)

            return str(output_path)

    def _write_to_current_buffer(self, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """
        Escreve no buffer da mensagem atual.
        """
        if self.current_message_index not in self.message_buffers:
            return

        buffer = self.message_buffers[self.current_message_index]

        # Cria registro de log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }

        if data:
            log_entry["data"] = data

        # Escreve no buffer como JSON Lines
        buffer.write(json.dumps(log_entry) + "\n")

        # Também adiciona aos metadados
        if self.session_metadata["messages"]:
            current_message_metadata = self.session_metadata["messages"][-1]
            current_message_metadata["logs"].append(log_entry)

    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove ou trunca campos muito grandes do estado para logging.
        Converte objetos não serializáveis do LangChain.
        """
        sanitized = {}

        for key, value in state.items():
            # Lidar com mensagens do LangChain
            if isinstance(value, BaseMessage):
                sanitized[key] = {
                    "_type": value.__class__.__name__,
                    "content": value.content,
                    "type": value.type
                }
            elif isinstance(value, list):
                # Verificar se é uma lista de mensagens
                if value and isinstance(value[0], BaseMessage):
                    sanitized[key] = [
                        {
                            "_type": msg.__class__.__name__,
                            "content": msg.content,
                            "type": msg.type
                        } for msg in value[:5]  # Limitar a 5 mensagens
                    ]
                elif key in ["context", "relevant_context", "aggregated_docs"]:
                    # Para listas de documentos, mostra apenas o tamanho e preview
                    sanitized[key] = {
                        "count": len(value),
                        "preview": value[:2] if value else []
                    }
                else:
                    # Para outras listas, tentar serializar normalmente
                    try:
                        sanitized[key] = value
                    except TypeError:
                        sanitized[key] = f"<Non-serializable list of {len(value)} items>"
            elif isinstance(value, str) and len(value) > 1000:
                # Trunca strings muito longas
                sanitized[key] = value[:1000] + "..."
            elif isinstance(value, dict):
                # Recursivamente sanitizar dicionários
                try:
                    sanitized[key] = self._sanitize_state(value)
                except Exception:
                    sanitized[key] = f"<Non-serializable dict with {len(value)} keys>"
            else:
                # Tentar serializar outros tipos
                try:
                    # Teste rápido de serializabilidade
                    json.dumps(value)
                    sanitized[key] = value
                except (TypeError, ValueError):
                    # Se não for serializável, usar representação string
                    sanitized[key] = f"<Non-serializable {type(value).__name__}>"

        return sanitized

    def _generate_session_summary(self) -> str:
        """
        Gera um resumo da sessão.
        """
        summary = []
        summary.append("RAG SESSION SUMMARY")
        summary.append("=" * 50)
        summary.append(f"Thread ID: {self.thread_id}")
        summary.append(f"Persona ID: {self.persona_id}")
        summary.append(f"Start Time: {self.session_metadata['start_time']}")
        summary.append(f"End Time: {self.session_metadata.get('end_time', 'N/A')}")
        summary.append(f"Total Messages: {len(self.session_metadata['messages'])}")
        summary.append("")

        for msg in self.session_metadata["messages"]:
            summary.append(f"Message {msg['index']}:")
            summary.append(f"  Query: {msg['query'][:100]}...")
            summary.append(f"  Start Time: {msg['start_time']}")
            summary.append(f"  Total Logs: {len(msg['logs'])}")

            # Conta logs por nível
            log_levels = {}
            for log in msg["logs"]:
                level = log.get("level", "UNKNOWN")
                log_levels[level] = log_levels.get(level, 0) + 1

            summary.append(f"  Log Levels: {log_levels}")
            summary.append("")

        return "\n".join(summary)

    def close(self):
        """
        Fecha todos os buffers.
        """
        with self.lock:
            for buffer in self.message_buffers.values():
                buffer.close()
            self.message_buffers.clear()


@contextmanager
def rag_function_logger(logger: Optional[RAGLogger], function_name: str, state: Dict[str, Any]):
    """
    Context manager para logging de funções RAG.

    Args:
        logger: RAGLogger instance (pode ser None)
        function_name: Nome da função
        state: Estado atual
    """
    if not logger:
        yield logger
        return

    start_time = datetime.now()
    logger.log_function_start(function_name, state)

    try:
        yield logger
    finally:
        duration = (datetime.now() - start_time).total_seconds() * 1000
        # Nota: O resultado será logado pela função que chama
        logger.log("DEBUG", f"Function {function_name} completed in {duration:.2f}ms", {
            "duration_ms": duration
        })


# Utilidades para facilitar o logging
def log_state_transition(logger: Optional[RAGLogger], from_node: str, to_node: str, reason: str = ""):
    """
    Registra transição entre nós do workflow.
    """
    if logger:
        logger.log("INFO", f"State transition: {from_node} → {to_node}", {
            "from_node": from_node,
            "to_node": to_node,
            "reason": reason
        })