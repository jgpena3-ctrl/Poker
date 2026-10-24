# Botes no encontrados - revision manual

Generado por `tools/aritmetica_botes.py`.

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack: no se normaliza) | 1 |
| `NADA` (el bote no coincide con ninguna lectura) | 14 |
| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | 0 |

En las `STACK` el registro ya es imposible (un jugador compromete mas que su stack), asi que normalizarlo dispararia el bote: se dejan intactas. En las `NADA` el bote declarado no sale con ninguna combinacion de apuestas parciales/absolutas, con ni sin comision, ni con ni sin la ciega del SB.

De las `ACCION_AMBIGUA`: `REPARTO` 0 (mismo neto y bruto; cambia quien aporta), `NETO_IGUAL` 0 (mismo neto; cambian importes igualados), `REAL` 0 (el neto cambia; hay que decidir). Solo `REAL` afecta a la ganancia. Las `DEVUELTA` (subida no pagada; el neto no cambia) se resuelven solas eligiendo la lectura absoluta.

## STACK (1)

### H_0740 - 2026-09-15

- **Pot declarado**: 37.7
- **Combinaciones**: 2
- **Netos posibles**: [18.24, 19.66]
- **Brutos posibles**: [37.84, 39.27]
- **Coincidencia**: bruto = 37.84 (dif 0.14)
- **Stacks**: BB=136.0, UTG=102.1, MP=110.3, CO=183.6, BTN=52.1, SB=28.1
- **Supera stack**: SB total=28.2 stack=28.1 exceso=+0.10
- **Nota**: el exceso <= 0.2 esta dentro de la tolerancia del bote; puede ser redondeo, no un error de stack.
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB r 2.0 | BB c 2.0 | CO c 2.0
- **flop**: SB b 2.9 | BB c 2.9 | CO f 0.0
- **turn**: SB b 3.7 | BB c 3.7
- **river**: SB b 19.6 | BB f 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | SB r absoluta 2.00 | BB c 2.00 | CO c 2.00 | SB b absoluta 2.90 | BB c 2.90 | CO f | SB b absoluta 3.70 | BB c 3.70 | BB f

## NADA (14)

### H_0026 - 2026-07-27

- **Pot declarado**: 27.7
- **Combinaciones**: 1
- **Netos posibles**: [28.5]
- **Brutos posibles**: [37.6]
- **Neto mas cercano**: 28.5 (dif 0.8)
- **Stacks**: CO=68.8, BTN=124.4, SB=65.6, BB=146.6, UTG=74.3, MP=59.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO p 1.0 | UTG f 0.0 | MP r 5.0 | CO f 0.0 | BTN f 0.0 | SB c 5.0 | BB f 0.0
- **flop**: SB b 3.4 | MP c 3.4
- **turn**: SB b 5.6 | MP c 5.6
- **river**: SB b 9.1 | MP f 0.0

### H_0037 - 2026-07-28

- **Pot declarado**: 33.5
- **Combinaciones**: 2
- **Netos posibles**: [18.73, 21.57]
- **Brutos posibles**: [31.73, 34.58]
- **Neto mas cercano**: 21.57 (dif -11.93)
- **Stacks**: CO=59.0, BTN=136.7, SB=88.3, BB=166.0, UTG=80.2, MP=52.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB r 5.0 | MP c 5.0 | CO c 5.0
- **flop**: BB x 0.0 | MP b 2.0 | CO r 15.0 | BB f 0.0 | MP f 0.0

### H_0243 - 2026-07-31

- **Pot declarado**: 33.7
- **Combinaciones**: 1
- **Netos posibles**: [19.86]
- **Brutos posibles**: [33.97]
- **Neto mas cercano**: 19.86 (dif -13.84)
- **Stacks**: BTN=94.0, SB=207.3, BB=56.6, UTG=100.5, MP=114.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN b 3.0 | SB f 0.0 | BB c 3.0
- **flop**: BB x 0.0 | BTN b 3.1 | BB c 3.1
- **turn**: BB x 0.0 | BTN b 3.9 | BB r 18.0 | BTN f 0.0

### H_0581 - 2026-09-15

- **Pot declarado**: 27.3
- **Combinaciones**: 1
- **Netos posibles**: [26.22]
- **Brutos posibles**: [26.22]
- **Neto mas cercano**: 26.22 (dif -1.08)
- **Stacks**: CO=100.0, BTN=11.3, SB=27.4, BB=42.1, UTG=106.2, MP=22.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO p 1.0 | UTG f 0.0 | MP c 1.0 | CO x 0.0 | BTN r 2.0 | SB c 2.0 | BB f 0.0 | MP c 2.0 | CO c 2.0
- **flop**: SB x 0.0 | MP b 3.0 | CO f 0.0 | BTN r 9.3 | SB f 0.0 | MP c 9.3

### H_0585 - 2026-09-15

- **Pot declarado**: 33.6
- **Combinaciones**: 2
- **Netos posibles**: [20.71, 22.61]
- **Brutos posibles**: [32.71, 34.61]
- **Neto mas cercano**: 22.61 (dif -10.99)
- **Stacks**: BB=101.8, MP=21.9, CO=40.6, SB=39.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | SB c 1.0 | BB r 5.0 | MP c 5.0 | SB f 0.0
- **flop**: BB b 5.4 | MP c 5.4
- **turn**: BB b 12.0 | MP f 0.0

