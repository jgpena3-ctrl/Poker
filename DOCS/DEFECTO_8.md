# DEFECTO 8 — alguien actúa después de haber foldeado

**Estado:** medido, sin corregir. **Rango H_0001..H_1014: 5.**
**Instrumento:** `tools/auditar_rango.py`, clase `ACCION_DESPUES_FOLD`.
**Consecuencia para Fase D:** **no bloquea.**

---

## 1. Qué es

Una posición emite una acción **después** de haber emitido un `f`. En el
preflop una sola vez: es imposible seguir en la mano después de foldear.

La comprobación es **solo preflop**, que es el alcance con el que se
publicó la cifra. Medida en todas las calles daría un número distinto, y no
sería la misma métrica.

## 2. Identificadores

```
H_0054, H_0103, H_0180, H_0236, H_0330
```

`H_0103` tiene **tres** ocurrencias en la misma mano, lo que apunta a que no
es un caso aislado sino una mano especialmente mal grabada.

## 3. Veredicto: **grabación**

No es poker: un jugador que foldea no vuelve a actuar en la misma mano. Es
una contradicción interna del registro.

La causa más probable es el recorder escribiendo la acción de una posición
que en realidad era otra, o reescribiendo una acción ya cerrada.

## 4. Cómo se cierra

Son 5. Un script que borre la acción contradictoria es correcto en poker, pero
**borra dato grabado**, y eso es una decisión, no un bugfix. La alternativa es
declararlas y excluirlas de la ventana, como se hizo con las 23 de CM-004.

Lo que **no** procede es corregirlas de una en una: en el bloque anterior se
corrigió `H_0263` a mano, que estaba en esta misma lista, y hubo que
revertirlo porque el patrón salía 8 veces y se tocaba 1.

## 5. Consecuencia para Fase D

**No bloquea.** 5 de 991. Pero son 5 manos cuyas frecuencias están
sistemáticamente sesgadas: una acción posterior a un fold infla la frecuencia
de esa categoría para quien la emitió.

Conviene comprobarlas antes de mirar cualquier perfil que pase por estas
manos.

## 6. Decisión sobre la cifra: opción A

> **La cifra publicada de 8 no tiene código que la produzca, y por tanto no
> es un dato. Se acepta como cifra histórica sin instrumento y la que vale es
> la del detector permanente.**

Se publicó 8 desde un script de un solo uso que no se versionó. El detector
permanente da **5**, y la diferencia viene de que aquel script miraba todas
las calles y este **solo preflop**, que es el alcance con el que se describes
la clase.

Que el alcance este declarado es parte del contrato: medirlo en todas las
calles daría otro número, y no sería la misma métrica con otro nombre.

`tools/auditar_rango.py --validar` lo dice explícitamente: esta cifra **no
se reproduce** y por qué. Un instrumento que declara que su número no tiene
origen es más útil que uno que lo publica sin avisar.

> No se ha intentado recuperar el criterio original. Un criterio que solo
> existe en el recuerdo de una conversación no es un criterio.