# -*- coding: utf-8 -*-
"""Los tres falsos positivos del barrido, y por que no vuelven.

Un detector que senala una linea correcta no es un detector: es ruido, y el
ruido entrena a no mirar nada. Los tres son el mismo error con ropa distinta —
el NUMERO coincide y el SUJETO no— y cada uno senalo algo distinto:

1. `DOCS/FASE_D_PLAN.md`
       | defecto | publicado | ahora | ...
       | **TOTAL** | **78** | **51** |
   El 78 es la suma de cuatro DEFECTOS de datos. Lo unico que decia
   «poblacion» era la palabra «TOTAL», que no dice de que.

2. `DOCS/TECNICO.md`
       Resultados reales (perfil con mas muestra): ... 236 manos
   El 236 es el tamano de un perfil del grid. Lo unico que decia «poblacion»
   era «muestra», y aqui «muestra» es «mas datos», no la muestra etiquetada.

3. `DOCS/CONTRATO_PREFLOP.md`
       ... son 2 270 millones de evaluaciones
   El 270 no es un numero: es la cola de un numero con espacio de millar. Y
   ese documento es un CONTRATO FIRMADO, que no se toca: el fallo era del
   escaner.

Los tres exports tres correcciones distintas, y las tres son reglas que no
existen por casualidad:

  - el sujeto se mira en la FILA **o** en el ENCABEZADO de la tabla
  - las palabras de sujeto no pueden ser ambiguas
  - los numeros se comparan ENTEROS, no por limites de token
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import retraccion_scan as rs                               # noqa: E402


# ---------------------------------------------------------------- 1
def test_un_total_de_defectos_no_es_un_total_de_observaciones():
    """El sujeto de un numero esta en el encabezado, y «TOTAL» no es un
    sujeto: no dice DE QUE total."""
    texto = ('| defecto | publicado | ahora | dentro de la ventana |\n'
             '|---|---:|---:|---:|\n'
             '| `IMPORTE_SUBIDA` | 36 | 31 | 25 |\n'
             '| `ACCION_FANTASMA` | 16 | 2 | 2 |\n'
             '| **TOTAL** | **78** | **51** | 42 |\n')
    assert rs.frases_retiradas_en(texto)[0] == [], (
        'un total de defectos no es un total de observaciones')
    # y con el sujeto en la fila, si lo hubiera, si se senalaria
    texto2 = texto.replace('| defecto |', '| poblacion |')
    assert rs.frases_retiradas_en(texto2)[0], (
        'pero si el encabezado dice poblacion, si')


# ---------------------------------------------------------------- 2
def test_el_tamanio_de_un_perfil_no_es_un_corte_postflop():
    """"Perfil con mas muestra" es un perfil con mas DATOS."""
    texto = ('- Resultados reales (perfil con mas muestra): '
             'Regular/no_raise 236 manos (open 51, fold 123, bb_check 27).\n')
    assert rs.frases_retiradas_en(texto)[0] == [], (
        'el tamano de un perfil no es un numero de cortes postflop')


# ---------------------------------------------------------------- 3
def test_un_numero_con_espacio_de_millar_no_es_el_numero_retirado():
    """`2 270 millones` es dos millones doscientos setenta mil. Y el
    documento es un contrato firmado: el fallo era del escaner."""
    texto = ('| 1 | **exacto o muestreado** | `equity_preflop.py` enumera '
             'las 1 712 304 manos. Contra un rango de 1326 combos son '
             '2 270 millones de evaluaciones. |\n')
    assert rs.frases_retiradas_en(texto)[0] == [], (
        'ha encontrado 270 dentro de "2 270 millones"')
    # y un 270 de verdad SI se ve. Y fíjate en que el control positivo NO
    # puede ser "2 270": normalizado es 2270, que no es 270. Que un numero con
    # separador de millar NO sea el numero retirado es justo lo que se quiere.
    texto2 = ('| | |\n'
              '|---|---:|\n'
              '| cortes postflop de la poblacion | **270** |\n')
    malas, _cit = rs.frases_retiradas_en(texto2)
    assert malas, 'y un numero REAL de 270 si se senala'
    assert malas[0][1] == '270'
    texto3 = ('| | |\n'
              '|---|---:|\n'
              '| cortes postflop de la poblacion | **2 270** |\n')
    assert rs.frases_retiradas_en(texto3)[0] == [], (
        'y "2 270" no es el 270 retirado: son dos millones doscientos setenta '
        'mil. Normalizado, 2270, que no es 270')


def test_un_numero_retirado_se_sigue_viendo():
    """Y lo ultimo: que la regla no se haya estrechado tanto que deje pasar
    lo que tiene que cazar. Este es el caso por el que existe."""
    texto = ('| | |\n'
             '|---|---:|\n'
             '| cortes preflop de poblacion B | 83 |\n'
             '| con etiqueta | **78** |\n')
    malas, _cit = rs.frases_retiradas_en(texto)
    assert malas, (
        'la regla ya no ve un 78 afirmado sobre la poblacion. Se ha '
        'estrechado de mas: cabe mas un numero retirado sin que lo vea nadie')
    assert malas[0][1] == '78'


# ============================ y las tres reglas, declaradas donde se usan
def test_las_tres_reglas_estan_declaradas():
    """Que no se limpien por Felipe: cada regla se puede borrar sin que nada
    falle hasta que aparezca el caso que la motivó."""
    fuente = io.open(rs.__file__, encoding='utf-8').read()
    assert 'SUJETO_POBLACION' in fuente, 'la lista de sujetos'
    assert 'UN_NUMERO' in fuente, 'el numero con separador de millar'
    assert 'habla_de_poblacion' in fuente, 'el sujeto fila-o-encabezado'
    i = fuente.index('SUJETO_POBLACION')
    cuerpo = fuente[i:fuente.index('def encabezado_de_tabla', i)]
    for ambigua in ('muestra', "'corte'", 'total'):
        assert ambigua not in cuerpo.replace(
            '-   corte    - "un corte de cartas"', ''), (
            'ha vuelto una palabra ambigua a la lista de sujetos: %r' % ambigua)