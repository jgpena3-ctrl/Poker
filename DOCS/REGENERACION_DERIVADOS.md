# Regeneración de los derivados

**Estado:** hecho.
**Fecha:** 2026-10-14
**Comando:** `python tools/reconstruir_derivados.py {baseline,regen,comparar}`
**Motivo:** los derivados se construyeron el 13/10 a las 19:57, en `e314f74`,
**antes** de que existiera la ventana de 877 y **antes** de la reinterpretación
de CM-004. Ha habido dos verdades en el repo: el `.jsonl` corregido y los
`.json` sin regenerar.

---

## 1. Qué se regeneró

| fichero | ventana | qué lo escribe |
|---|---|---|
| `preflop_stats.json` | 877 | `python -m motor.learn --json` |
| `player_stats.json` | 877 | `python -m motor.stats --json` |
| `profiles.json` | 877 | `python -m motor.profile --json` |
| `profile_ranges.json` | 877 | `python -m motor.player_ranges --json` |
| `postflop_ranges.json` | 877 | `python -m motor.postflop_ranges --json` |
| `observations.json` | 877 | `python -m motor.observations --json` |
| `behavior.json` | 877 | `python -m motor.behavior --json` |

**Ventana: 877 manos** — 900 de `RELIABLE_HANDS` menos las 23 de CM-004. Es
la primera vez que los derivados se construyen sobre la ventana fiable y no
sobre las 900. Antes de esta regeneración, ninguno de los siete lo estaba.

---

## 2. Qué cambió

### 2.1 Lo que no cambió, y es lo importante

```
manos                877 -> 877     eventos          4533 -> 4533
jugadores            154 -> 154     eventos_con_cartas 1127 -> 1127

bb_check   224 -> 224      limp      360 -> 360     open      433 -> 433
rol        167 -> 167      fold     1495 -> 1495     squeeze    20 -> 20
3bet        80 -> 80        call_limp 156 -> 156     4bet        2 -> 2
call_open  406 -> 406      call_3bet  14 -> 14       call_3bet  14 -> 14
fold_vs_open 1064 -> 1064  fold_vs_3bet 112 -> 112

no_raise    2835 -> 2835    facing_open 1570 -> 1570    facing_3bet 128 -> 128
```

**Ni una sola frecuencia preflop se movió.** Es el resultado que cabía
esperar, y la comprobación que hacía falta:

- Las 23 de CM-004 están **excluidas** de la ventana, así que su
  reinterpretación no entra en ninguna cuenta.
- `H_0350` sí está dentro, pero el cambio es de un centinela de carta: dos
  `cards="-"` que pasan a `""`. Las cartas siguen sin saberse; lo que cambia
  es que ya no hay un guion donde el motor esperaba un código de carta.

### 2.2 Lo que sí cambió

| | antes | después | |
|---|---:|---:|---|
| `postflop_ranges.cnt` | 181 claves | 180 | una clave menos |
| `observations` | 9347 | 9097 | −250 |
| `profiles.json`: etiquetas | — | — | 3 de 154 cambian |
| `hands_input` / `hands_used` | 900 / 887 | 877 / 864 | la ventana |

**`observations`: −250.** Las 23 manos excluidas aportaban unas 11
observaciones cada una. La primera línea que el diff borra es `H_0031`, la
primera de las 23, que es exactamente donde tiene que empezar.

**`postflop_ranges`: −1 clave.** Es el efecto de `H_0350`. Antes, con
`cards="-"` como centinela, el motor invocaba al rango rival con un bloqueador
que no era una carta; ahora la ausencia se declara y el contador fantasma
desaparece.

### 2.3 Las tres etiquetas de perfil que cambiaron

Esto merece su propia sección, porque **no** es ruido de formato.

La etiqueta PEZ/TIBURON **no es un agrupamiento**: es un umbral
(`simple_label`, `motor/profile.py:95`):

```
stack medio < 50 BB                    -> PEZ
vpip > 0,32 y pfr < 0,10               -> PEZ
resto                                 -> TIBURON
```

Tres jugadores cruzaron un umbral al recalcular:

| jugador | | antes | después | causa |
|---|---|---:|---:|---|
| `Juanmabm` | etiqueta | PEZ | TIBURON | su vpip pasó de >0,32 a **0,3137** |
| | vpip | >0,32 | 0,3137 | a **0,006** del umbral |
| | n | 55 | 51 | |
| `Valentina22` | etiqueta | TIBURON | PEZ | stack medio 50,3 → **48,8** |
| | stack medio | 50,3 | 48,8 | a **1,2** del umbral de 50 |
| | n | 3 | **2** | |
| `P5` | etiqueta | TIBURON | PEZ | vpip 1,0 / pfr 0,0 cumple la regla PEZ |
| | n | 3 | **2** | etiqueta calculada sobre **dos manos** |

**Qué significa.** Dos de los tres tienen **n = 2**: su etiqueta sale de dos
manos y no dice nada sobre cómo juegan. El tercero, con 51 manos, está a
0,006 del umbral: una mano lo mueve.

No es un fallo de la regeneración. Es una propiedad de una regla de umbral, y
deja una conclusión que conviene tener escrita:

> **La etiqueta PEZ/TIBURON no es una afirmación estable sobre el estilo de
> un jugador.** Es un umbral, y cerca del umbral —o con pocas manos— la
> etiqueta es ruido. Para los jugadores con `reliability == 'probable'`
> (`n < 40`, que ya está en el propio `profiles.json`) **no debe leerse como
> un hecho sobre cómo juegan.**

No se corrige aquí porque no es un bug: es lo que dice la regla. Lo que faltaba
era decirlo.

---

## 3. Verificación posterior

```
python tools/verificar_cm004.py     # invariante CM-004: 0 de 1280
python tools/reconstruir_derivados.py comparar
python -m pytest motor recorder tests -q
```

Y lo que pedía `revision_1` Tarea 4: **`metrica_politica()` da idéntico.**

```
puntos 656   denominador 507   MULTIWAY 226   44,6 %   cota 255
ventana fiable: 877
```

Ninguna cifra publicada se mueve. Las que se publicaron esta mañana siguen
válidas.

---

## 4. Reversión

`data/*.json` está versionado. La baseline y las métricas posteriores están
en `data/_snapshot_pre_rebuild_f5f44ca/`, con sus hashes:

```
python tools/reconstruir_derivados.py backup     # antes de la siguiente
python tools/reconstruir_derivados.py regen
python tools/reconstruir_derivados.py comparar
```

Los hashes de `hands_db.jsonl` están en
[`CM004_REINTERPRETACION.md`](CM004_REINTERPRETACION.md) §7 y en
[`RECONSTRUCCIONES_CM004.md`](RECONSTRUCCIONES_CM004.md) §4.