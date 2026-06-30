"""Orquestrador ETL — executa todos os pipelines de dados em sequência.

Uso:
    python run_etl.py                          # Executa todos os pipelines
    python run_etl.py anfavea                  # Executa somente o pipeline ANFAVEA
    python run_etl.py anfavea cno              # Executa ANFAVEA e CNO
    python run_etl.py macro                    # Executa somente o pipeline macro

Pipelines disponíveis: anfavea, cno, macro, performance, tabela_mestre

Ordem recomendada de execução completa:
    1. anfavea, cno, performance  (requerem arquivos manuais em dados/raw/)
    2. macro                      (consome APIs públicas)
    3. tabela_mestre              (consolida dados/silver/ → dados/gold/)
"""
import logging
import sys

from config import CFG
from etl.anfavea import processar_anfavea
from etl.cno import processar_cno
from etl.macroeconomia import processar_macroeconomia
from etl.performance import processar_performance
from etl.tabela_mestre import processar_tabela_mestre

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

PIPELINES = {
    "anfavea": processar_anfavea,
    "cno": processar_cno,
    "macro": processar_macroeconomia,
    "performance": processar_performance,
    "tabela_mestre": processar_tabela_mestre,
}


def main(selecao: list[str] = None) -> int:
    """Executa os pipelines indicados e retorna o código de saída.

    Args:
        selecao: Lista de nomes de pipelines a executar. Se vazia ou None,
                 executa todos.

    Returns:
        0 se todos os pipelines concluíram sem erros, 1 caso contrário.
    """
    alvos = selecao if selecao else list(PIPELINES.keys())
    invalidos = [a for a in alvos if a not in PIPELINES]
    if invalidos:
        logger.error("Pipelines desconhecidos: %s. Disponíveis: %s", invalidos, list(PIPELINES.keys()))
        return 1

    logger.info("=== Iniciando ETL | Pipelines: %s ===", alvos)
    erros = []

    for nome in alvos:
        try:
            logger.info("--- Pipeline: %s ---", nome)
            PIPELINES[nome](CFG)
        except Exception as exc:  # noqa: BLE001
            logger.error("Falha em '%s': %s", nome, exc, exc_info=True)
            erros.append(nome)

    if erros:
        logger.error("=== ETL finalizado com erros nos pipelines: %s ===", erros)
        return 1

    logger.info("=== ETL finalizado com sucesso ===")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    sys.exit(main(args or None))
