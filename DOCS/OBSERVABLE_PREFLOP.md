# LA EQUITY PREFLOP OBSERVABLE: que es, quien la valida, y que se sabe

> Y este documento es el entregable del frente de la vía preflop, y su
> criterio es el del proyecto: **separar lo MEDIDO de lo que todavía es una
> HIPÓTESIS**. Y eso es más importante de lo que parece, porque una
> hipótesis escrita como un resultado acaba citándose como un resultado.

## 1. QUÉ SIGNIFICA «OBSERVABLE»

Y la definición, que es la del contrato (`CONTRATO_PREFLOP.md`):

| | equity **RETROSPECTIVA** | equity **OBSERVABLE** |
|---|---|---|
| qué usa del rival | sus **cartas reales** | su **RANGO**, y nada más |
| qué usa del board | el board que se repartió | ninguno: es preflop |
| qué responde | «¿cómo habría ido esta mano?» | «¿qué se podía saber al decidir?» |
| en la base | es lo que mide `tools/equity_de_mano.py` | es lo que mide `equity_preflop_rango` |

> Y la diferencia no es de precisión: es de **pregunta**. Y una medición
> retrospectiva no es una medición mala: es la medición de OTRA cosa, y por
> eso no se puede usar para juzgar la decisión.

## 2. QUIÉN VALIDA LA PROPIEDAD, Y SIN SESGO

Y la población que puede validarla son las manos de la **partición de
validación** —MEDIDO, 47 manos—, y el sesgo que hay que evitar es el
**inverso de la fuga**: no se puede usar una mano para validar el estimador
observable **si el estimador se ha construido con las cartas de esa mano**.

Y eso es exactamente lo que el test de fuga comprueba, y es lo que el
contrato pide:

> «Si el rango se construye con las cartas del rival, esto falla. La tentación
> va a ser pasarle la mano real porque es más exacto. Este test es para que
> eso no pase por sin que se note: es una fuga de información y no se nota en
> el número, solo en que el número es demasiado bueno.»

Y el test, `tools/test_observable_preflop.py`, monta un rango con masa en **un
solo** combo e intercepta la evaluación por combo: si el motor usara las
cartas reales del rival, se mirarían OTROS combos, y el test falla.

## 3. LO QUE ESTÁ MEDIDO, Y LO QUE NO

### MEDIDO

| | |
|---|---|
| el camino observable **existe** | `motor/hand_evaluator.py::equity_preflop_rango`, y `situation.equity_vs_range` delega en él cuando el board está vacío |
| **no usa las cartas del rival** | el test de fuga, que es el del contrato, y que ahora corre |
| es **determinista** | el mismo `seed` da los mismos combos, en el mismo orden |
| su **varianza** | MEDIDO en el contrato: con 40 combos, **sigma ~ 0,0099**, y mueve el AUC **0,0004** |
| la herramienta que mide el AUC usa la vía **retrospectiva** | `tools/equity_de_mano.py`, y lo **declara**: `'observable': False`, con el motivo |

### HIPÓTESIS, Y NO MEDIDO

> **Que la equity preflop observable ORDENE las manos.** Y no está medido, y
> no se puede medir todavía, y el motivo es de coste y no de Instrumento:
> cada combo enumera C(48,5) = 1 712 304 sorteos, de modo que una equity
> con 40 combos es de minutos, y la partida de validación son 47 manos.

Y la consecuencia, que es la que hay que tener presente: **el AUC publicado
no es el AUC de la equity observable**, y no lo va a ser sin una
recalibración, que es post-adopción.

## 4. TRES HALLAZGOS

**H4 — EL COMENTARIO DE LA HERRAMIENTA ESTÁ VIEJO.** Y textual: en
`tools/equity_de_mano.py` dice «el motor no tiene ningún camino de equity
preflop», y desde `equity_preflop_rango` **sí lo tiene**, y `situation`
delega en él. Y el comentario no se arregla en este bloque, porque el
comentario cuenta una decisión —«mientras tanto, lo único que hay es la
enumeración contra las cartas reales»— y esa decisión sigue vigente: la
herramienta sigue midiendo la equity retrospectiva ✓.

**H5 — EL CAMINO OBSERVABLE ES PRACTICABLE, PERO HAY QUE BAJAR `n_combos`.** Y
`equity_vs_range` lo expone ✓, de modo que se puede pedir con 2 combos y no
con 200. Y a los parámetros por defecto son 200 combos, de modo que el
camino es lento por defecto, y eso es una decisión —la del contrato— y no un
defecto.

**H6 — CAMBIAR LA HERRAMIENTA PARA USAR LA VÍA OBSERVABLE MOVERÍA EL AUC
PUBLICADO.** Y eso **no se hace en este bloque**, porque un cambio que mueve
una cifra publicada es una **recalibración**, y las recalibraciones van
después de la adopción. Y la cifra que se movería es el AUC, que es la
métrica del proyecto.

## 5. EL EXPERIMENTO, PREPARADO

Y lo que hay, y es lo que R2 pide: **el experimento está escrito y se puede
ejecutar**, y su resultado no se anticipa.

```
python tools/auditar_equity_observable.py --piloto      # una mano, dos combos
python tools/auditar_equity_observable.py                # las 47, 40 combos
```

Y lo que hace, en orden:

1. **la población** — las manos de la **partición versionada**
   (`calibrar.es_validacion`), que es la misma que usa el AUC publicado, de
   modo que la comparación sea legítima;
2. **el rango** — por `rango_del_rival`, el mismo camino que la herramienta
   publicada, de modo que el estimador no se haya construido con las cartas
   de la mano que valida;
3. **la equity** — con `equity_preflop_rango`, que **no ve las cartas del
   rival**: la observable;
4. **la etiqueta** — `1.0` si ganó, `0.0` si perdió, y **los empates no
   entran y se cuentan**, que es la regla del reparto del `CONTRATO_L_SEC.md`;
5. **el AUC y su intervalo** — con el mismo bootstrap que el AUC publicado.

Y el **coste se imprime antes de empezar**, que es el dato que hace que esto
sea de horas: MEDIDO, una mano con dos combos tarda **54 s**, de modo que las
47 con 40 combos son **1880 enumeraciones** de C(48,5).

> Y el piloto, ejecutado a mano: **una mano medida**, y el script dijo que no
> se puede calcular el AUC porque **no hay las dos clases** ✓. Y eso es lo
> que tiene que decir, y no un 0.5 inventado.

Y lo que el experimento **no** hace, y es lo importante: **no toca la
herramienta que genera el AUC publicado**, y no lo toca porque usarla
movería el AUC. Y hay un test que lo comprueba por el árbol: la rama preflop
de `equity_contra` sigue usando la enumeración contra la mano real.

## 6. Y LO QUE NO SE HACE

| | |
|---|---|
| medir el AUC observable | es una cifra nueva, y su instrumento es caro; y no es una recalibración *sino* una medición nueva, que se hará con su propio nombre |
| cambiar `tools/equity_de_mano.py` para usar la vía observable | movería el AUC publicado: es post-adopción |
| tocar la firma de `equity_preflop_rango` | el contrato la declara «sin tocar», y ahora hay un test que lo vigila |
| ampliar la cobertura preflop | el `L_SEC` lo prohíbe hasta que esté firmado, y sigue sin estarlo |