### H_0588 - 2026-09-15

- **Pot declarado**: 15.0
- **Combinaciones**: 2
- **Netos posibles**: [11.59, 13.49]
- **Brutos posibles**: [14.59, 16.49]
- **Neto mas cercano**: 13.49 (dif -1.51)
- **Stacks**: BTN=112.5, SB=13.0, BB=40.6, CO=37.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 2.5 | SB c 2.5
- **flop**: SB x 0.0 | BB x 0.0
- **turn**: SB x 0.0 | BB b 3.6 | SB c 3.6
- **river**: SB x 0.0 | BB b 3.0 | SB f 0.0

### H_0589 - 2026-09-15

- **Pot declarado**: 15.0
- **Combinaciones**: 1
- **Netos posibles**: [14.54]
- **Brutos posibles**: [14.54]
- **Neto mas cercano**: 14.54 (dif -0.46)
- **Stacks**: CO=112.5, BTN=6.9, SB=46.5, BB=37.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO c 1.0 | BTN r 6.9 | SB f 0.0 | BB c 6.9 | CO f 0.0

### H_0590 - 2026-09-15

- **Pot declarado**: 4.0
- **Combinaciones**: 1
- **Netos posibles**: [5.8]
- **Brutos posibles**: [10.2]
- **Neto mas cercano**: 5.8 (dif 1.8)
- **Stacks**: BB=108.5, BTN=48.8
- **Acciones**:
- **preflop**: BB p 1.0 | BTN c 1.0 | BB x 0.0
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB b 1.0 | BTN c 1.0
- **river**: BB b 1.0 | BTN r 5.4 | BB f 0.0

### H_0593 - 2026-09-15

- **Pot declarado**: 16.8
- **Combinaciones**: 1
- **Netos posibles**: [9.31]
- **Brutos posibles**: [16.51]
- **Neto mas cercano**: 9.31 (dif -7.49)
- **Stacks**: SB=108.5, BB=181.5, BTN=48.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN r 2.5 | SB c 2.5 | BB f 0.0
- **flop**: SB x 0.0 | BTN b 1.9 | SB c 1.9
- **turn**: SB x 0.0 | BTN x 0.0
- **river**: SB b 7.2 | BTN f 0.0

### H_0642 - 2026-09-15

- **Pot declarado**: 22.2
- **Combinaciones**: 1
- **Netos posibles**: [14.84]
- **Brutos posibles**: [22.43]
- **Neto mas cercano**: 14.84 (dif -7.36)
- **Stacks**: SB=254.0, BB=101.0, MP=13.7, CO=119.8, BTN=92.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 2.1 | MP c 2.1 | SB c 2.1
- **turn**: SB x 0.0 | BB x 0.0 | MP x 0.0
- **river**: SB b 3.0 | BB f 0.0 | MP r 10.6 | SB f 0.0

### H_0676 - 2026-09-15

- **Pot declarado**: 33.9
- **Combinaciones**: 1
- **Netos posibles**: [28.99]
- **Brutos posibles**: [28.99]
- **Neto mas cercano**: 28.99 (dif -4.91)
- **Stacks**: BB=99.0, MP=103.8, CO=45.0, BTN=47.4, SB=34.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 2.4 | MP c 2.4 | CO f 0.0 | BTN c 2.4 | SB f 0.0
- **river**: BB b 5.8 | MP c 5.8 | BTN c 11.6 | BB f 0.0 | MP f 0.0

### H_0835 - 2026-09-16

- **Pot declarado**: 23.5
- **Combinaciones**: 1
- **Netos posibles**: [14.72]
- **Brutos posibles**: [22.52]
- **Neto mas cercano**: 14.72 (dif -8.78)
- **Stacks**: MP=76.4, CO=53.6, BTN=51.5, SB=71.6, BB=100.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB b 0.5 | MP r 2.5 | CO f 0.0 | BTN f 0.0 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0
- **turn**: SB x 0.0 | BB x 0.0 | MP b 4.0 | SB c 4.0 | BB f 0.0
- **river**: SB x 0.0 | MP b 7.8 | SB f 0.0

### H_0872 - 2026-09-16

- **Pot declarado**: 114.5
- **Combinaciones**: 2
- **Netos posibles**: [31.58, 33.48]
- **Brutos posibles**: [115.38, 117.28]
- **Neto mas cercano**: 33.48 (dif -81.02)
- **Stacks**: CO=101.5, BTN=130.6, SB=62.5, BB=100.0, UTG=77.3, MP=68.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | SB c 5.0
- **flop**: SB x 0.0 | BB b 3.2 | SB c 3.2
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 8.0 | BB r 91.8 | SB f 0.0

### H_0912 - 2026-09-17

- **Pot declarado**: 71.7
- **Combinaciones**: 1
- **Netos posibles**: [71.9]
- **Brutos posibles**: [71.9]
- **Neto mas cercano**: 71.9 (dif 0.2)
- **Stacks**: UTG=95.7, MP=83.4, CO=353.8, BTN=112.8, SB=97.2, BB=63.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN r 3.0 | SB c 3.0 | BB c 3.0 | CO c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0 | BTN b 3.8 | SB f 0.0 | BB f 0.0 | CO c 3.8
- **turn**: CO x 0.0 | BTN b 9.3 | CO c 9.3
- **river**: CO b 18.1 | BTN c 18.1
