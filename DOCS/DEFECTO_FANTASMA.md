# DEFECTO_FANTASMA — acciones de posiciones que no estaban en la mesa

**Estado:** medido, sin corregir. **Rango H_0001..H_1014: 16.**
**Instrumento:** `tools/auditar_rango.py`, clase `ACCION_FANTASMA`.
**Consecuencia para Fase D:** **no bloquea, pero impide confiar en la identidad
de quien actuó.**

---

## 1. Qué es

Una posición emite acciones y **no está** en `players[]` entre los activos.
Casi siempre es una posición que el recorder dejó vacía (`pos: ""`) y que sin
embargo emitió acción: una sexta mesa que el recorder leyó como si no lo fuera.

## 2. Identificadores (rango declarado fiable)

```
H_0016, H_0022, H_0061, H_0143, H_0198, H_0209, H_0240, H_0519, H_0564, H_0718
H_0748, H_0822, H_0827, H_0846, H_0968, H_0978
```

Dos de ellas se solapan con otras clases, y eso es lo que las hace más
interesantes:

- **`H_0748`** también está en `POSICION_DUPLICADA` y en `WINNER_FOLDEO`.
  Tres contradicciones en la misma mano.
- **`H_0143`** es una de las 23 de CM-004, y una de las que la corrección
  manual del 14/10 volvió a tocar.

## 3. Veredicto: **grabación**, y del recorder, no del poker

No hay lectura de poker en la que alguien actúe sin estar sentado. Es el
recorder escribiendo acciones de una plaza que no esta ocupada, o de una
que no se pudo leer.

La causa más probable es la que ya está documentada en otra parte del
proyecto: **no hay ninguna marca de hero, y el recorder rellena `players[]` en
el orden en que ve las plazas**, con huecos. Una plaza que no se vio en la
captura queda con `pos: ""` y con `active: false`, pero su acción sí se
registró.

## 4. Por qué no se corrige a mano

Dos razones, y la segunda es la importante:

1. **Son 16.** Lo de siempre: un patrón de N casos se mide y se corrige con
   un script sobre los N, o no se corrige.
2. **Arreglarlo exige saber qué posición era.** El dato no lo dice: `pos` está
   vacío. Corregirlo sería **inventar la identidad de quien jugó la mano**, que
   es el mismo defecto que hizo inútil la corrección de las 6
   reconstrucciones.

Lo que sí se puede hacer, y es lo correcto, es **declararlas**: 16 manos en
las que hay acciones sin dueño identificable. Se excluyen de la calibración
por esa razón, que sí es verificable, y el patrón se arregla en el recorder
hacia adelante.

## 5. Consecuencia para Fase D

**No bloquea la calibración de frecuencias por acción y posición**, porque el
motor ya agrupa por lo que hay en `players[]` y una plaza fantasma no entra en
ningún perfil.

**Sí bloquea una cosa concreta**: cualquier análisis que necesite saber
**quién** actuó. Si la pregunta es «qué hace el UTG», las manos fantasma no
contaminan. Si es «cuántas manos jugó este jugador», sí: hay 16 manos con
acciones que no se pueden atribuir.

> `H_0748` merece mirado aparte: está en tres clases de golpe. O se revisa a
> mano, o se declara que esa mano no sirve para nada.

## 6. Relación con los otros defectos

Comparte causa con `SIN_ALLIN`: los dos son cosas que **el recorder antiguo no
escribía**, y los dos son bloques de manos del principio de la base. `H_0016`
y `H_0022` están entre las primeras 73, que son las que no tienen `allin`.