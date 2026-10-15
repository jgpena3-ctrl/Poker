# DEFECTO 45 — una subida que no supera la ciega

**Estado:** medido, sin corregir. **Rango H_0001..H_1014: 36.**
**Instrumento:** `tools/auditar_rango.py`, clase `IMPORTE_SUBIDA`.
**Consecuencia para Fase D:** **no bloquea, pero contamina la lectura del BB.**

---

## 1. Qué es

Una entrada con `action: 'r'` cuyo `amount` **no supera** la apuesta viva
anterior. En poker una subida sube: no puede repetir el nivel.

Las dos formas que aparecen, y que se distinguen por el importe:

| forma | importe | nº |
|---|---|---:|
| subir a **exactamente** la ciega nominal (1.0) | `r 1.0` | 31 |
| subir **por debajo** de la ciega nominal | `r 0.5` | 5 |

`r 1.0` como primera acción voluntaria no es una apertura: es un limp
etiquetado como subida, o un error de importe. `r 0.5` es imposible en
cualquier forma: no se puede subir a menos que la ciega.

## 2. Identificadores (rango declarado fiable)

```
H_0044, H_0049, H_0076, H_0097, H_0104, H_0105, H_0107, H_0108, H_0117, H_0131
H_0139, H_0147, H_0148, H_0151, H_0159, H_0161, H_0163, H_0164, H_0167, H_0168
H_0169, H_0170, H_0171, H_0173, H_0175, H_0177, H_0185, H_0197, H_0207, H_0214
H_0215, H_0249, H_0327, H_0335, H_0369, H_0736
```

## 3. Veredicto: **grabación**, y de una sola clase

No es un defecto de poker: nadie sube por debajo de la ciega. Es un
**error de etiquetado o de importe en el recorder**: la acción ocurrió y se
grabó mal, o no ocurrió como se grabó.

La regla que se ensayó en el bloque anterior —«una subida a importe ≤ la
ciega no es una apertura, es una llamada»— **se descartó**, y con razón:se aplicó a 3 manos y dejó 33 sin tocar. Un patrón que sale 36 veces no lo
arregla nadie a mano en tres.

## 4. Cómo se cierra

Con un script, sobre **las 36**, y declarando cuál de las dos lecturas se
toma. Hay una decisión de fondo aquí, y es de quien mantiene la base:

- **`r 1.0` → `c 1.0`** (limp): conserva la acción y corrige la etiqueta.
- **dejarlo como está**: la acción era una subida de 1.0 sobre un bote de
  1.0, que en algunas variantes de stakes es legal.

La segunda es defendible para `r 1.0` y **no** para `r 0.5`. Por eso los 5
casos de `r 0.5` son un subconjunto con decisión propia.

## 5. Consecuencia para Fase D

**No bloquea el arranque, pero hay que decirlo antes de mirar cifras del BB.**
Las subidas imposibles son del BB o de la última posición, y si el BB tiene
una frecuencia de subida anómala, parte de eso puede venir de aquí.

Lo que **no** se debe hacer es usar esto para «limpiar» las 36 antes de
medir: sería volver a parchear a mano, la tercera vez, y esta sobre una clase
entera.

## 6. Decisión sobre la cifra: opción A

> **La cifra publicada de 45 no tiene código que la produzca, y por tanto no
> es un dato. Se acepta como cifra histórica sin instrumento y la que vale es
> la del detector permanente.**

Se publicó 45 desde un script de un solo uso que no se versionó. El detector
permanente da una cifra distinta, y además la lógica era incorrecta: comparaba
cada `r` contra `learn.BB`, la **ciega nominal**, en vez de contra la
**apuesta viva anterior**. Con eso, una subida que superaba la ciega pero no la
apuesta anterior pasaba desapercibida.

Corregida la lógica, el recuento cambia otra vez. `tools/auditar_rango.py`
es el que vale, y se autocomprueba:

```
python tools/auditar_rango.py --validar
```

- **Dos cifras reproducen**: el patrón del BB (652) y su ausencia real (23).
- **Dos no reproducen**: esta y la de `DEFECTO_8.md`. No se esconden: el
  script lo dice y explica por qué.

**La cifra vigente sale del script, no de este documento.** Si cambia el
script, cambia el número, y `--validar` lo contrasta contra lo que se publicó
para que la discrepancia se vea.

> No se ha intentado recuperar el criterio original con el que se midieron
> las 45. Un criterio que solo existe en el recuerdo de una conversación no es
> un criterio: es una excusa para no decidir.