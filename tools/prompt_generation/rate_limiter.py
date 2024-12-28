import time
from collections import deque
from typing import Deque

class RateLimiter:
    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        """
        max_calls: número máximo de chamadas permitidas na janela de tempo (window_seconds).
        window_seconds: tamanho da janela, em segundos, na qual max_calls são permitidas.
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        # deque é mais eficiente para remoção de elementos no início.
        self.call_timestamps: Deque[float] = deque()

    def wait_for_slot(self):
        """
        Aguarda até que haja "vaga" para realizar nova chamada, respeitando max_calls
        dentro de window_seconds.
        """
        while True:
            now = time.time()

            # 1. Remove todos os timestamps fora da janela.
            while self.call_timestamps and (now - self.call_timestamps[0]) > self.window_seconds:
                self.call_timestamps.popleft()

            # 2. Se houver espaço para uma nova chamada, verifique a condição especial.
            if len(self.call_timestamps) < self.max_calls:
                # 3. Lógica especial caso estejamos exatamente no último slot.
                if len(self.call_timestamps) >= self.max_calls - 2:
                    tempo_falta = ((self.call_timestamps[0] + self.window_seconds) - now) * 0.75
                    if tempo_falta > 0:
                        print(f"Última chamada permitida dentro da janela de {self.window_seconds} segundos. Aguardando {tempo_falta:.2f} segundos.")
                        time.sleep(tempo_falta)

                # 4. Se já temos espaço, encerramos o loop.
                break

            # 5. Caso contrário, calculamos quanto tempo falta até o slot mais antigo sair da janela.
            tempo_falta = (self.call_timestamps[0] + self.window_seconds) - now
            if tempo_falta > 0:
                print(f"Limite de chamadas atingido. Aguardando {tempo_falta:.2f} segundos.")
                time.sleep(tempo_falta)

        # Registramos o timestamp da nova chamada
        self.call_timestamps.append(time.time())
