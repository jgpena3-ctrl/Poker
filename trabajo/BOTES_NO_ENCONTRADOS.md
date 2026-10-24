# Botes no encontrados - revision manual

Generado por `tools/aritmetica_botes.py`.

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack: no se normaliza) | 1 |
| `NADA` (el bote no coincide con ninguna lectura) | 29 |
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
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB r 2.0 | BB c 1.0 | CO c 1.0
- **flop**: SB b 2.9 | BB c 2.9 | CO f 0.0
- **turn**: SB b 3.7 | BB c 3.7
- **river**: SB b 19.6 | BB f 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | SB r absoluta 2.00 | BB c 2.00 | CO c 2.00 | SB b absoluta 2.90 | BB c 2.90 | CO f | SB b absoluta 3.70 | BB c 3.70 | BB f

## NADA (29)

### H_0444 - 2026-09-13

- **Pot declarado**: 56.0
- **Combinaciones**: 1
- **Netos posibles**: [27.55]
- **Brutos posibles**: [55.05]
- **Neto mas cercano**: 27.55 (dif -28.45)
- **Stacks**: SB=88.0, BB=30.0, MP=56.1, CO=108.5, BTN=40.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO r 2.5 | BTN c 2.5 | SB f 0.0 | BB f 0.0 | MP c 1.5
- **flop**: MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: MP b 10.0 | CO f 0.0 | BTN r 37.5 | MP f 0.0

### H_0532 - 2026-09-14

- **Pot declarado**: 25.61
- **Combinaciones**: 1
- **Netos posibles**: [11.97]
- **Brutos posibles**: [25.37]
- **Neto mas cercano**: 11.97 (dif -13.64)
- **Stacks**: BB=94.4, UTG=28.7, MP=115.8, CO=107.8, SB=40.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: SB x 0.0 | BB b 1.9 | UTG c 1.9 | MP f 0.0 | SB f 0.0
- **river**: BB b 2.4 | UTG r 15.8 | BB f 0.0

### H_0537 - 2026-09-15

- **Pot declarado**: 16.6
- **Combinaciones**: 1
- **Netos posibles**: [12.92]
- **Brutos posibles**: [16.22]
- **Neto mas cercano**: 12.92 (dif -3.68)
- **Stacks**: BTN=161.5, SB=68.4, BB=103.8, CO=104.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 3.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | CO b 3.3 | SB r 6.6 | CO f 0.0

### H_0553 - 2026-09-15

- **Pot declarado**: 29.6
- **Combinaciones**: 1
- **Netos posibles**: [19.48]
- **Brutos posibles**: [29.27]
- **Neto mas cercano**: 19.48 (dif -10.12)
- **Stacks**: MP=142.5, CO=48.7, BTN=74.4, SB=149.8, BB=107.2, UTG=59.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 3.0 | BTN c 3.0 | SB f 0.0 | BB f 0.0
- **flop**: CO b 2.5 | BTN c 2.5
- **turn**: CO x 0.0 | BTN x 0.0
- **river**: CO x 0.0 | BTN b 4.0 | CO r 13.8 | BTN f 0.0

### H_0581 - 2026-09-15

- **Pot declarado**: 27.3
- **Combinaciones**: 1
- **Netos posibles**: [26.22]
- **Brutos posibles**: [26.22]
- **Neto mas cercano**: 26.22 (dif -1.08)
- **Stacks**: CO=100.0, BTN=11.3, SB=27.4, BB=42.1, UTG=106.2, MP=22.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN r 2.0 | SB c 2.0 | BB f 0.0 | MP c 1.0 | CO c 1.0
- **flop**: SB x 0.0 | MP b 3.0 | CO f 0.0 | BTN r 9.3 | SB f 0.0 | MP c 6.3
- **turn**: MP x 0.0

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
- **preflop**: SB p 0.5 | BB p 1.0 | CO c 1.0 | BTN r 6.9 | SB f 0.0 | BB c 5.9 | CO f 0.0
- **flop**: BB x 0.0

### H_0590 - 2026-09-15

- **Pot declarado**: 10.3
- **Combinaciones**: 1
- **Netos posibles**: [5.7]
- **Brutos posibles**: [10.1]
- **Neto mas cercano**: 5.7 (dif -4.6)
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

### H_0611 - 2026-09-15

- **Pot declarado**: 37.0
- **Combinaciones**: 1
- **Netos posibles**: [27.27]
- **Brutos posibles**: [36.47]
- **Neto mas cercano**: 27.27 (dif -9.73)
- **Stacks**: CO=237.8, BTN=100.0, SB=12.5, BB=128.3, MP=97.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.5 | BTN r 9.0 | SB f 0.0 | BB f 0.0 | CO c 6.5
- **flop**: CO x 0.0 | BTN x 0.0
- **turn**: CO b 4.6 | BTN r 13.8 | CO f 0.0

