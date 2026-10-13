# Reconstrucción de derivados — commit `1b14c18`

**Fecha:** 2026-10-13
**Origen:** `tools/reconstruir_derivados.py`
**Backup:** `data/_snapshot_pre_rebuild_1b14c18/` (verificado por SHA-256)

## Por qué se reconstruye

Los derivados en `data/*.json` estaban construidos con código que ya no existe:

| bug corregido | alcance | fase |
|---|---|---|
| ventana de 1280 manos | todos los derivados leían 380 manos no fiables | F1 |
| ciega del BB contada como subida | `learn.preflop_events` | F2 |
| squeeze con `limps_before` | 13 falsos squeezes | revisión_1 |
| orden temporal: folds por delante | 139/900 manos (15.4%) | revisión_2 |
| `_pf_rival_pos` con limpes cortos | 577/900 manos | revisión_1 |
| ciega BB confundida con acción voluntaria | caso BB que iguala una subida | revisión_2 |
| `_prior_grid` con fallback arbitrario | todos los priors 3bet/call_open | F4 |

## Comparación antes / después

### Metricas de `learn.preflop_events` — SIN CAMBIOS

| metrica | antes | después |
|---|---|---|
| manos | 900 | 900 |
| eventos | 4632 | 4632 |
| jugadores | 154 | 154 |
| eventos con cartas | 1159 | 1159 |
| `no_raise` / `facing_open` / `facing_3bet` | 2904 / 1600 / 128 | 2904 / 1600 / 128 |

Las 13 categorías tampoco cambian. **Esto es lo esperado y es correcto**: el
baseline se capturó con el `learn.py` ya corregido, así que una diferencia aquí
habría indicado una regresión.

> Los bugs de F2 (squeeze, orden temporal) quedan fuera de esta tabla porque
> estaban **ya corregidos** en el momento de capturar el baseline. Lo que estos
> derivados*muestran* es el efecto acumulado de F1 (ventana de 900).

### `profile_ranges.json` — cobertura muy superior

| | antes | después | delta |
|---|---|---|---|
| jugadores | 56 | **154** | +98 |
| `omega` (jugadores) | 56 | **154** | +98 |
| `opp_keys` | 6 | 6 | 0 |
| `cnt_keys` | 22 | 22 | 0 |
| bytes | 81 605 | 94 714 | +13 109 |

El fichero anterior solo etiquetaba **56 de 154** jugadores: casi dos tercios de
la base no estaban en el modelo de rangos. Ahora sí están.

### `postflop_ranges.json` — cobertura superior

| | antes | después | delta |
|---|---|---|---|
| `opp_keys` | 80 | **106** | +26 |
| `cnt_keys` | 131 | **181** | +50 |
| bytes | 8 131 | 13 114 | +4 983 |

## Observación importante sobre `_pf_rival_pos`

El fix de `_pf_rival_pos` (577/900 manos con rival equivocado) **no aparece en
esta comparación, y no es un fallo del procedimiento**: esa función se ejecuta
en `asistente_live` al **recomendar**, no al construir los derivados. El modelo
guardado (`profile_ranges.json`) no depende de qué rival se leApplicable a
cada consulta; solo cambia lo que el motor devuelve en vivo.

Para verificar ese fix hay que mirar el panel del asistente, no los ficheros.

## Validación posterior

```
496 passed, 1 skipped, 2 warnings
```

Los 2 warnings son intencionados: son los tests que verifican que `_prior_grid`
avisa al caer al prior plano.

`python -m motor.db_health` responde correctamente y muestra cobertura por
perfil × calle × acción.

## Riesgos que persisten en los derivados reconstruidos

| riesgo | impacto | fase |
|---|---|---|
| `bb_check` subrepresentado | 41 eventos perdidos de 830 (4.9%) | pendiente |
| `amount` mezcla niveles e incrementos | 33 de las 34 inversiones detectadas | F3 |
| un caso de OCR (`H_0141`: `2.7` leído `27.0`) | 1 mano | OCR |

Ninguno de los tres invalida la reconstrucción: los tres serían igual de
persistentes con los ficheros antiguos, y los tres tienen ahora una medición
reproducible (`tools/auditar_bb_check.py`, `tools/investigar_importes.py`).

## Cómo revertir

```bash
Copy-Item data/_snapshot_pre_rebuild_1b14c18/*.json data/ -Force
```