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
systemáticamente sesgadas: una acción posterior a un fold infla la frecuencia
de esa categoría para quien la emitió.

Conviene comprobarlas antes de mirar cualquier perfil que pase por estas
manos.

> **Aviso de cifra.** Se publicó **8**; el detector permanente da **5**.
> Mismo motivo que en `DEFECTO_45.md`: el 8 vino de un script que no se ha
> versionado.