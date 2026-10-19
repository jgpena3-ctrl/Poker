# LA FRONTERA DEL GRABADOR

**Qué separa dos generaciones de captura dentro de la misma base.**

Base: `trabajo/hands_db_edicion.jsonl` · 1258 manos
Original: `data/hands_db.jsonl` · SHA `35727961646dfaba…` · **sin tocar**

---

## 1. El criterio

Una mano cuyo **`streets.preflop.actions[0]`** es

```json
{"pos": "BB", "action": "b", "amount": 1.0}
```

fue grabada por un grabador que **ya emitía la ciega del BB** como primera
acción de la calle.

Una que **no** lo tiene fue grabada por uno que no la emitía, o por una captura
en la que la ciega no se vio.

---

## 2. Dónde cae

| | fecha |
|---|---|
| **última mano SIN `b:1` primero** | `2026-09-10T11:19:52` |
| **primera mano CON `b:1` primero** | **`2026-09-10T11:20:15`** |

**23 segundos de distancia.** Es el corte más fino que se puede fechar con los
datos, y no depende de ninguna versión de código: es una diferencia de
comportamiento observable en el fichero.

---

## 3. La distribución

| ventana | con `b:1` primero | sin | % con |
|---|---:|---:|---:|
| **W1** (≤ 2026-08-11) | 0 | 336 | **0,0 %** |
| **W3** (2026-08-12 → 09-11) | 16 | 2 | 88,9 % |
| **W4** (≥ 2026-09-11) | 899 | 5 | **99,4 %** |
| **total** | 915 | 343 | 72,7 % |

**[C]** Las 336 manos de W1 **no tienen ni una sola** con `b:1` primero.
**[C]** El corte cae en el arranque de W3, que es cuando empieza el
comportamiento nuevo.

### Por qué importa

Las ventanas **W1/W3/W4** de `AUDITORIA_SEMANTICA_GRABADOR.md` se delimitaron
por **fechas de commit**. Esta frontera las delimita por **el dato mismo**, y
caen en el mismo sitio. Son dos pruebas independientes del mismo corte.

---

## 4. Los 12 parpadeos

La frontera no es una línea recta: el estado alterna **13 veces**, no una.

```
2026-09-10T11:19:52  sin b:1  ->  11:20:15  b:1     <- EL CORTE
2026-09-10T11:31:00  b:1      ->  11:32:36  sin b:1
2026-09-10T11:32:36  sin b:1  ->  11:32:51  b:1
2026-09-14T16:29:39  b:1      ->  16:30:10  sin b:1
2026-09-14T16:30:10  sin b:1  ->  16:30:39  b:1
2026-09-14T17:05:48  b:1      ->  17:06:54  sin b:1
2026-09-14T17:06:54  sin b:1  ->  17:08:35  b:1
2026-09-15T19:55:10  b:1      ->  19:55:28  sin b:1
2026-09-15T19:55:28  sin b:1  ->  19:57:00  b:1
2026-09-16T12:54:06  b:1      ->  12:54:33  sin b:1
2026-09-16T12:54:33  sin b:1  ->  13:27:56  b:1
2026-09-18T14:03:15  b:1      ->  14:03:37  sin b:1
```

**[D]** Los 12 parpadeos duran **entre 15 segundos y 53 minutos**. No son un
cambio de versión — una versión no se reinstala cada minuto. Son **huecos de
captura**: manos en las que la ciega del BB no se leyó, o en las que el
primero que actuó fue otro.

**[D]** Por eso la frontera sirve como **intervalo probable**, no como fecha
exacta de un despliegue.

---

## 5. Qué se hizo con ella

Al agregar las ciegas:

| regla | nº |
|---|---:|
| `BB b 1.0` en la acción 0 → **sustituida** por `BB p 1.0` | **915** |
| `BB p 1.0` **añadida** donde no había ciega | **342** |
| `SB r 0.5` → **sustituida** por `SB p 0.5` | **11** |
| `SB p 0.5` **añadida** | **1217** |
| manos tocadas | **1257 de 1258** |

**[C]** La única intacta es `H_0049`, que ya tenía sus tres `p`.

**[C]** Resultado: **1258 de 1258** manos tienen `BB p 1.0`. Ninguna quedó sin
ciega.

---

## 6. Cómo usarla después

**[P]** La frontera sirve para tres cosas concretas:

1. **Segmentar cualquier medición por generación de grabador**, sin depender de
   fechas de commit que pueden no corresponder a lo que estaba corriendo.
2. **Explicar las rarezas que solo aparecen en un lado.** Por ejemplo: el
   patrón de «falta 1.0» del BB se concentra en W4, que es exactamente el lado
   con `b:1` primero.
3. **Fechar un cambio de comportamiento del grabador** cuando no hay commit que
   lo documente.

**[P]** Cómo consultar la frontera de una mano concreta:

```python
acs = mano['streets']['preflop']['actions']
b1 = bool(acs) and acs[0].get('pos') == 'BB' \
     and acs[0].get('action') == 'b' and acs[0].get('amount') == 1.0
# b1 True  -> grabador nuevo (con la ciega emitida)
# b1 False -> grabador antiguo, o captura sin ciega
```

**[D]** **Límite que hay que recordar:** desde la sesión anterior, todas las
manos tienen `p` y la frontera **ya no se puede leer en el fichero**. Este
documento es lo que la conserva. Si la copia se sobrescribe, se pierde.

---

## 7. Lo que la frontera NO dice

**[D]** No dice **qué versión** del grabador era. Solo que el comportamiento
cambió en ese momento.

**[D]** No dice si el cambio fue de código o de configuración de la app.

**[D]** Los 343 lados «sin `b:1`» **no son todos** del grabador antiguo: 12
parpadeos están dentro del periodo nuevo. **[C]** 336 son de W1, que sí es el
grabador antiguo; las otras 7 son huecos.