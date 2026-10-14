# CORRELACIÓN DE CAPTURAS — CM-004

**Resultado: 0 de 23 manos tienen un original localizable por los métodos
disponibles.**
**Script:** `python tools/correlacionar_capturas.py`
**Salida cruda:** `DOCS/CORRELACION_CAPTURAS.txt`
**Consecuencia:** CM-004 queda como **sin original verificable**. La
decisión de regrabar se convierte, según revision_2, en **aceptar la
pérdida o conseguir otra fuente legítima** — no en inventar una reparación.

---

## 1. Lo primero: ¿hay timestamp?

Sí, y por tanto el método de revision_1 es aplicable.

| | |
|---|---|
| manos con `date` parseable | **1280 de 1280** |
| rango | 2026-07-27 → 2026-09-18 |

No hay que parar aquí por falta de timestamp. El problema es otro.

## 2. Las capturas

| | |
|---|---|
| PNG totales | **174** |
| en `capturas/` | 127 |
| en `capturas/juego/` | 47 |
| rango de `mtime` | 2026-06-04 → 2026-09-14 |

Las 23 manos de CM-004 van del **2026-07-28** al **2026-09-15**, dentro del
rango. Hay capturas que podrían ser de ellas.

## 3. Método 1 — fecha ± tolerancia: **no sirve**

| tolerancia | manos con ≥1 captura candidata |
|---|---|
| ± 1 h | 18 de 23 |
| ± 6 h | 20 de 23 |
| ± 24 h | 22 de 23 |

Un 22 de 23 parece un éxito. **No lo es, y por eso el script lo dice antes
de que nadie lo cite.**

Con ±24 h salen hasta **23 capturas** alrededor de una sola mano. Y hay
**7,6 capturas por mano**. Eso no es correlación: es que el poker se juega
en sesiones de horas, así que una ventana de 24 h alrededor de cualquier
mano encuentra prácticamente cualquier captura de esa sesión.

Un instrumento que dice "22 de 23" cuando la verdad es "no lo sé" es peor
que uno que dice "no lo sé". Por eso el script imprime el sanity check al
lado del número.

## 4. Método 2 — el número del nombre de fichero: **no sirve**

Los PNG se llaman `Captura de pantalla (NNN).png`. Si `NNN` fuera el
`hand_id`, la correlación sería directa y no habría nada que discutir. Se
comprueba contra la fecha de `H_00NN`:

| | |
|---|---|
| capturas de la raíz con número | 88, rango 2..191 |
| huecos en ese rango | **102** |
| coinciden con `H_00N` (<24 h) | 19 de 86 |
| **delta mediano** | **261 h** |
| min / max | 0 h / 1290 h |

Con 102 huecos en el rango, los números **no son un índice correlativo de
manos**. Y un delta mediano de 261 h —más de diez días— dice que el número
no es el `hand_id`. El 19 de 86 que "coincide" es lo que sale por azar al
comparar dos series que se solapan en el tiempo.

## 5. Veredicto

```
Correlacionables por los métodos disponibles: 0 de 23
```

Los dos métodos baratos se descartan por medición, no por opinión. No se ha
aplicado ninguno de los dos que sería concluyente:

## 6. El método que queda, y por qué no se ha hecho

**Leer la mesa del pantallazo** — OCR o visión — y casar las comunitarias y
los stacks con la mano. El proyecto tiene `tools/lector_cartas.py` y
`tools/lector_cartas_v2.py`, así que es viable.

No se ha hecho porque revision_1 pidió explícitamente no hacerlo hoy, y
porque es un trabajo de horas con resultado incierto: de 174 PNG habría que
descartar 173 para poder confirmar uno.

**Es la vía legítima si se quiere un original.** Si algún día se decide
invertir en ello, es el único camino que queda.

## 7. Qué significa para CM-004

Según revision_2, y ahora con el dato en la mesa:

> "Si las capturas no se pueden correlacionar con esas manos, CM-004 debe
> quedar documentada como sin original verificable, y la decisión de
> regrabar se convierte en aceptar la pérdida o conseguir otra fuente
> legítima, no en inventar una reparación."

Es exactamente el caso. **No regrabar.** Quedan dos caminos si algún día se
quiere recuperar la evidencia:

1. OCR sobre `capturas/` (trabajo acotado, resultado incierto).
2. Que exista una sesión grabada en otro soporte — vídeo, otro
   ordenador, una copia de las capturas de otra máquina.

Mientras tanto, las 23 manos **se conservan intactas y excluidas de la
calibración** (`EXCLUSION_CM004.md`). No se reparan, no se borran, no se
tocan.