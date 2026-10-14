# EXCLUSIÓN CM-004 de la ventana de calibración

**Estado:** aplicada. **Reversible** (es una lista, no una modificación
del dato).
**Decisión:** revision_1 Tarea 2 y revision_2 punto 4. La exclusión **no**
depende de decidir si se regraba o se migra la base.
**Código:** `motor/learn.py` → `EXCLUSIONES_VENTANA_FABLE`, `manos_excluidas()`,
`motivos_exclusion()`.
**Test:** `motor/test_exclusion_cm004.py` (7 casos).

---

## 1. Qué se excluye y por qué

| | |
|---|---|
| manos | **23** |
| clave | `CM-004` |
| motivo | la entrada `BB: 'b'` —la ciega— aparece **después** de acciones voluntarias |
| consecuencia | `learn._es_ciega_bb` exige `not voluntary_before`, así que no la reconoce como ciega y el motor la lee como una subida que puede no haber ocurrido |
| naturaleza | defecto de **orden**, no de valor |

Las 23:

```
H_0031 H_0037 H_0039 H_0051 H_0067 H_0078 H_0104 H_0107 H_0109
H_0127 H_0143 H_0147 H_0161 H_0170 H_0183 H_0210 H_0215 H_0248
H_0262 H_0263 H_0279 H_0294 H_0722
```

## 2. Por qué se excluyen sin esperar a la decisión de regrabar

El defecto está identificado y su efecto **no está cuantificado**. CM-003
hace al BB más pasivo y CM-004 más agresivo, y se anulan en *dirección*
pero no en *magnitud*. Mantenerlas dentro de la ventana sería usar unas
cifras que el propio proyecto ya sabe que no son fiables.

Excluirlas no cierra la puerta a regrabar: es quitar una lista.

## 3. Dónde queda el corte

```python
RELIABLE_HANDS = 900          # lineas de corte, no manos

load_hands(reliable_only=True)
    # corte por lineas: las primeras 900
    # menos las manos de EXCLUSIONES_VENTANA_FABLE
    # -> 877
```

Comprobado: las 23 caen **dentro** de las primeras 900 líneas. Ninguna
queda fuera, así que la resta es entera.

| | |
|---|---|
| `load_hands(reliable_only=True)` | **877** |
| `load_hands(reliable_only=False)` | 1280 |
| `load_hands(max_hands=900)` | 900 |

**Las manos no se borran.** Siguen en `data/hands_db.jsonl` y en
`load_hands(reliable_only=False)`. Se excluyen de la calibración, no de la
evidencia. Hay un test que lo comprueba (`test_las_23_no_se_borran_del_fichero`).

### El orden de las dos operaciones importa

La exclusión se aplica **después** del corte por líneas. Con
`max_hands=50` el resultado es **47**, no 50: dentro de las primeras 50
líneas caben 3 de las 23. Eso no es un bug, es lo que significa "estas 50
líneas, menos las que no son fiables". Está fijado con un test que cuenta
las tres (`H_0031`, `H_0037`, `H_0039`).

## 4. Qué se rompió al hacerlo, y cómo se arregló

La ventana cambió de 900 a 877 y eso afecta a cuatro cosas. Ninguna se
arregló volviendo a poner 900:

### 4.1 `motor/_procedencia.py` — el sello de la ventana

`hands_window` se deduce comparando `hands_input` contra `RELIABLE_HANDS`.
Con 877 manos, **la propia ventana fiable se etiquetaba como `custom`**.

Es exactamente el fallo que ese módulo existe para evitar: un consumidor
habría leído "esto no viene de la ventana fiable" sobre datos que sí
vienen de ella. Ahora compara contra
`RELIABLE_HANDS - len(manos_excluidas())`, con la limitación documentada.

### 4.2 `test_squeeze_regresion_sobre_las_900` — 26 → 20

La regresión de squeeze se medía sobre la ventana. Al excluir 23 manos, la
medición baja de 26 a 20: **6 de los squeeze estaban entre las excluidas**.

La baseline se actualiza a 20 y el docstring cuenta las dos, para que la
causa del cambio quede escrita y no se vuelva a perder.

### 4.3 Dos tests de `hands_input == 900`

Reescritos como `RELIABLE_HANDS - len(manos_excluidas())`. Un `900`
mágico vuelve a romperse en cuanto la ventana cambie otra vez.

### 4.4 Las cifras de F7.2

El denominador se recalcula sobre 877 manos. Ver `CONTRATO_F72A.md` §5.

## 5. Efecto sobre las cifras (antes → después)

Mismo criterio que `CONTRATO_F72A.md` §5.4: el denominador **excluye los
folds** del hero, que deciden pero no consultan equity.

| | 900 manos | 877 manos |
|---|---|---|
| puntos de decisión (con folds) | 670 | **656** |
| HU (no fold) | 286 | **281** |
| MULTIWAY (no fold) | 230 | **226** |
| **denominador de política** | 516 | **507** |
| **MULTIWAY %** | 44,6 % | **44,6 %** |
| cota | 260 | **255** |

El efecto es pequeño y va en la dirección esperada: quitar manos dudosas
de la muestra reduce un poco el numerador y el denominador por igual.

> La tabla de este documento se corrigió el 2026-10-14. Publicaba el
> denominador **con folds dentro** (588 → 578), que era como se medía antes
> de que la métrica se corrigiera. Con el criterio vigente, el porcentaje
> sale **44,6 % en las dos ventanas**: quitar 23 manos no lo mueve.

## 6. Cómo se revierte

Borrar la entrada de `EXCLUSIONES_VENTANA_FABLE` con clave `CM-004`. La
ventana vuelve a 900 y los tests de exclusión hay que borrarlos con ellos.

> **Actualizado 2026-10-14.** Esta sección decía *«no se tocó el fichero de
> datos»*. Ya no es cierto: las 23 se reescribieron a mano después. Ver
> `CM004_REINTERPRETACION.md`. El motivo de la exclusión cambió con ello y
> `DECISION_CM004.md` §0 lo explica.