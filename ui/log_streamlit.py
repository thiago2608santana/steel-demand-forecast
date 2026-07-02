"""Captura do logging padrão para exibição ao vivo em containers Streamlit."""
import logging
from contextlib import contextmanager


class StreamlitLogHandler(logging.Handler):
    """Handler que acumula registros e os renderiza num st.empty()."""

    NOME = "streamlit_log_handler"

    def __init__(self, container, max_linhas: int = 40):
        super().__init__()
        self.set_name(self.NOME)
        self._container = container
        self._linhas: list[str] = []
        self._max_linhas = max_linhas
        self.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s — %(message)s", "%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._linhas.append(self.format(record))
            self._container.code("\n".join(self._linhas[-self._max_linhas:]), language=None)
        except Exception:  # noqa: BLE001 — logging nunca deve derrubar a UI
            pass


@contextmanager
def capturar_logs(container, level: int = logging.INFO):
    """Anexa um StreamlitLogHandler ao root logger durante o bloco.

    Remove handlers homônimos remanescentes antes de anexar — reruns do
    Streamlit não podem acumular handlers no root logger.
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        if h.get_name() == StreamlitLogHandler.NOME:
            root.removeHandler(h)

    handler = StreamlitLogHandler(container)
    handler.setLevel(level)
    root.addHandler(handler)
    nivel_anterior = root.level
    if root.level > level:
        root.setLevel(level)
    try:
        yield handler
    finally:
        root.removeHandler(handler)
        root.setLevel(nivel_anterior)