### H_0623 - 2026-09-15

- **Pot declarado**: 15.06
- **Combinaciones**: 1
- **Netos posibles**: [11.21]
- **Brutos posibles**: [14.71]
- **Neto mas cercano**: 11.21 (dif -3.85)
- **Stacks**: MP=228.8, CO=180.5, BTN=103.8, SB=21.1, BB=125.9, UTG=96.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 1.4 | SB c 1.4
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 3.5 | BB r 7.0 | SB f 0.0

### H_0676 - 2026-09-15

- **Pot declarado**: 33.9
- **Combinaciones**: 1
- **Netos posibles**: [28.12]
- **Brutos posibles**: [28.12]
- **Neto mas cercano**: 28.12 (dif -5.78)
- **Stacks**: BB=99.0, MP=103.8, CO=45.0, BTN=47.4, SB=34.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 2.4 | MP c 2.4 | CO f 0.0 | BTN c 2.4 | SB f 0.0
- **river**: BB b 5.8 | MP c 5.8 | BTN c 11.6 | BB f 0.0 | MP f 0.0

### H_0694 - 2026-09-15

- **Pot declarado**: 24.5
- **Combinaciones**: 1
- **Netos posibles**: [13.68]
- **Brutos posibles**: [24.18]
- **Neto mas cercano**: 13.68 (dif -10.82)
- **Stacks**: BTN=85.9, SB=118.1, BB=56.1, CO=94.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 2.5 | SB c 2.5 | BB f 0.0
- **flop**: SB x 0.0 | BTN b 1.4 | SB c 1.4
- **turn**: SB x 0.0 | BTN b 2.8 | SB r 13.3 | BTN f 0.0

### H_0697 - 2026-09-15

- **Pot declarado**: 7.0
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [6.0]
- **Neto mas cercano**: 3.5 (dif -3.5)
- **Stacks**: SB=85.5, BB=125.1, UTG=51.1, MP=100.0, CO=None, BTN=23.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN r 3.5 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0741 - 2026-09-15

- **Pot declarado**: 37.7
- **Combinaciones**: 1
- **Netos posibles**: [24.7]
- **Brutos posibles**: [37.2]
- **Neto mas cercano**: 24.7 (dif -13.0)
- **Stacks**: SB=127.5, BB=102.1, UTG=110.3, MP=181.6, CO=52.1, BTN=35.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO r 2.0 | BTN c 2.0 | SB c 2.0 | BB f 0.0 | MP c 1.0
- **flop**: SB x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB b 4.3 | MP c 4.3 | CO f 0.0 | BTN f 0.0
- **river**: SB b 4.2 | MP r 16.7 | SB f 0.0

### H_0755 - 2026-09-15

- **Pot declarado**: 28.7
- **Combinaciones**: 1
- **Netos posibles**: [18.62]
- **Brutos posibles**: [28.22]
- **Neto mas cercano**: 18.62 (dif -10.08)
- **Stacks**: BTN=120.3, SB=20.5, BB=101.3, UTG=42.3, MP=237.4, CO=110.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 3.0 | CO c 3.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | MP b 4.8 | CO r 14.4 | SB f 0.0 | MP f 0.0

### H_0765 - 2026-09-15

- **Pot declarado**: 45.0
- **Combinaciones**: 1
- **Netos posibles**: [29.64]
- **Brutos posibles**: [44.24]
- **Neto mas cercano**: 29.64 (dif -15.36)
- **Stacks**: MP=120.4, CO=29.6, BTN=113.4, SB=99.0, BB=231.1, UTG=118.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 5.0 | CO f 0.0 | BTN f 0.0 | SB c 5.0 | BB c 4.0 | UTG f 0.0
- **flop**: SB b 7.6 | BB r 22.2 | MP f 0.0 | SB f 0.0

### H_0785 - 2026-09-15

- **Pot declarado**: 53.45
- **Combinaciones**: 2
- **Netos posibles**: [41.04]
- **Brutos posibles**: [51.74, 58.14]
- **Neto mas cercano**: 41.04 (dif -12.41)
- **Stacks**: CO=131.8, BTN=108.5, SB=52.3, BB=142.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 3.0 | SB c 3.0 | BB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 6.4 | BTN f 0.0 | SB r 17.1 | BB r 27.8 | SB f 0.0

### H_0868 - 2026-09-16

- **Pot declarado**: 92.825
- **Combinaciones**: 1
- **Netos posibles**: [52.2]
- **Brutos posibles**: [92.0]
- **Neto mas cercano**: 52.2 (dif -40.62)
- **Stacks**: CO=85.4, BTN=102.5, SB=43.2, BB=113.0, UTG=87.3, MP=70.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.5 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 3.6 | BTN r 13.0 | SB f 0.0 | BB c 13.0
- **river**: BB b 10.6 | BTN r 50.4 | BB f 0.0

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

