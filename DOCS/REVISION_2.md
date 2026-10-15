# REVISION_2 — el `.txt` se corrompió, y esto lo declara

**Estado:** vigente.
**Origen:** `revision_2.txt`, que se corrompió y ya no existe.

---

## 1. Qué pasó

El fichero `revision_2.txt`, en la raíz del repositorio, se corrompió:

| | |
|---|---|
| tamaño | 3017 bytes |
| bytes NUL | **460**, en el bloque central |
| fin del fichero | truncado a media frase: *«Y los cinco casos citad»* |
| contenido del final | un fragmento de material de `DEFECTO_652`, ya resuelto en `75bbdb7` |

No se sabe cómo se corrompió ni cuándo. **No estaba en git** —nunca se
commiteó—, así que no hay versión anterior a la que volver. No se ha
reconstruido a partir del fragmento: sin el original, una versión generada
no conservaría el contenido pretendido, y un documento que dice una cosa
distinta de la que decía es peor que un documento que no está.

Se borra y se sustituye por este.

## 2. Qué contenía, y que sigue en pie

`revision_2.txt`-era era la especificación de **F6.2.b** — el productor de
`equity_main` en modo sombra —, y los criterios de aceptación que traía.

**F6.2.b está implementado**, desde `000c360`:

```
F6.2.b: equity_main cableado en la ruta de asistente_live,
        en modo sombra, sin alterar la accion
```

Su especificación escrita está en dos sitios que **sí** están en git:

| | |
|---|---|
| [`F62B_INSERCION.md`](F62B_INSERCION.md) | el mini-inventario del punto de inserción: las cuatro preguntas, medidas |
| [`APARCADO_DB.md`](APARCADO_DB.md) | el estado del bloque |

Y los seis criterios de aceptación que traía `revision_2.txt` tienen tests, en
`motor/test_equity_main_live.py`: productor aislado, rival correcto, datos
insuficientes sin inventar valores, modo sombra que no consume, invariancia de
la acción, y los casos de rival válido / ausente / sin equity / excepción.

## 3. Qué NO dice este documento

- **No** reconstruye el texto perdido. No lo tengo.
- **No** dice que el contenido fuera irrelevante. Era la especificación de un
  bloque que se implementó; lo que se perdió es el documento, no el trabajo.
- **No** cierra F6.2.b. Dice que **está implementado y verificable en otro
  sitio**, que es distinto de «cerrado y documentado aquí».

> Si alguien necesita el texto original, no está. Y no se va a escribir de
> memoria: un `revision_2.md` con el contenido inventado sería exactamente el
> fallo que este repositorio lleva nueve bloques evitando.