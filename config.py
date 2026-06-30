"""Carregador de configuração a partir do config.yaml."""
from pathlib import Path
import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config(path: str = None) -> dict:
    """Carrega e retorna o dicionário de configuração do arquivo YAML."""
    config_path = Path(path) if path else _CONFIG_PATH
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


CFG: dict = load_config()
