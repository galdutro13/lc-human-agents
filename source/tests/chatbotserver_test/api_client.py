import httpx
import logging
from typing import Dict, Any, Optional
import json

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ApiClient:
    """Cliente API para comunicação entre serviços."""

    def __init__(self, base_url: str, timeout: int = 30):
        """
        Inicializa o cliente API.

        :param base_url: URL base do serviço (ex: http://localhost:8000)
        :param timeout: Timeout em segundos para requisições
        """
        self.base_url = base_url
        self.timeout = timeout

    async def request(
            self,
            method: str,
            endpoint: str,
            data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Realiza uma requisição HTTP para o serviço.

        :param method: Método HTTP (GET, POST, etc)
        :param endpoint: Endpoint da API
        :param data: Dados para o corpo da requisição
        :param params: Parâmetros de query string
        :param headers: Headers HTTP
        :return: Resposta da API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        if headers is None:
            headers = {}

        headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, params=params, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, params=params, headers=headers)
                else:
                    raise ValueError(f"Método HTTP não suportado: {method}")

                response.raise_for_status()
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Erro na requisição para {url}: {str(e)}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"Erro HTTP {e.response.status_code} para {url}: {e.response.text}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Erro ao decodificar resposta JSON de {url}")
            raise ValueError("Resposta inválida do servidor")


class BancoApiClient(ApiClient):
    """Cliente API específico para o serviço BancoBot."""

    async def send_message(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia uma mensagem para o BancoBot.

        :param message: Mensagem a ser enviada
        :param thread_id: ID do thread da conversa
        :return: Resposta do BancoBot
        """
        data = {"message": message}
        if thread_id:
            data["thread_id"] = thread_id

        return await self.request("POST", "/message", data=data)

    async def get_status(self, thread_id: str) -> Dict[str, Any]:
        """
        Obtém o status de um thread de conversa.

        :param thread_id: ID do thread da conversa
        :return: Status do thread
        """
        return await self.request("GET", f"/status/{thread_id}")


class UsuarioApiClient(ApiClient):
    """Cliente API específico para o serviço UsuarioBot."""

    async def send_message(self, message: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Envia uma mensagem para o UsuarioBot.

        :param message: Mensagem a ser enviada
        :param thread_id: ID do thread da conversa
        :return: Resposta do UsuarioBot
        """
        data = {"message": message}
        if thread_id:
            data["thread_id"] = thread_id

        return await self.request("POST", "/message", data=data)

    async def create_session(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria uma nova sessão de UsuarioBot.

        :param config: Configuração para o UsuarioBot
        :return: Detalhes da sessão criada
        """
        return await self.request("POST", "/session", data=config)