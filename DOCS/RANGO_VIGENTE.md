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
**1280** líneas. El fichero tiene ahora **1253**. La ventana sigue teniendo
877 líneas, pero no las mismas manos; por eso la tabla cruzada se re-ancló
aquí contra la base canónica actual (SHA
`c3172a147423d12a652767586dd76c36f24347c9dd503959dbea019e64944a09`).

### Tabla cruzada re-anclada, sobre la ventana vigente (2026-10-26)

| clase | fold | no fold | total | **de política** |
|---|---:|---:|---:|---:|
| HU | 43 | **301** | 344 | **301** |
| MULTIWAY | 32 | **211** | 243 | **211** |
| DESCONOCIDO | 9 | 42 | 51 | 0 |
| sin ningún rival al que responder | 10 | 16 | 26 | 0 |
| **TOTAL** | **94** | **570** | **664** | **512** |

```
512 = 301 HU + 211 MULTIWAY
570 no-fold = 512 + 42 + 16  ->  + 94 folds  =  664 puntos
cota = 211 + 24 (techo sin evidencia) = 235
MULTIWAY % = 211 / 512 = 41,2 %
```

**Referencia histórica (base anterior, 1258 líneas):** 672 puntos · 519 de
política · 238 MULTIWAY · 45,9 % · cota 267. La diferencia es otra muestra,
no un redondeo: el fichero cambió 27 manos respecto a la ventana.

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