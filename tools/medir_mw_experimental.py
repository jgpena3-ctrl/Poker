"""Mide el motor experimental MW por etapa, con fixtures sintéticos.

Uso:
    python tools/medir_mw_experimental.py [repeticiones]

No lee manos históricas, no escribe artefactos y no alimenta serving. Los
números son mediciones locales: no constituyen un presupuesto ni una promesa
de latencia. Para afirmar un límite (por ejemplo 8 s) hay que medir el flujo
completo en la máquina y el conjunto de fixtures objetivo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.mw_benchmark import format_report, run_benchmark


def main(argv):
    repeats = int(argv[1]) if len(argv) > 1 else 5
    report = run_benchmark(repeats=repeats)
    print(format_report(report))


if __name__ == '__main__':
    main(sys.argv)
