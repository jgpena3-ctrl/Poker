# RANGO VIGENTE — las tres cifras, y por qué son tres

**Estado:** firmado. La ventana de calibración son **877** manos.
**Fecha:** 2026-10-14 (actualizado el 2026-10-25 tras la adopción y la
reparación de asientos)
**Vigila:** `motor/test_rango_fiable.py` (sin `xfail`: verifica las tres).

---

## 1. Las tres cifras, y qué es cada una

Había tres números conviviendo sin que nadie los hubiera separado. No son
versiones del mismo rango: son **tres cosas distintas**.

| cifra | qué es | quién la usa |
|---:|---|---|
| **900** | `learn.RELIABLE_HANDS`. Un corte de **líneas**, no de `hand_id` | el tope de la ventana |
| **877** | lo que produce `load_hands(reliable_only=True)`: 900 − 23 de CM-004 | **la ventana de calibración** |
| **988** | `H_0001..H_1014` de la base de 1253, el rango **auditado** | saber qué hay, no para qué se usa |

**La distinción es la que faltaba:** *rango auditado* (988, para saber qué hay)
frente a *ventana de calibración* (877, para qué se usa). Un rango auditado
puede ser más grande que la ventana sin que haya contradicción: son preguntas
distintas.

```
RELIABLE_HANDS ......... 900   corte de líneas
menos exclusiones ......  -23   las 23 de CM-004
= VENTANA DE CALIBRACIÓN 877   lo que usan las cifras
= RANGO AUDITADO ....... 988   H_0001..H_1014, para auditar
```

## 2. Quién autoriza el 877, y por qué

La ventana de calibración son 877 porque:

1. `learn.RELIABLE_HANDS = 900` limita por líneas, y 900 es el corte que el
   proyecto fijó para la primera mitad de la base.
2. `EXCLUSIONES_VENTANA_FABLE` aparta 23 manos (CM-004) por un defecto
   identificado y de efecto sin cuantificar.
3. **877 es lo que usan las cifras publicadas.** Cambiarlo obliga a
   recalcularlo todo.

> **Motivo de la exclusión, que cambió dos veces.** El motivo original —«la
> entrada `BB b` aparece después de acciones voluntarias»— ya **no se
> cumple**: la reinterpretación lo corrigió. El motivo vigente es que **no
> existe un original verificable** que permita certificar las acciones
> registradas. Ver `DECISION_CM004.md` §0-bis.

## 3. Qué comando produce el rango

```python
from motor.learn import load_hands
manos = load_hands(reliable_only=True)
len(manos)        # 877
```

- **referencia de líneas:** `RELIABLE_HANDS = 900` (`motor/learn.py`).
- **exclusiones:** `EXCLUSIONES_VENTANA_FABLE`, 23 ids (`motor/learn.py:73`).
- **comando:** `python -m motor.learn --stats` imprime el recuento.

**Y va por líneas, no por `hand_id`.** Eso importa y no es un detalle: borrar
una mano anterior al corte mete en la ventana una mano que estaba fuera. Es
lo que pasó con las 22 eliminaciones.

## 4. ⚠ Las cifras publicadas NO cuadran con la base actual

Esto se descubrió al escribir este documento, y es lo más importante que hay
aquí.

Las cifras de F7.2 se publicaron con la ventana de 877 sobre el fichero de
**1280** líneas. El fichero tiene ahora **1253** (1258 antes de la adopción y
la reparación), y 70 de las líneas de la ventana son **distintas**. La ventana
sigue teniendo 877 líneas, pero **no las mismas manos**.

> La tabla de esta sección se midió sobre las 1258. Tras adoptar la base de
> 1253 no se ha vuelto a anclar: se conserva como referencia histórica de la
> discrepancia, no como cifra vigente. El re-anclaje es la tarea 5 de
> `DOCS/HOJA_DE_RUTA_POST_ADOPCION.md`.

```
                              PUBLICADO      AHORA      DELTA
puntos de decisión                656        672        +16
denominador de política           507        519        +12
MULTIWAY (no fold)                226        238        +12
MULTIWAY %                      44,6 %      45,9 %     +1,3
cota de desconocidos              255        267        +12
```

**El porcentaje se mueve.** No es un redondeo: es otra muestra.

Esto no es culpa del cambio manual, es su **consecuencia**, y es exactamente
lo que pasa cuando se edita el fichero del que salen las cifras sin
recalcular. Lo que estaba mal no es el número: es que el número se publicó
sobre una base que ya no existe.

### La tabla cruzada, sobre la ventana vigente

| clase | fold | no fold | total | **de política** |
|---|---:|---:|---:|---:|
| HU | 39 | **281** | 320 | **281** |
| MULTIWAY | 36 | **238** | 274 | **238** |
| DESCONOCIDO | 9 | 43 | 52 | 0 |
| sin ningún rival al que responder | 9 | 17 | 26 | 0 |
| **TOTAL** | **93** | **579** | **672** | **519** |

```
519 + 43 + 17 = 579 no-fold  ->  + 93 folds  =  672 puntos
519 = 281 HU + 238 MULTIWAY
cota = 238 + 29 (techo sin evidencia) = 267
```

## 5. El rango auditado (988) no es la ventana

`H_0001..H_1014` son **988** manos en la base de 1253 (991 antes de retirar
`H_0028`, `H_0072` y `H_0146`), y son las que se han auditado en
`HALLZGOS_H0001_H1014.md`. No se usan para calibrar.

Que el rango auditado sea mayor que la ventana **no es una contradicción**:
una es para saber qué hay, la otra para qué se usa. Lo que sí sería una
contradicción es que las cifras de la ventana se presentaran como si
describieran el rango auditado entero.

## 6. Si hay que cambiar algo

- **Cambiar la ventana** (877 → otro número): cambiar `RELIABLE_HANDS`, o
  `EXCLUSIONES_VENTANA_FABLE`, **y recalcular todas las cifras de F7.2 y
  regenerar los derivados**. No es un cambio de una línea.
- **Ampliar el rango auditado**: cambiar `RANGO_AUDITADO_HASTA` y volver a
  correr `tools/auditar_rango.py`. No toca las cifras.

Las dos constantes están en `motor/learn.py`, juntas, para que no se puedan
confundir otra vez.