### H_0919 - 2026-09-17

- **Pot declarado**: 16.625
- **Combinaciones**: 1
- **Netos posibles**: [8.07]
- **Brutos posibles**: [16.38]
- **Neto mas cercano**: 8.07 (dif -8.55)
- **Stacks**: BB=184.4, UTG=79.3, MP=390.1, CO=136.4, BTN=74.2, SB=98.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG b 2.5 | MP r 10.8 | BB f 0.0 | UTG f 0.0

### H_0925 - 2026-09-17

- **Pot declarado**: 27.225
- **Combinaciones**: 1
- **Netos posibles**: [26.32]
- **Brutos posibles**: [26.32]
- **Neto mas cercano**: 26.32 (dif -0.91)
- **Stacks**: SB=173.0, BB=114.4, UTG=323.0, MP=108.1, CO=137.3, BTN=95.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 3.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB c 3.0 | UTG c 3.0
- **flop**: BB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: BB x 0.0 | UTG x 0.0 | MP x 0.0
- **river**: BB x 0.0 | UTG b 9.1 | MP c 9.1 | BB f 0.0 | MP f 0.0

### H_0982 - 2026-09-17

- **Pot declarado**: 70.0
- **Combinaciones**: 1
- **Netos posibles**: [16.25]
- **Brutos posibles**: [69.75]
- **Neto mas cercano**: 16.25 (dif -53.75)
- **Stacks**: MP=166.9, CO=124.2, BTN=61.3, SB=99.5, BB=44.4, UTG=42.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.0 | MP f 0.0 | CO f 0.0 | BTN r 5.0 | SB f 0.0 | BB f 0.0 | UTG c 3.0
- **flop**: UTG b 2.8 | BTN r 56.3 | UTG f 0.0

### H_1089 - 2026-09-17

- **Pot declarado**: 18.1
- **Combinaciones**: 1
- **Netos posibles**: [11.21]
- **Brutos posibles**: [17.81]
- **Neto mas cercano**: 11.21 (dif -6.89)
- **Stacks**: BB=87.8, MP=71.8, CO=98.3, BTN=135.6, SB=166.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.0 | BTN f 0.0 | SB c 2.0 | BB c 2.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0
- **turn**: SB x 0.0 | BB b 2.9 | CO f 0.0 | SB r 9.5 | BB f 0.0

### H_1130 - 2026-09-18

- **Pot declarado**: 40.2
- **Combinaciones**: 1
- **Netos posibles**: [21.66]
- **Brutos posibles**: [39.76]
- **Neto mas cercano**: 21.66 (dif -18.54)
- **Stacks**: SB=116.3, BB=81.5, UTG=116.1, MP=37.8, CO=148.4, BTN=45.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.0 | SB c 2.0 | BB c 2.0
- **flop**: SB x 0.0 | BB b 4.0 | BTN f 0.0 | SB c 4.0
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 4.4 | BB r 22.5 | SB f 0.0

### H_1143 - 2026-09-18

- **Pot declarado**: 32.7
- **Combinaciones**: 1
- **Netos posibles**: [20.9]
- **Brutos posibles**: [32.2]
- **Neto mas cercano**: 20.9 (dif -11.8)
- **Stacks**: BTN=93.5, SB=116.0, BB=41.3, CO=205.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 3.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | CO b 3.3 | SB c 3.3
- **turn**: SB x 0.0 | CO x 0.0
- **river**: SB b 4.2 | CO r 15.5 | SB f 0.0

### H_1145 - 2026-09-18

- **Pot declarado**: 41.43
- **Combinaciones**: 1
- **Netos posibles**: [27.17]
- **Brutos posibles**: [40.97]
- **Neto mas cercano**: 27.17 (dif -14.26)
- **Stacks**: MP=93.5, CO=105.5, BTN=41.3, SB=215.1, BB=60.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 2.5 | CO f 0.0 | BTN c 2.5 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | MP x 0.0 | BTN x 0.0
- **turn**: BB x 0.0 | MP x 0.0 | BTN b 5.7 | BB f 0.0 | MP c 5.7
- **river**: MP b 4.6 | BTN r 18.4 | MP f 0.0

### H_1172 - 2026-09-18

- **Pot declarado**: 13.2
- **Combinaciones**: 1
- **Netos posibles**: [10.45]
- **Brutos posibles**: [12.95]
- **Neto mas cercano**: 10.45 (dif -2.75)
- **Stacks**: UTG=94.6, MP=77.3, CO=101.7, BTN=100.0, SB=55.5, BB=41.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB c 2.5 | BB f 0.0
- **flop**: SB x 0.0 | CO b 2.5 | SB r 5.0 | CO f 0.0
