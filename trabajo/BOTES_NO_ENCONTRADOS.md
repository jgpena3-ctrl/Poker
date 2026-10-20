# Botes no encontrados - revision manual

Generado por `tools/aritmetica_botes.py`.

| motivo | manos |
|---|---:|
| `STACK` (alguna accion supera el stack: no se normaliza) | 13 |
| `NADA` (el bote no coincide con ninguna lectura) | 129 |
| `ACCION_AMBIGUA` (bote unico, acciones no unicas) | 61 |

En las `STACK` el registro ya es imposible (un jugador compromete mas que su stack), asi que normalizarlo dispararia el bote: se dejan intactas. En las `NADA` el bote declarado no sale con ninguna combinacion de apuestas parciales/absolutas, con ni sin comision, ni con ni sin la ciega del SB.

De las `ACCION_AMBIGUA`: `DEVUELTA` 44 (la diferencia esta en una subida no pagada; el bote neto NO cambia), `REPARTO` 11 (mismo neto y bruto; cambia quien aporta), `NETO_IGUAL` 5 (mismo neto; cambian importes igualados), `REAL` 1 (el neto cambia; hay que decidir). Solo `REAL` afecta a la ganancia.

## STACK (13)

### H_0022 - 2026-07-27

- **Pot declarado**: 23.8
- **Combinaciones**: 1
- **Netos posibles**: [24.23]
- **Brutos posibles**: [52.23]
- **Coincidencia**: neto_sin_sb = 23.725 (dif -0.075)
- **Stacks**: MP=65.8, CO=136.7, BTN=81.2, SB=100.0, BB=None, UTG=31.0
- **Supera stack**: UTG total=36.0 stack=31.0 exceso=+5.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.0 | MP f 0.0 | CO r 8.0 | BTN c 7.5 | SB f 0.0 | BB f 0.0 | UTG c 8.0
- **flop**: BTN x 0.0 | UTG b 28.0 | CO f 0.0 | BTN f 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG b absoluta 2.00 | MP f | CO r absoluta 8.00 | BTN c 8.00 | SB f | BB f | UTG c 8.00 | BTN x | CO f | BTN f

### H_0034 - 2026-07-28

- **Pot declarado**: 7.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [90.6, 91.1]
- **Neto mas cercano**: 3.0 (dif -4.0)
- **Stacks**: BB=69.5, UTG=136.7, MP=151.0, BTN=79.2, SB=56.6
- **Supera stack**: SB total=88.6 stack=56.6 exceso=+32.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 1.0 | SB r 88.6 | BB f 0.0

### H_0036 - 2026-07-28

- **Pot declarado**: 10.5
- **Combinaciones**: 1
- **Netos posibles**: [10.45]
- **Brutos posibles**: [94.15]
- **Coincidencia**: neto = 10.45 (dif -0.05)
- **Stacks**: MP=70.5, CO=136.7, BTN=87.8, SB=161.0, BB=80.2, UTG=45.7
- **Supera stack**: UTG total=88.7 stack=45.7 exceso=+43.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 5.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 5.0 | BB x 0.0
- **flop**: SB x 0.0 | UTG b 83.7 | SB f 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG b absoluta 5.00 | MP f | CO f | BTN f | SB c 5.00 | BB x | SB x | SB f

### H_0055 - 2026-07-28

- **Pot declarado**: 24.0
- **Combinaciones**: 2
- **Netos posibles**: [24.52, 26.43]
- **Brutos posibles**: [37.62, 39.52]
- **Coincidencia**: neto_sin_sb = 24.025 (dif 0.025)
- **Stacks**: SB=141.2, BB=88.4, UTG=175.3, MP=24.5, BTN=123.1
- **Supera stack**: MP total=25.0 stack=24.5 exceso=+0.50
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | BTN b 2.5 | SB f 0.0 | BB f 0.0 | MP r 7.0 | BTN c 7.0
- **flop**: MP x 0.0 | BTN b 4.9 | MP r 18.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | BTN b absoluta 2.50 | SB f | BB f | MP r absoluta 7.00 | BTN c 7.00 | MP x | BTN b absoluta 4.90

### H_0077 - 2026-07-29

- **Pot declarado**: 37.1
- **Combinaciones**: 1
- **Netos posibles**: [24.98]
- **Brutos posibles**: [125.98]
- **Neto mas cercano**: 24.98 (dif -12.12)
- **Stacks**: BTN=46.2, SB=140.6, BB=101.4, UTG=113.7, MP=21.5, CO=40.7
- **Supera stack**: MP total=110.4 stack=21.5 exceso=+88.90
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 3.0 | MP c 3.0 | CO c 3.0 | BTN c 3.0 | SB f 0.0 | BB f 0.0
- **flop**: UTG x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: UTG b 6.4 | MP c 6.4 | CO f 0.0 | BTN f 0.0
- **river**: UTG x 0.0 | MP b 101.0

### H_0084 - 2026-07-29

- **Pot declarado**: 39.0
- **Combinaciones**: 1
- **Netos posibles**: [22.99]
- **Brutos posibles**: [52.69]
- **Neto mas cercano**: 22.99 (dif -16.01)
- **Stacks**: SB=34.3, BB=134.6, UTG=111.0, MP=118.2, CO=20.0, BTN=14.0
- **Supera stack**: SB total=41.3 stack=34.3 exceso=+7.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO b 4.5 | BTN f 0.0 | SB c 4.5 | BB f 0.0
- **flop**: SB x 0.0 | CO b 7.1 | SB r 36.8
- **turn**: SB x 0.0
- **river**: SB x 0.0

### H_0136 - 2026-07-29

- **Pot declarado**: 16.2
- **Combinaciones**: 4
- **Netos posibles**: [16.15, 18.05]
- **Brutos posibles**: [45.75, 47.65]
- **Coincidencia**: neto = 16.15 (dif -0.05)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB b [2.5, 2.0]
- **Stacks**: SB=31.6, BB=109.8, UTG=13.5, MP=94.7, BTN=91.2
- **Supera stack**: SB total=37.6 stack=31.6 exceso=+6.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | BTN f 0.0 | SB b 2.0 | BB r 8.0 | UTG f 0.0 | SB c 8.0
- **flop**: SB x 0.0 | BB x 0.0
- **turn**: SB b 29.6 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | BTN f | SB b parcial 2.50 | BB r absoluta 8.00 | UTG f | SB c 8.00 | SB x | BB x | BB f
  2. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | BTN f | SB b absoluta 2.00 | BB r absoluta 8.00 | UTG f | SB c 8.00 | SB x | BB x | BB f

### H_0190 - 2026-07-30

- **Pot declarado**: 27.0
- **Combinaciones**: 1
- **Netos posibles**: [27.17]
- **Brutos posibles**: [27.17]
- **Coincidencia**: neto = 27.17 (dif 0.17)
- **Stacks**: MP=113.2, CO=12.7, BTN=50.2, SB=108.1, BB=130.3, UTG=26.4
- **Supera stack**: CO total=12.8 stack=12.7 exceso=+0.10
- **Nota**: el exceso <= 0.2 esta dentro de la tolerancia del bote; puede ser redondeo, no un error de stack.
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | UTG c 1.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG x 0.0 | BTN x 0.0 | SB b 2.4 | BB f 0.0 | UTG f 0.0 | CO r 6.8 | BTN f 0.0 | SB c 6.8
- **turn**: SB x 0.0 | CO b 5.0 | SB c 4.9
- **river**: SB x 0.0 | CO x 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | MP f | UTG c 1.00 | CO c 1.00 | BTN c 1.00 | SB c 1.00 | BB x | BB x | UTG x | BTN x | SB b absoluta 2.40 | BB f | UTG f | CO r absoluta 6.80 | BTN f | SB c 6.80 | SB x | SB c 5.00 | SB x | CO x

### H_0194 - 2026-07-30

- **Pot declarado**: 57.9
- **Combinaciones**: 1
- **Netos posibles**: [57.8]
- **Brutos posibles**: [167.4]
- **Coincidencia**: neto = 57.8 (dif -0.1)
- **Stacks**: BTN=111.7, SB=18.6, BB=47.2, UTG=110.2, MP=128.8, CO=22.4
- **Supera stack**: MP total=132.0 stack=128.8 exceso=+3.20, CO total=131.3 stack=22.4 exceso=+108.90
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP b 5.0 | CO c 5.0 | BTN c 5.0 | SB f 0.0 | BB c 5.0 | UTG c 5.0
- **flop**: BB x 0.0 | UTG x 0.0 | MP b 121.0 | CO c 121.0 | BTN f 0.0 | BB f 0.0 | UTG f 0.0
- **turn**: MP b 6.0 | CO c 5.3
- **river**: MP x 0.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP b absoluta 5.00 | CO c 5.00 | BTN c 5.00 | SB f | BB c 5.00 | UTG c 5.00 | BB x | UTG x | MP b absoluta 121.00 | CO c all-in 17.40 | BTN f | BB f | UTG f | CO c all-in 0.00 | MP x

### H_0311 - 2026-08-01

- **Pot declarado**: 129.9
- **Combinaciones**: 1
- **Netos posibles**: [94.5]
- **Brutos posibles**: [109.8]
- **Neto mas cercano**: 94.5 (dif -35.4)
- **Stacks**: BTN=113.9, SB=45.5, BB=120.6, UTG=33.2, MP=151.0, CO=173.3
- **Supera stack**: SB total=60.7 stack=45.5 exceso=+15.20
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP b 5.0 | CO f 0.0 | BTN f 0.0 | SB c 5.0 | BB f 0.0 | UTG c 5.0
- **flop**: SB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: SB b 5.0 | UTG f 0.0 | MP r 5.1
- **river**: SB b 8.2 | MP r 50.7 | SB c 50.7

### H_0691 - 2026-09-15

- **Pot declarado**: 35.6
- **Combinaciones**: 1
- **Netos posibles**: [35.62]
- **Brutos posibles**: [35.62]
- **Coincidencia**: neto = 35.625 (dif 0.025)
- **Stacks**: CO=87.4, BTN=95.0, SB=56.1, BB=93.2, MP=13.0
- **Supera stack**: MP total=18.0 stack=13.0 exceso=+5.00
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | BTN r 5.0 | SB f 0.0 | BB f 0.0 | MP c 5.0
- **flop**: MP x 0.0 | BTN x 0.0
- **turn**: MP b 13.0 | BTN c 13.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO f | BTN r absoluta 5.00 | SB f | BB f | MP c 5.00 | MP x | BTN x | BTN c 13.00

### H_0713 - 2026-09-15

- **Pot declarado**: 44.7
- **Combinaciones**: 1
- **Netos posibles**: [42.84]
- **Brutos posibles**: [44.74]
- **Coincidencia**: bruto = 44.745 (dif 0.045)
- **Stacks**: MP=95.6, CO=176.4, BTN=45.4, SB=153.5, BB=57.4, UTG=21.8
- **Supera stack**: UTG total=23.7 stack=21.8 exceso=+1.90
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 5.0 | CO f 0.0 | SB f 0.0 | BB f 0.0 | UTG c 5.0
- **flop**: UTG x 0.0 | MP b 2.7 | UTG c 2.7
- **turn**: UTG x 0.0 | MP b 8.0 | UTG c 8.0
- **river**: UTG x 0.0 | MP b 8.0 | UTG c 8.0
- **Lecturas alternativas** (1):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP r absoluta 5.00 | CO f | SB f | BB f | UTG c 5.00 | UTG x | MP b absoluta 2.70 | UTG c 2.70 | UTG x | MP b absoluta 8.00 | UTG c 8.00 | UTG x | MP b absoluta 8.00 | UTG c all-in 6.10

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

## NADA (129)

### H_0026 - 2026-07-27

- **Pot declarado**: 27.7
- **Combinaciones**: 1
- **Netos posibles**: [30.4]
- **Brutos posibles**: [39.5]
- **Neto mas cercano**: 30.4 (dif 2.7)
- **Stacks**: CO=68.8, BTN=124.4, SB=65.6, BB=146.6, UTG=74.3, MP=59.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 6.0 | CO b 1.0 | BTN f 0.0 | SB c 1.0 | SB c 5.0 | BB x 0.0
- **flop**: SB b 3.4 | MP c 3.4
- **turn**: SB b 5.6 | MP c 5.6
- **river**: SB b 9.1 | MP f 0.0

### H_0027 - 2026-07-27

- **Pot declarado**: 3.8
- **Combinaciones**: 1
- **Netos posibles**: [2.85]
- **Brutos posibles**: [9.85]
- **Neto mas cercano**: 2.85 (dif -0.95)
- **Stacks**: BTN=66.0, SB=125.4, BB=66.6, UTG=146.6, MP=74.3, CO=60.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN b 1.0 | SB c 1.0 | CO x 0.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0 | BTN b 7.0 | SB f 0.0 | BB f 0.0 | CO f 0.0

### H_0030 - 2026-07-28

- **Pot declarado**: 20.0
- **Combinaciones**: 2
- **Netos posibles**: [14.63]
- **Brutos posibles**: [17.53, 21.03]
- **Neto mas cercano**: 14.63 (dif -5.37)
- **Stacks**: UTG=67.5, MP=122.7, BTN=63.4, SB=150.0, BB=77.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | BTN b 1.4 | SB c 1.4 | BB c 1.4
- **turn**: SB x 0.0 | BB x 0.0 | BTN b 3.5 | SB r 4.1 | BB f 0.0 | BTN r 7.0
- **river**: SB x 0.0 | BTN x 0.0

### H_0031 - 2026-07-28

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 7.0]
- **Neto mas cercano**: 2.0 (dif -1.0)
- **Stacks**: UTG=67.5, BTN=122.7, SB=64.4, BB=148.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | SB f 0.0

### H_0032 - 2026-07-28

- **Pot declarado**: 29.4
- **Combinaciones**: 4
- **Netos posibles**: [34.2, 36.1]
- **Brutos posibles**: [43.9, 45.8]
- **Neto mas cercano**: 34.2 (dif 4.8)
- **Stacks**: BTN=67.5, SB=137.6, BB=50.0, UTG=148.0, MP=79.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | BTN f 0.0 | SB b 5.0 | BB r 9.0 | SB c 9.0 | MP x 0.0
- **flop**: SB x 0.0 | BB b 6.0 | MP c 0 | SB c 5.9
- **turn**: SB x 0.0 | MP x 0.0 | BB b 9.7 | SB f 0.0

### H_0037 - 2026-07-28

- **Pot declarado**: 18.5
- **Combinaciones**: 2
- **Netos posibles**: [18.73, 21.57]
- **Brutos posibles**: [31.73, 34.58]
- **Neto mas cercano**: 18.73 (dif 0.23)
- **Stacks**: CO=59.0, BTN=136.7, SB=88.3, BB=166.0, UTG=80.2, MP=52.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB r 5.0 | MP c 5.0 | CO c 5.0
- **flop**: BB x 0.0 | MP b 2.0 | CO r 15.0 | BB f 0.0

### H_0049 - 2026-07-28

- **Pot declarado**: 8.1
- **Combinaciones**: 1
- **Netos posibles**: [11.88]
- **Brutos posibles**: [11.88]
- **Neto mas cercano**: 11.88 (dif 3.78)
- **Stacks**: CO=47.0, BTN=143.7, SB=85.9, BB=168.4, UTG=41.9, MP=102.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP p 1.0 | UTG f 0.0 | MP x 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | MP x 0.0
- **turn**: BB b 1.0 | MP c 1.0
- **river**: BB b 4.0 | MP c 0

### H_0053 - 2026-07-28

- **Pot declarado**: 11.2
- **Combinaciones**: 2
- **Netos posibles**: [7.79]
- **Brutos posibles**: [9.29, 10.29]
- **Neto mas cercano**: 7.79 (dif -3.41)
- **Stacks**: MP=49.0, CO=143.2, BTN=86.9, SB=174.3, BB=36.7, UTG=111.2
- **Acciones**:
- **preflop**: BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB p 0.5 | BB r 2.0
- **flop**: SB x 0.0 | BB x 0.0
- **turn**: SB b 3.6 | BB c 2.9
- **river**: SB x 0.0 | BB x 0.0

### H_0054 - 2026-07-28

- **Pot declarado**: 3.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [6.5]
- **Neto mas cercano**: 2.5 (dif -1.0)
- **Stacks**: CO=50.0, BTN=140.7, SB=87.4, BB=175.3, UTG=36.7, MP=111.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN b 5.0 | SB f 0.0 | BB f 0.0

### H_0056 - 2026-07-28

- **Pot declarado**: 9.0
- **Combinaciones**: 1
- **Netos posibles**: [8.07]
- **Brutos posibles**: [8.07]
- **Neto mas cercano**: 8.07 (dif -0.93)
- **Stacks**: BB=145.7, UTG=88.4, MP=175.3, BTN=20.0, SB=123.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | SB f 0.5 | BTN x 0.0 | BB x 0.0
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB b 1.2 | BTN c 1.2
- **river**: BB b 2.3 | BTN c 2.3 | BB c 2.3

### H_0058 - 2026-07-28

- **Pot declarado**: 37.8
- **Combinaciones**: 1
- **Netos posibles**: [20.43]
- **Brutos posibles**: [35.73]
- **Neto mas cercano**: 20.43 (dif -17.37)
- **Stacks**: MP=145.7, BTN=87.4, SB=175.8, BB=19.6, UTG=106.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.5 | MP f 0.0 | BTN f 0.0 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | UTG b 1.7 | BB c 1.7
- **turn**: BB x 0.0 | UTG b 6.3 | BB c 6.3
- **river**: BB x 0.0 | UTG b 15.3

### H_0060 - 2026-07-28

- **Pot declarado**: 1.0
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [2.38]
- **Neto mas cercano**: 2.38 (dif 1.38)
- **Stacks**: BTN=19.0, SB=144.7, BB=87.4, UTG=176.8, MP=19.6, CO=106.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | SB f 0.0 | CO c 0 | BB x 0.0

### H_0074 - 2026-07-29

- **Pot declarado**: 75.4
- **Combinaciones**: 2
- **Netos posibles**: [18.52]
- **Brutos posibles**: [47.73, 50.73]
- **Neto mas cercano**: 18.52 (dif -56.88)
- **Stacks**: UTG=38.2, MP=140.1, CO=99.9, BTN=141.1, SB=29.7, BB=31.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 3.0 | MP f 0.0 | CO f 0.0 | BTN r 9.0 | SB f 0.0 | BB f 0.0 | UTG r 38.2
- **flop**: BTN x 0.0
- **turn**: BTN x 0.0
- **river**: BTN x 0.0

### H_0078 - 2026-07-29

- **Pot declarado**: 40.7
- **Combinaciones**: 2
- **Netos posibles**: [33.44, 36.29]
- **Brutos posibles**: [37.24, 40.09]
- **Neto mas cercano**: 36.29 (dif -4.41)
- **Stacks**: SB=52.2, BB=159.0, UTG=101.4, MP=113.7, CO=21.5, BTN=18.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB c 1.0 | BB r 6.0 | BTN c 6.0 | SB c 6.0
- **flop**: SB x 0.0 | BB b 8.6 | BTN r 12.4
- **turn**: BB x 0.0
- **river**: BB x 0.0

### H_0080 - 2026-07-29

- **Pot declarado**: 24.7
- **Combinaciones**: 2
- **Netos posibles**: [5.7]
- **Brutos posibles**: [15.7, 16.2]
- **Neto mas cercano**: 5.7 (dif -19.0)
- **Stacks**: UTG=53.2, MP=146.8, CO=101.4, BTN=113.7, SB=12.5, BB=19.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 2.5 | CO f 0.0 | BTN f 0.0 | SB r 12.5 | BB x 0.0
- **flop**: MP x 0.0
- **turn**: MP x 0.0
- **river**: MP x 0.0

### H_0085 - 2026-07-29

- **Pot declarado**: 26.5
- **Combinaciones**: 2
- **Netos posibles**: [143.0, 148.0]
- **Brutos posibles**: [183.7, 188.7]
- **Neto mas cercano**: 143.0 (dif 116.5)
- **Stacks**: BB=35.3, UTG=135.1, MP=111.0, CO=118.7, BTN=20.0, SB=14.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.5 | MP f 0.0 | CO r 9.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | UTG r 22.0 | CO c 22.0
- **flop**: UTG b 21.6 | CO c 21.6
- **turn**: UTG x 0.0 | CO b 28.4 | UTG c 28.4
- **river**: UTG x 0.0 | CO b 40.7

### H_0093 - 2026-07-29

- **Pot declarado**: 12.1
- **Combinaciones**: 1
- **Netos posibles**: [21.57]
- **Brutos posibles**: [21.57]
- **Neto mas cercano**: 21.57 (dif 9.47)
- **Stacks**: MP=41.5, CO=122.5, BTN=71.0, SB=136.3, BB=34.9, UTG=15.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 3.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB c 0
- **flop**: BB x 0.0 | MP b 8.1 | BB c 0 | BB c 3.1
- **turn**: BB x 0.0 | MP x 0.0
- **river**: BB x 0.0 | MP x 0.0

### H_0102 - 2026-07-29

- **Pot declarado**: 10.0
- **Combinaciones**: 2
- **Netos posibles**: [2.38]
- **Brutos posibles**: [11.38, 12.38]
- **Neto mas cercano**: 2.38 (dif -7.62)
- **Stacks**: SB=39.7, BB=129.2, UTG=72.5, MP=132.3, CO=24.7, BTN=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 4.0 | SB f 0.5 | BB r 5.0 | BTN x 0.0
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB b 5.0 | BTN f 0.0

### H_0103 - 2026-07-29

- **Pot declarado**: 2.0
- **Combinaciones**: 1
- **Netos posibles**: [1.5]
- **Brutos posibles**: [1.5]
- **Neto mas cercano**: 1.5 (dif -0.5)
- **Stacks**: SB=40.7, BB=128.2, UTG=72.5, MP=132.3, BTN=24.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB f 0.0

### H_0112 - 2026-07-29

- **Pot declarado**: 2.4
- **Combinaciones**: 1
- **Netos posibles**: [1.43]
- **Brutos posibles**: [1.43]
- **Neto mas cercano**: 1.43 (dif -0.97)
- **Stacks**: CO=35.0, BTN=124.2, SB=64.7, BB=106.1, UTG=53.4, MP=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | MP x 0.0 | BB x 0.0
- **flop**: BB x 0.0 | MP x 0.0
- **turn**: BB x 0.0 | MP x 0.0
- **river**: BB x 0.0 | MP x 0.0

### H_0117 - 2026-07-29

- **Pot declarado**: 3.3
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [5.67]
- **Neto mas cercano**: 2.38 (dif -0.92)
- **Stacks**: MP=51.7, BTN=113.0, SB=65.0, BB=102.1, UTG=53.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG p 1.0 | UTG x 0.0 | BTN f 0.0 | SB f 0.0 | MP x 0.0 | BB x 0.0
- **flop**: BB x 0.0 | MP x 0.0 | UTG b 3.3 | MP f 0.0 | BB f 0.0

### H_0129 - 2026-07-29

- **Pot declarado**: 39.0
- **Combinaciones**: 1
- **Netos posibles**: [15.2]
- **Brutos posibles**: [28.2]
- **Neto mas cercano**: 15.2 (dif -23.8)
- **Stacks**: SB=27.9, BB=101.3, UTG=58.5, MP=98.5, CO=73.4, BTN=18.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.0 | MP f 0.0 | CO f 0.0 | BTN r 3.0 | SB c 3.0 | BB f 0.0 | UTG c 3.0
- **flop**: SB x 0.0 | UTG x 0.0 | BTN b 3.0 | SB r 16.0 | UTG f 0.0 | BTN f 0.0
- **turn**: SB x 0.0

### H_0138 - 2026-07-29

- **Pot declarado**: 4.5
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [7.5]
- **Neto mas cercano**: 3.5 (dif -1.0)
- **Stacks**: UTG=35.1, MP=98.5, BTN=20.0, SB=95.2, BB=92.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 5.0 | BTN f 0.0 | SB f 0.5 | BB f 0.0 | UTG f 0.0

### H_0139 - 2026-07-29

- **Pot declarado**: 1.9
- **Combinaciones**: 1
- **Netos posibles**: [1.43]
- **Brutos posibles**: [5.42]
- **Neto mas cercano**: 1.43 (dif -0.47)
- **Stacks**: UTG=35.1, BTN=98.5, SB=96.2, BB=91.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB p 1.0 | BB x 0.0 | UTG f 0.0 | BTN f 0.0 | SB x 0.0
- **flop**: SB x 0.0 | BB x 0.0
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB x 0.0 | BB b 4.0 | SB f 0.0

### H_0145 - 2026-07-29

- **Pot declarado**: 23.7
- **Combinaciones**: 2
- **Netos posibles**: [52.0, 53.0]
- **Brutos posibles**: [81.0, 82.0]
- **Neto mas cercano**: 52.0 (dif 28.3)
- **Stacks**: SB=101.2, BB=79.7, UTG=95.1, MP=143.7, BTN=61.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 2.5 | BTN c 2.5 | SB r 15.0 | BB f 0.0 | MP f 0.0 | BTN c 15.0
- **flop**: SB b 10.5 | BTN c 10.5
- **turn**: SB b 29.0

### H_0157 - 2026-07-30

- **Pot declarado**: 2.4
- **Combinaciones**: 1
- **Netos posibles**: [12.35]
- **Brutos posibles**: [16.35]
- **Neto mas cercano**: 12.35 (dif 9.95)
- **Stacks**: SB=39.0, BB=82.6, UTG=49.5, MP=66.0, CO=91.4, BTN=170.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN b 2.0 | SB c 2.0 | UTG c 2.0 | MP c 2.0 | BB x 0.0
- **flop**: SB x 0.0 | UTG x 0.0 | MP b 1.0 | BTN c 1.0 | SB c 1.0 | UTG c 1.0
- **turn**: SB x 0.0 | UTG x 0.0 | BTN x 0.0 | MP b 4.0 | BTN f 0.0 | SB f 0.0 | UTG f 0.0

### H_0158 - 2026-07-30

- **Pot declarado**: 17.1
- **Combinaciones**: 1
- **Netos posibles**: [23.27]
- **Brutos posibles**: [36.08]
- **Neto mas cercano**: 23.27 (dif 6.17)
- **Stacks**: BTN=36.0, SB=46.5, BB=75.4, UTG=91.4, MP=167.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 2.0 | BTN r 8.0 | SB f 0.0 | BB c 1.0 | MP c 8.0 | BB f 0.0
- **flop**: MP x 0.0 | BTN b 12.8 | MP f 0.0

### H_0169 - 2026-07-30

- **Pot declarado**: 3.8
- **Combinaciones**: 1
- **Netos posibles**: [1.9]
- **Brutos posibles**: [4.8]
- **Neto mas cercano**: 1.9 (dif -1.9)
- **Stacks**: MP=100.0, SB=43.2, BB=143.0, UTG=88.9, BTN=130.3
- **Acciones**:
- **preflop**: BB p 1.0 | BTN f 0.0 | SB p 0.5 | SB c 1.0 | BB c 1.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | MP b 2.9 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0176 - 2026-07-30

- **Pot declarado**: 3.5
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [7.0, 7.5]
- **Neto mas cercano**: 3.0 (dif -0.5)
- **Stacks**: BB=112.0, UTG=18.8, BTN=135.8, SB=92.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | BTN c 1.0 | SB b 5.0 | BB f 0.0 | BTN f 0.0

### H_0180 - 2026-07-30

- **Pot declarado**: 31.8
- **Combinaciones**: 1
- **Netos posibles**: [30.88]
- **Brutos posibles**: [40.38]
- **Neto mas cercano**: 30.88 (dif -0.92)
- **Stacks**: BB=111.5, UTG=21.5, MP=33.5, CO=131.8, BTN=95.1, SB=19.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO c 1.0 | BTN b 7.0 | SB f 0.0 | BB f 0.0 | UTG c 7.0 | CO c 7.0
- **flop**: UTG x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: UTG x 0.0 | CO b 5.0 | BTN f 0.0 | UTG c 5.0
- **river**: UTG b 9.5

### H_0185 - 2026-07-30

- **Pot declarado**: 23.4
- **Combinaciones**: 1
- **Netos posibles**: [22.8]
- **Brutos posibles**: [27.8]
- **Neto mas cercano**: 22.8 (dif -0.6)
- **Stacks**: UTG=114.7, MP=11.3, CO=26.5, BTN=126.7, SB=106.1, BB=25.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP p 1.0 | MP x 0.0 | CO f 0.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP b 5.0 | BTN c 5.0 | SB f 0.0 | BB f 0.0
- **turn**: MP b 5.0 | BTN r 10.0
- **river**: MP x 0.0 | BTN x 0.0

### H_0188 - 2026-07-30

- **Pot declarado**: 120.3
- **Combinaciones**: 1
- **Netos posibles**: [118.3]
- **Brutos posibles**: [118.3]
- **Neto mas cercano**: 118.3 (dif -2.0)
- **Stacks**: BTN=113.2, SB=11.0, BB=58.5, UTG=110.6, MP=105.1, CO=26.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 4.0 | MP r 9.0 | CO f 0.0 | BTN f 0.0 | SB c 9.0 | BB f 0.0 | UTG c 9.0
- **flop**: SB x 0.0 | UTG b 7.5 | MP c 7.5
- **turn**: SB x 0.0 | UTG b 7.5 | MP r 15.0 | UTG c 15.0
- **river**: SB x 0.0 | UTG x 0.0 | MP b 23.9 | UTG c 23.9

### H_0200 - 2026-07-31

- **Pot declarado**: 18.2
- **Combinaciones**: 1
- **Netos posibles**: [19.19]
- **Brutos posibles**: [19.19]
- **Neto mas cercano**: 19.19 (dif 0.99)
- **Stacks**: BTN=111.2, SB=22.7, BB=100.7, UTG=126.0, MP=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.5 | MP f 0.0 | BTN f 0.0 | SB c 1.5 | BB f 0.0
- **flop**: SB x 0.0 | UTG x 0.0
- **turn**: SB x 0.0 | UTG b 2.4 | SB c 2.4
- **river**: SB x 0.0 | UTG b 4.7 | SB c 4.7

### H_0213 - 2026-07-31

- **Pot declarado**: 8.1
- **Combinaciones**: 1
- **Netos posibles**: [7.12]
- **Brutos posibles**: [11.62]
- **Neto mas cercano**: 7.12 (dif -0.98)
- **Stacks**: UTG=127.2, BTN=91.7, SB=121.1, BB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 3.0 | BTN c 3.0 | SB f 0.0 | BB f 0.0
- **flop**: UTG b 4.5 | BTN f 0.0

### H_0236 - 2026-07-31

- **Pot declarado**: 2.5
- **Combinaciones**: 1
- **Netos posibles**: [1.5]
- **Brutos posibles**: [1.5]
- **Neto mas cercano**: 1.5 (dif -1.0)
- **Stacks**: BB=119.5, UTG=107.1, MP=51.5, CO=79.3, BTN=100.7, SB=95.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0

### H_0240 - 2026-07-31

- **Pot declarado**: 199.0
- **Combinaciones**: 4
- **Netos posibles**: [178.9, 210.1]
- **Brutos posibles**: [178.9, 210.1]
- **Neto mas cercano**: 210.1 (dif 11.1)
- **Stacks**: CO=107.5, BTN=51.0, BB=100.7
- **Acciones**:
- **preflop**: BB p 1.0 | CO b 3.0 | BTN f 0.0 | BB c 3.0
- **flop**: BB x 0.0 | CO x 0.0
- **turn**: BB x 0.0 | CO b 2.1 | BB c 2.1
- **river**: BB x 0.0 | CO b 7.8 | BB r 15.6 | CO r 54.4 | BB r 85.6 | CO c 85.6

### H_0243 - 2026-07-31

- **Pot declarado**: 19.6
- **Combinaciones**: 1
- **Netos posibles**: [21.93]
- **Brutos posibles**: [34.99]
- **Neto mas cercano**: 21.93 (dif 2.33)
- **Stacks**: BTN=94.0, SB=207.3, BB=56.6, UTG=100.5, MP=114.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN b 3.0 | SB f 0.0 | BB c 3.0
- **flop**: BB x 0.0 | BTN b 3.1 | BB c 3.1
- **turn**: BB x 0.0 | BTN b 4.93 | BB r 18.0 | BTN f 0.0

### H_0259 - 2026-07-31

- **Pot declarado**: 6.2
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [5.97]
- **Neto mas cercano**: 2.38 (dif -3.82)
- **Stacks**: UTG=145.5, MP=32.3, BTN=102.2, SB=123.2, BB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 1.5 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | UTG x 0.0
- **flop**: UTG x 0.0 | MP x 0.0
- **turn**: UTG b 3.1 | MP f 0.0

### H_0260 - 2026-07-31

- **Pot declarado**: 4.5
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [8.5]
- **Neto mas cercano**: 3.5 (dif -1.0)
- **Stacks**: BB=149.2, UTG=29.8, MP=102.2, CO=25.0, BTN=122.7, SB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | BTN b 6.0 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0263 - 2026-07-31

- **Pot declarado**: 6.2
- **Combinaciones**: 2
- **Netos posibles**: [5.22, 7.12]
- **Brutos posibles**: [8.32, 10.22]
- **Neto mas cercano**: 7.12 (dif 0.92)
- **Stacks**: MP=147.7, BTN=26.8, SB=104.7, BB=126.2, UTG=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | SB f 0.0 | BTN x 0.0 | BB r 2.5 | BTN c 2.5
- **flop**: BB x 0.0 | BTN b 3.1 | BB f 0.0

### H_0284 - 2026-07-31

- **Pot declarado**: 2.9
- **Combinaciones**: 1
- **Netos posibles**: [1.9]
- **Brutos posibles**: [5.9]
- **Neto mas cercano**: 1.9 (dif -1.0)
- **Stacks**: MP=160.7, CO=20.0, BTN=105.1, SB=35.2, BB=122.2, UTG=114.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB c 1.0 | CO x 0.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | CO b 4.0 | SB f 0.0 | BB f 0.0

### H_0291 - 2026-07-31

- **Pot declarado**: 4.5
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [8.5]
- **Neto mas cercano**: 3.5 (dif -1.0)
- **Stacks**: UTG=159.2, MP=13.5, CO=111.6, BTN=22.3, SB=152.7, BB=113.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO r 6.0 | BTN f 0.0 | SB f 0.5 | BB f 0.0 | MP f 0.0

### H_0293 - 2026-07-31

- **Pot declarado**: 22.8
- **Combinaciones**: 2
- **Netos posibles**: [10.45, 11.4]
- **Brutos posibles**: [17.45, 18.4]
- **Neto mas cercano**: 11.4 (dif -11.4)
- **Stacks**: SB=160.7, BB=11.5, UTG=115.1, MP=21.3, CO=152.2, BTN=112.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | BTN f 0.0 | SB b 5.0 | BB c 5.0 | MP f 0.0
- **flop**: SB b 7.0
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB x 0.0 | BB x 0.0

### H_0303 - 2026-07-31

- **Pot declarado**: 4.5
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [8.5]
- **Neto mas cercano**: 3.5 (dif -1.0)
- **Stacks**: BB=166.5, UTG=49.9, MP=124.6, CO=20.0, BTN=152.5, SB=130.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP r 6.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 1.0 | UTG f 0.0

### H_0321 - 2026-08-01

- **Pot declarado**: 109.0
- **Combinaciones**: 1
- **Netos posibles**: [39.8]
- **Brutos posibles**: [80.7]
- **Neto mas cercano**: 39.8 (dif -69.2)
- **Stacks**: SB=111.4, BB=52.0, UTG=120.0, MP=198.4, BTN=199.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 3.0 | MP f 0.0 | BTN r 7.0 | SB f 0.0 | BB c 7.0 | UTG c 7.0
- **flop**: BB x 0.0 | UTG x 0.0 | BTN x 0.0
- **turn**: UTG x 0.0 | BB b 10.2 | UTG f 0.0 | BTN r 51.1
- **river**: BB x 0.0 | BTN x 0.0

### H_0322 - 2026-08-01

- **Pot declarado**: 7.8
- **Combinaciones**: 1
- **Netos posibles**: [8.74]
- **Brutos posibles**: [8.74]
- **Neto mas cercano**: 8.74 (dif 0.94)
- **Stacks**: BTN=110.9, SB=113.0, BB=198.4, UTG=256.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 2.5 | BTN f 0.0 | SB c 1.5 | BB x 0.0
- **flop**: SB x 0.0 | UTG b 1.6 | SB c 1.6
- **turn**: SB x 0.0 | UTG x 0.0
- **river**: SB x 0.0 | UTG x 0.0

### H_0330 - 2026-08-09

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Neto mas cercano**: 2.0 (dif -1.0)
- **Stacks**: UTG=20.1, BTN=60.7, SB=123.7, BB=69.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0

### H_0356 - 2026-09-10

- **Pot declarado**: 10.0
- **Combinaciones**: 1
- **Netos posibles**: [19.48]
- **Brutos posibles**: [19.48]
- **Neto mas cercano**: 19.48 (dif 9.48)
- **Stacks**: BB=97.0, MP=129.7, CO=100.8, BTN=82.3, SB=49.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 5.0 | BTN f 0.0 | SB f 0.0 | BB c 5.0
- **flop**: BB x 0.0 | CO x 0.0
- **turn**: BB x 0.0 | CO x 0.0
- **river**: BB b 5.0 | CO c 5.0

### H_0357 - 2026-09-10

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [4.0, 4.5]
- **Neto mas cercano**: 3.0 (dif 1.5)
- **Stacks**: SB=87.0, BB=129.7, CO=110.2, BTN=82.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB b 0.5 | CO f 0.0 | BTN f 0.0 | SB b 2.5 | BB f 0.0

### H_0358 - 2026-09-10

- **Pot declarado**: 5.2
- **Combinaciones**: 1
- **Netos posibles**: [10.16]
- **Brutos posibles**: [10.16]
- **Neto mas cercano**: 10.16 (dif 4.96)
- **Stacks**: BTN=88.0, SB=128.7, BB=110.2, CO=82.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 2.5 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB x 0.0 | BTN b 2.6 | BB c 2.6
- **river**: BB x 0.0 | BTN x 0.0

### H_0362 - 2026-09-10

- **Pot declarado**: 7.8
- **Combinaciones**: 1
- **Netos posibles**: [10.16]
- **Brutos posibles**: [16.86]
- **Neto mas cercano**: 10.16 (dif 2.36)
- **Stacks**: BTN=93.1, SB=127.2, BB=104.1, MP=82.8, CO=101.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN r 2.5 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB b 2.6 | BTN c 2.6
- **river**: BB b 6.7 | BTN f 0.0

### H_0369 - 2026-09-13

- **Pot declarado**: 135.7
- **Combinaciones**: 1
- **Netos posibles**: [129.8]
- **Brutos posibles**: [129.8]
- **Neto mas cercano**: 129.8 (dif -5.9)
- **Stacks**: CO=99.8, BTN=57.4, SB=120.0, BB=80.6, UTG=70.888, MP=67.488
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO f 0.0 | BTN c 1.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG b 1.0 | MP r 2.0 | BTN f 0.0 | BB r 5.0 | UTG f 0.0 | MP c 5.0 | BB c 3.0
- **turn**: BB b 10.2 | MP r 20.4 | BB c 20.4
- **river**: BB x 0.0 | MP b 38.0 | BB c 38.0

### H_0396 - 2026-09-13

- **Pot declarado**: 10.9
- **Combinaciones**: 2
- **Netos posibles**: [4.37]
- **Brutos posibles**: [10.07, 10.57]
- **Neto mas cercano**: 4.37 (dif -6.53)
- **Stacks**: BTN=115.7, SB=158.8, BB=60.1, MP=82.5, CO=145.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 2.0 | BB x 0.0
- **flop**: SB b 1.3 | BB c 1.3
- **turn**: SB b 4.7 | BB f 0.0

### H_0403 - 2026-09-13

- **Pot declarado**: 42.5
- **Combinaciones**: 1
- **Netos posibles**: [41.7]
- **Brutos posibles**: [41.7]
- **Neto mas cercano**: 41.7 (dif -0.8)
- **Stacks**: MP=111.5, CO=164.4, BTN=58.6, SB=81.5, BB=145.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.0 | BTN c 2.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | CO b 2.1 | BTN c 2.1 | BB f 0.0
- **turn**: CO x 0.0 | BTN b 4.6 | CO c 4.6
- **river**: CO x 0.0 | BTN b 12.5 | CO c 12.5

### H_0420 - 2026-09-13

- **Pot declarado**: 16.3
- **Combinaciones**: 2
- **Netos posibles**: [22.61, 23.56]
- **Brutos posibles**: [39.61, 40.56]
- **Neto mas cercano**: 22.61 (dif 6.31)
- **Stacks**: BB=101.9, MP=175.0, CO=10.0, BTN=44.4, SB=245.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB c 3.0
- **flop**: SB b 1.9 | BB c 1.9
- **turn**: SB x 0.0 | BB b 7.0 | SB c 7.0
- **river**: SB b 17.0 | BB f 0.0

### H_0425 - 2026-09-13

- **Pot declarado**: 0.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 2.0)
- **Stacks**: MP=95.5, CO=173.5, BTN=8.0, SB=21.0, BB=252.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 2.5 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0445 - 2026-09-13

- **Pot declarado**: 140.0
- **Combinaciones**: 1
- **Netos posibles**: [177.0]
- **Brutos posibles**: [177.0]
- **Neto mas cercano**: 177.0 (dif 37.0)
- **Stacks**: BTN=87.5, SB=29.0, BB=43.6, MP=106.0, CO=55.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | BTN r 4.0 | SB f 0.0 | BB c 4.0 | MP c 4.0
- **flop**: BB x 0.0 | MP x 0.0 | BTN x 0.0
- **turn**: BB f 0.0 | MP b 11.9 | BTN r 26.0 | MP c 26.0
- **river**: MP b 20.5 | BTN r 57.5 | MP c 57.5

### H_0455 - 2026-09-14

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: MP=81.9, CO=101.0, BTN=71.4, SB=103.5, BB=60.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP b 2.5 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0512 - 2026-09-14

- **Pot declarado**: 6.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [5.5]
- **Neto mas cercano**: 2.5 (dif -4.0)
- **Stacks**: SB=110.5, BB=43.6, CO=37.7, BTN=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 4.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0519 - 2026-09-14

- **Pot declarado**: 18.5
- **Combinaciones**: 1
- **Netos posibles**: [12.82]
- **Brutos posibles**: [17.43]
- **Neto mas cercano**: 12.82 (dif -5.68)
- **Stacks**: CO=105.0, BTN=105.1, SB=61.4, BB=19.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 3.0 | BTN f 0.0 | SB f 0.0 | BB c 3.0
- **flop**: BB b 3.5 | CO c 3.5
- **turn**: BB b 4.6 | CO f 0.0

### H_0521 - 2026-09-14

- **Pot declarado**: 9.0
- **Combinaciones**: 1
- **Netos posibles**: [10.45]
- **Brutos posibles**: [20.45]
- **Neto mas cercano**: 10.45 (dif 1.45)
- **Stacks**: SB=97.4, BB=48.0, MP=102.1, CO=60.9, BTN=31.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB b 0.5 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | MP x 0.0 | CO b 2.0 | BB c 2.0 | MP c 2.0
- **turn**: BB b 10.0 | MP f 0.0 | CO f 0.0

### H_0526 - 2026-09-14

- **Pot declarado**: 8.8
- **Combinaciones**: 1
- **Netos posibles**: [5.7]
- **Brutos posibles**: [7.9]
- **Neto mas cercano**: 5.7 (dif -3.1)
- **Stacks**: BB=96.9, MP=None, CO=109.9, BTN=16.8, SB=34.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | CO b 1.0 | SB c 1.0 | BB c 1.0 | MP f 0.0
- **turn**: SB x 0.0 | BB x 0.0 | CO b 2.2 | SB f 0.0 | BB f 0.0

### H_0534 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=162.0, BTN=69.4, SB=104.3, BB=103.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO b 2.5 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0537 - 2026-09-15

- **Pot declarado**: 6.7
- **Combinaciones**: 1
- **Netos posibles**: [13.25]
- **Brutos posibles**: [16.55]
- **Neto mas cercano**: 13.25 (dif 6.55)
- **Stacks**: BTN=161.5, SB=68.4, BB=103.8, CO=104.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 3.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | CO b 3.3 | SB r 6.6 | CO f 0.0

### H_0544 - 2026-09-15

- **Pot declarado**: 8.2
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [7.08]
- **Neto mas cercano**: 2.38 (dif -5.82)
- **Stacks**: SB=162.5, BB=55.0, UTG=69.0, MP=100.0, CO=109.2, BTN=43.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.2 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | BTN b 3.5 | BB f 0.0

### H_0546 - 2026-09-15

- **Pot declarado**: 0.5
- **Combinaciones**: 4
- **Netos posibles**: [102.6, 108.6]
- **Brutos posibles**: [102.6, 108.6]
- **Neto mas cercano**: 102.6 (dif 102.1)
- **Stacks**: CO=162.0, BTN=52.3, SB=69.5, BB=100.0, UTG=109.2, MP=45.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 3.0 | SB f 0.0 | BB r 11.0 | BTN r 52.3 | BB c 40.3
- **flop**: BB x 0.0
- **turn**: BB x 0.0

### H_0548 - 2026-09-15

- **Pot declarado**: 18.6
- **Combinaciones**: 1
- **Netos posibles**: [25.65]
- **Brutos posibles**: [25.65]
- **Neto mas cercano**: 25.65 (dif 7.05)
- **Stacks**: UTG=162.0, MP=50.0, CO=70.9, BTN=149.3, SB=108.2, BB=45.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.5 | MP c 2.5 | CO f 0.0 | BTN f 0.0 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | MP x 0.0
- **turn**: SB x 0.0 | BB b 4.8 | UTG c 4.8 | MP f 0.0 | SB f 0.0
- **river**: BB x 0.0 | UTG b 3.7 | BB c 3.7

### H_0554 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: UTG=142.5, MP=58.6, CO=64.9, BTN=149.3, SB=106.2, BB=59.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.5 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0581 - 2026-09-15

- **Pot declarado**: 27.3
- **Combinaciones**: 1
- **Netos posibles**: [26.22]
- **Brutos posibles**: [26.22]
- **Neto mas cercano**: 26.22 (dif -1.08)
- **Stacks**: CO=100.0, BTN=11.3, SB=27.4, BB=42.1, UTG=106.2, MP=22.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN r 2.0 | SB c 2.0 | BB f 0.0 | MP c 2.0 | CO c 2.0
- **flop**: SB x 0.0 | MP b 3.0 | CO f 0.0 | BTN r 9.3 | SB f 0.0 | MP c 9.3
- **turn**: MP x 0.0

### H_0585 - 2026-09-15

- **Pot declarado**: 16.2
- **Combinaciones**: 2
- **Netos posibles**: [18.81, 20.71]
- **Brutos posibles**: [30.81, 32.71]
- **Neto mas cercano**: 18.81 (dif 2.61)
- **Stacks**: BB=101.8, MP=21.9, CO=40.6, BTN=104.7, SB=39.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | SB c 1.0 | BB r 4.0 | MP c 4.0 | SB f 0.0
- **flop**: BB b 5.4 | MP c 5.4
- **turn**: BB b 12.0 | MP f 0.0

### H_0588 - 2026-09-15

- **Pot declarado**: 15.0
- **Combinaciones**: 2
- **Netos posibles**: [9.69, 11.59]
- **Brutos posibles**: [12.69, 14.59]
- **Neto mas cercano**: 11.59 (dif -3.41)
- **Stacks**: BTN=112.5, SB=13.0, BB=40.6, CO=37.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 1.5 | SB c 1.5
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
- **flop**: BB x 0.0

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

### H_0594 - 2026-09-15

- **Pot declarado**: 4.0
- **Combinaciones**: 1
- **Netos posibles**: [2.0]
- **Brutos posibles**: [3.5]
- **Neto mas cercano**: 2.0 (dif -2.0)
- **Stacks**: BTN=113.6, BB=44.4
- **Acciones**:
- **preflop**: BB p 1.0 | BTN r 2.5 | BB f 0.0

### H_0595 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [1.0]
- **Brutos posibles**: [1.0]
- **Neto mas cercano**: 1.0 (dif -0.5)
- **Stacks**: BB=114.6, BTN=43.4
- **Acciones**:
- **preflop**: BB p 1.0 | BTN f 0.0

### H_0612 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: MP=224.2, CO=113.7, BTN=12.0, SB=127.3, BB=97.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 2.5 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0642 - 2026-09-15

- **Pot declarado**: 14.6
- **Combinaciones**: 1
- **Netos posibles**: [14.84]
- **Brutos posibles**: [22.43]
- **Neto mas cercano**: 14.84 (dif 0.24)
- **Stacks**: SB=254.0, BB=101.0, MP=13.7, CO=119.8, BTN=92.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 2.1 | MP c 2.1 | SB c 2.1
- **turn**: SB x 0.0 | BB x 0.0 | MP x 0.0
- **river**: SB b 3.0 | BB f 0.0 | MP r 10.6 | SB f 0.0

### H_0643 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: BTN=247.8, SB=100.0, BB=22.2, MP=119.8, CO=92.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN r 2.5 | SB f 0.0 | BB f 0.0

### H_0644 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=249.3, BTN=100.0, SB=21.2, BB=92.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0676 - 2026-09-15

- **Pot declarado**: 34.8
- **Combinaciones**: 1
- **Netos posibles**: [28.99]
- **Brutos posibles**: [28.99]
- **Neto mas cercano**: 28.99 (dif -5.81)
- **Stacks**: BB=99.0, MP=103.8, CO=45.0, BTN=47.4, SB=34.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 2.4 | MP c 2.4 | CO f 0.0 | BTN c 2.4 | SB f 0.0
- **river**: BB b 5.8 | MP c 5.8 | BTN c 11.6 | BB f 0.0 | MP f 0.0

### H_0677 - 2026-09-15

- **Pot declarado**: 17.8
- **Combinaciones**: 1
- **Netos posibles**: [22.99]
- **Brutos posibles**: [22.99]
- **Neto mas cercano**: 22.99 (dif 5.19)
- **Stacks**: SB=89.8, BB=94.6, MP=44.0, CO=66.3, BTN=33.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | MP b 2.2 | CO f 0.0 | SB c 2.2 | BB f 0.0
- **turn**: SB b 2.0 | MP c 2.0
- **river**: SB b 5.9 | MP c 5.9

### H_0678 - 2026-09-15

- **Pot declarado**: 5.5
- **Combinaciones**: 1
- **Netos posibles**: [9.03]
- **Brutos posibles**: [12.03]
- **Neto mas cercano**: 9.03 (dif 3.53)
- **Stacks**: BTN=78.7, SB=93.6, BB=72.2, UTG=61.9, MP=65.3, CO=33.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.0 | MP f 0.0 | CO c 2.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0
- **flop**: UTG x 0.0 | CO b 2.0 | UTG c 2.0
- **turn**: UTG x 0.0 | CO b 3.0 | UTG f 0.0

### H_0689 - 2026-09-15

- **Pot declarado**: 11.5
- **Combinaciones**: 1
- **Netos posibles**: [13.78]
- **Brutos posibles**: [13.78]
- **Neto mas cercano**: 13.78 (dif 2.28)
- **Stacks**: BTN=78.2, SB=100.0, BB=57.6, UTG=42.9, MP=98.7, CO=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG x 0.0 | MP x 0.0 | CO b 1.0 | BTN c 1.0 | BB f 0.0 | UTG c 1.0 | MP c 1.0
- **turn**: UTG x 0.0 | MP x 0.0 | CO x 0.0 | BTN x 0.0
- **river**: UTG x 0.0 | MP b 2.5 | CO f 0.0 | BTN c 2.5 | UTG f 0.0

### H_0697 - 2026-09-15

- **Pot declarado**: 7.0
- **Combinaciones**: 1
- **Netos posibles**: [3.5]
- **Brutos posibles**: [6.0]
- **Neto mas cercano**: 3.5 (dif -3.5)
- **Stacks**: SB=85.5, BB=125.1, UTG=51.1, MP=100.0, CO=None, BTN=23.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN r 3.5 | SB f 0.0 | BB f 0.0 | UTG f 0.0

### H_0726 - 2026-09-15

- **Pot declarado**: 11.0
- **Combinaciones**: 1
- **Netos posibles**: [9.12]
- **Brutos posibles**: [9.12]
- **Neto mas cercano**: 9.12 (dif -1.88)
- **Stacks**: MP=109.9, CO=98.5, BTN=100.0, SB=241.8, BB=49.0, UTG=20.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 3.8 | SB c 3.8
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB x 0.0 | BB x 0.0

### H_0739 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [2.5]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: UTG=136.0, MP=102.1, CO=110.3, BTN=182.1, SB=52.6, BB=29.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB f 0.0 | BB f 0.0

### H_0743 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [8.55, 11.4]
- **Brutos posibles**: [11.35, 14.2]
- **Neto mas cercano**: 8.55 (dif 7.05)
- **Stacks**: MP=122.9, CO=98.6, BTN=108.8, SB=193.1, BB=50.1, UTG=35.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 2.0 | BTN f 0.0 | SB c 2.0 | BB r 3.0 | CO c 3.0 | SB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0
- **turn**: SB b 2.8 | BB f 0.0 | CO f 0.0

### H_0757 - 2026-09-15

- **Pot declarado**: 38.6
- **Combinaciones**: 1
- **Netos posibles**: [36.58]
- **Brutos posibles**: [37.98]
- **Neto mas cercano**: 36.58 (dif -2.02)
- **Stacks**: MP=120.3, CO=17.5, BTN=97.3, SB=45.0, BB=229.6, UTG=121.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 3.0 | BTN c 3.0 | SB f 0.0 | BB c 3.0
- **flop**: BB x 0.0 | CO b 3.0 | BTN c 3.0 | BB f 0.0
- **turn**: CO x 0.0 | BTN b 4.9 | CO c 4.9
- **river**: CO x 0.0 | BTN b 8.0 | CO c 6.6

### H_0774 - 2026-09-15

- **Pot declarado**: 32.7
- **Combinaciones**: 2
- **Netos posibles**: [9.05]
- **Brutos posibles**: [28.15, 28.65]
- **Neto mas cercano**: 9.05 (dif -23.65)
- **Stacks**: SB=112.9, UTG=None, BB=113.4, MP=76.1, CO=258.0, BTN=145.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 5.0 | BTN f 0.0 | SB r 6.0 | BB f 0.0
- **flop**: SB x 0.0 | CO x 0.0
- **turn**: SB b 3.1 | CO r 17.2 | SB f 0.0

### H_0797 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.5]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=133.4, BTN=91.2, SB=33.4, BB=170.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN r 3.0 | SB f 0.0 | BB f 0.0

### H_0798 - 2026-09-15

- **Pot declarado**: 41.0
- **Combinaciones**: 2
- **Netos posibles**: [39.14]
- **Brutos posibles**: [40.14, 40.64]
- **Neto mas cercano**: 39.14 (dif -1.86)
- **Stacks**: BB=133.4, CO=92.7, BTN=32.9, SB=169.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB r 2.0 | BB x 0.0
- **flop**: SB b 2.9 | BB c 2.9
- **turn**: SB b 4.7 | BB c 4.7
- **river**: SB x 0.0 | BB b 12.0 | SB c 12.0

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

### H_0855 - 2026-09-16

- **Pot declarado**: 58.5
- **Combinaciones**: 1
- **Netos posibles**: [82.3]
- **Brutos posibles**: [82.3]
- **Neto mas cercano**: 82.3 (dif 23.8)
- **Stacks**: BTN=94.4, SB=51.8, BB=75.9, UTG=109.6, MP=89.2, CO=37.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 3.0 | CO f 0.0 | BTN c 3.0 | SB c 3.0 | BB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | MP x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB x 0.0 | MP x 0.0 | BTN b 5.7 | SB f 0.0 | BB c 5.7 | MP f 0.0
- **river**: BTN b 5.6 | BB r 30.7 | BTN c 30.7

### H_0872 - 2026-09-16

- **Pot declarado**: 30.7
- **Combinaciones**: 2
- **Netos posibles**: [29.68, 31.58]
- **Brutos posibles**: [113.48, 115.38]
- **Neto mas cercano**: 31.58 (dif 0.88)
- **Stacks**: CO=101.5, BTN=130.6, SB=62.5, BB=100.0, UTG=77.3, MP=68.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 4.0 | SB c 4.0
- **flop**: SB x 0.0 | BB b 3.2 | SB c 3.2
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB b 8.0 | BB r 91.8 | SB f 0.0

### H_0896 - 2026-09-16

- **Pot declarado**: 38.6
- **Combinaciones**: 1
- **Netos posibles**: [29.26]
- **Brutos posibles**: [38.86]
- **Neto mas cercano**: 29.26 (dif -9.34)
- **Stacks**: BB=106.5, UTG=121.4, MP=116.1, CO=109.5, BTN=41.3, SB=26.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO f 0.0 | BTN r 2.0 | SB f 0.0 | BB c 2.0 | MP c 2.0
- **flop**: BB x 0.0 | MP x 0.0 | BTN b 3.1 | BB c 3.1 | MP c 3.1
- **turn**: BB x 0.0 | MP x 0.0 | BTN b 5.0 | BB c 5.0 | MP c 5.0
- **river**: BB x 0.0 | MP x 0.0 | BTN b 9.6 | BB f 0.0 | MP f 0.0

### H_0897 - 2026-09-17

- **Pot declarado**: 114.0
- **Combinaciones**: 2
- **Netos posibles**: [269.7, 272.2]
- **Brutos posibles**: [269.7, 272.2]
- **Neto mas cercano**: 269.7 (dif 155.7)
- **Stacks**: BB=100.0, UTG=125.7, MP=326.6, CO=123.5, BTN=80.4, SB=143.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 2.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB r 3.0 | BB f 0.0 | UTG c 2.0 | MP c 2.0 | CO c 2.0 | BTN c 2.0
- **flop**: SB b 7.6 | UTG c 7.6 | MP c 7.6 | CO r 41.8 | BTN f 0.0 | SB f 0.0 | UTG c 41.8 | MP f 0.0
- **turn**: UTG x 0.0 | CO b 78.7 | UTG c 78.7

### H_0901 - 2026-09-17

- **Pot declarado**: 62.0
- **Combinaciones**: 1
- **Netos posibles**: [58.9]
- **Brutos posibles**: [58.9]
- **Neto mas cercano**: 58.9 (dif -3.1)
- **Stacks**: BB=96.0, UTG=28.7, MP=362.9, CO=100.0, BTN=67.7, SB=130.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO c 1.0 | BTN r 2.0 | SB c 2.0 | BB f 0.0
- **flop**: SB x 0.0 | UTG x 0.0 | MP x 0.0 | CO b 7.8 | BTN c 7.8 | SB c 7.8 | UTG f 0.0 | MP f 0.0
- **turn**: SB x 0.0 | CO x 0.0 | BTN x 0.0
- **river**: SB x 0.0 | CO x 0.0 | BTN b 15.0 | SB f 0.0 | CO c 15.0

### H_0904 - 2026-09-17

- **Pot declarado**: 5.1
- **Combinaciones**: 1
- **Netos posibles**: [1.9]
- **Brutos posibles**: [3.2]
- **Neto mas cercano**: 1.9 (dif -3.2)
- **Stacks**: CO=94.5, BTN=27.8, SB=363.5, BB=100.0, MP=102.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 1.3 | SB f 0.0

### H_0909 - 2026-09-17

- **Pot declarado**: 5.7
- **Combinaciones**: 1
- **Netos posibles**: [31.54]
- **Brutos posibles**: [31.54]
- **Neto mas cercano**: 31.54 (dif 25.84)
- **Stacks**: BTN=101.7, SB=40.2, BB=410.0, UTG=110.3, MP=98.2, CO=50.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP x 0.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 2.9 | CO c 2.9 | SB f 0.0
- **turn**: BB b 4.1 | CO c 4.1
- **river**: BB b 8.1 | CO c 8.1

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

### H_0921 - 2026-09-17

- **Pot declarado**: 110.8
- **Combinaciones**: 1
- **Netos posibles**: [110.6]
- **Brutos posibles**: [110.6]
- **Neto mas cercano**: 110.6 (dif -0.2)
- **Stacks**: BTN=182.9, SB=72.8, BB=388.7, UTG=145.1, MP=74.2, CO=97.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP c 3.0 | CO f 0.0 | BTN f 0.0 | SB c 3.0 | BB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG b 3.7 | MP f 0.0 | SB c 3.7 | BB c 3.7
- **turn**: SB x 0.0 | BB x 0.0 | UTG b 30.0 | SB c 30.0 | BB c 30.0
- **river**: SB x 0.0 | BB x 0.0 | UTG x 0.0

### H_0926 - 2026-09-17

- **Pot declarado**: 170.7
- **Combinaciones**: 1
- **Netos posibles**: [200.5]
- **Brutos posibles**: [209.9]
- **Neto mas cercano**: 200.5 (dif 29.8)
- **Stacks**: BTN=172.5, SB=111.4, BB=337.1, UTG=100.0, MP=137.3, CO=95.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 3.0 | BB c 3.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG b 6.4 | SB f 0.0 | BB c 6.4
- **turn**: SB x 0.0 | UTG b 50.0 | BB r 100.0 | UTG c 90.6

### H_0928 - 2026-09-17

- **Pot declarado**: 80.2
- **Combinaciones**: 1
- **Netos posibles**: [80.0]
- **Brutos posibles**: [80.0]
- **Neto mas cercano**: 80.0 (dif -0.2)
- **Stacks**: SB=168.5, BB=110.7, MP=530.3, CO=119.3, BTN=84.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | MP x 0.0 | CO x 0.0
- **turn**: BB x 0.0 | MP b 12.5 | CO f 0.0 | BB c 12.5
- **river**: BB x 0.0 | MP b 27.0 | BB c 27.0

### H_0932 - 2026-09-17

- **Pot declarado**: 16.7
- **Combinaciones**: 1
- **Netos posibles**: [15.77]
- **Brutos posibles**: [139.27]
- **Neto mas cercano**: 15.77 (dif -0.93)
- **Stacks**: SB=157.7, BB=53.8, UTG=633.5, MP=None, CO=108.4, BTN=75.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG b 1.0 | MP r 6.8 | SB f 0.0 | BB f 0.0 | UTG c 6.8
- **turn**: UTG x 0.0 | MP b 123.5 | UTG f 0.0

### H_0938 - 2026-09-17

- **Pot declarado**: 7.6
- **Combinaciones**: 1
- **Netos posibles**: [2.85]
- **Brutos posibles**: [4.65]
- **Neto mas cercano**: 2.85 (dif -4.75)
- **Stacks**: CO=149.9, BTN=27.8, SB=620.4, BB=151.8, UTG=131.0, MP=74.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB b 1.8 | BTN f 0.0 | SB f 0.0

### H_0941 - 2026-09-17

- **Pot declarado**: 104.7
- **Combinaciones**: 1
- **Netos posibles**: [80.84]
- **Brutos posibles**: [102.84]
- **Neto mas cercano**: 80.84 (dif -23.86)
- **Stacks**: BB=175.6, UTG=25.8, MP=600.6, CO=147.8, BTN=None, SB=73.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO r 2.0 | SB f 0.0 | BB f 0.0
- **flop**: UTG x 0.0 | MP x 0.0 | CO b 5.3 | BTN f 0.0 | UTG f 0.0 | MP c 5.3
- **turn**: MP x 0.0 | CO b 13.0 | MP c 13.0
- **river**: MP b 20.9 | CO r 41.9 | MP f 0.0

### H_0950 - 2026-09-17

- **Pot declarado**: 8.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [7.0, 7.5]
- **Neto mas cercano**: 2.0 (dif -6.0)
- **Stacks**: BB=165.1, MP=30.2, CO=196.5, BTN=126.7, SB=67.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 6.0 | BB f 0.0

### H_0957 - 2026-09-17

- **Pot declarado**: 42.7
- **Combinaciones**: 1
- **Netos posibles**: [38.48]
- **Brutos posibles**: [41.88]
- **Neto mas cercano**: 38.48 (dif -4.22)
- **Stacks**: BB=146.5, UTG=58.6, MP=18.0, CO=187.4, BTN=125.2, SB=68.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO f 0.0 | BTN r 4.0 | SB f 0.0 | BB c 4.0 | MP c 4.0
- **flop**: BB x 0.0 | MP x 0.0 | BTN x 0.0
- **turn**: BB b 5.9 | MP c 5.9 | BTN f 0.0
- **river**: BB b 11.5 | MP c 8.1

### H_0973 - 2026-09-17

- **Pot declarado**: 6.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [5.5]
- **Neto mas cercano**: 2.5 (dif -4.0)
- **Stacks**: BTN=121.0, SB=148.6, BB=77.0, UTG=99.0, MP=39.0, CO=19.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 4.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_0978 - 2026-09-17

- **Pot declarado**: 113.0
- **Combinaciones**: 1
- **Netos posibles**: [145.0]
- **Brutos posibles**: [145.0]
- **Neto mas cercano**: 145.0 (dif 32.0)
- **Stacks**: MP=164.0, CO=128.2, BTN=70.3, SB=94.6, BB=52.7, UTG=34.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 2.5 | CO c 2.5 | BTN c 2.5 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB b 1.0 | MP r 13.0 | CO f 0.0 | BTN c 13.0 | SB f 0.0 | BB f 0.0
- **turn**: MP b 38.0 | BTN c 38.0
- **river**: MP x 0.0 | BTN b 16.0 | MP c 16.0

### H_0985 - 2026-09-17

- **Pot declarado**: 74.9
- **Combinaciones**: 1
- **Netos posibles**: [62.8]
- **Brutos posibles**: [74.2]
- **Neto mas cercano**: 62.8 (dif -12.1)
- **Stacks**: UTG=124.5, MP=122.7, CO=28.4, BTN=140.5, SB=84.0, BB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.5 | MP f 0.0 | CO c 2.5 | BTN c 2.5 | SB c 2.5 | BB c 2.5
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB b 1.0 | BB r 11.4 | UTG f 0.0 | CO c 11.4 | BTN f 0.0 | SB f 0.0
- **river**: BB b 25.9 | CO c 14.5

### H_0993 - 2026-09-17

- **Pot declarado**: 7.5
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [5.58]
- **Neto mas cercano**: 2.38 (dif -5.12)
- **Stacks**: CO=145.7, BTN=125.8, SB=140.6, BB=85.0, UTG=59.1, MP=118.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB b 3.2 | UTG f 0.0

### H_1011 - 2026-09-17

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=102.0, BTN=136.4, SB=39.4, BB=96.4, MP=98.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_1022 - 2026-09-17

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.38]
- **Brutos posibles**: [4.78]
- **Neto mas cercano**: 2.38 (dif 0.88)
- **Stacks**: CO=105.8, BTN=150.0, SB=109.7, BB=50.0, UTG=75.0, MP=93.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | BTN x 0.0
- **turn**: BB x 0.0 | BTN b 2.4 | BB f 0.0

### H_1053 - 2026-09-17

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=100.0, BTN=96.2, SB=44.4, BB=102.0, MP=173.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP r 2.5 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_1080 - 2026-09-17

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [3.5]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: SB=86.8, BB=75.8, UTG=99.0, MP=107.3, CO=193.2, BTN=67.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO r 2.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_1112 - 2026-09-18

- **Pot declarado**: 13.7
- **Combinaciones**: 2
- **Netos posibles**: [61.8]
- **Brutos posibles**: [62.2, 64.3]
- **Neto mas cercano**: 61.8 (dif 48.1)
- **Stacks**: SB=96.8, BB=113.2, UTG=100.0, MP=18.0, CO=126.7, BTN=30.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | BTN x 0.0
- **turn**: SB b 2.1 | BB c 2.1 | BTN r 6.7 | SB r 30.0 | BB f 0.0 | BTN c 29.6

### H_1118 - 2026-09-18

- **Pot declarado**: 17.8
- **Combinaciones**: 1
- **Netos posibles**: [34.67]
- **Brutos posibles**: [37.58]
- **Neto mas cercano**: 34.67 (dif 16.87)
- **Stacks**: SB=122.6, BB=100.5, UTG=105.6, MP=17.5, CO=125.2, BTN=62.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO r 5.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | MP c 5.0
- **flop**: MP x 0.0 | CO b 3.6 | MP c 3.6
- **turn**: MP x 0.0 | CO b 11.8 | MP c 8.9

### H_1123 - 2026-09-18

- **Pot declarado**: 35.1
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [36.6]
- **Neto mas cercano**: 2.5 (dif -32.6)
- **Stacks**: BB=120.6, UTG=73.0, MP=117.4, CO=31.5, BTN=147.5, SB=57.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 35.1 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_1140 - 2026-09-18

- **Pot declarado**: 20.8
- **Combinaciones**: 1
- **Netos posibles**: [29.73]
- **Brutos posibles**: [29.73]
- **Neto mas cercano**: 29.73 (dif 8.93)
- **Stacks**: CO=93.8, BTN=102.0, SB=41.8, BB=207.2, MP=14.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO r 5.0 | BTN f 0.0 | SB f 0.0 | BB f 0.0 | MP c 5.0
- **flop**: MP x 0.0 | CO x 0.0
- **turn**: MP b 9.9 | CO c 9.9

### H_1153 - 2026-09-18

- **Pot declarado**: 58.6
- **Combinaciones**: 1
- **Netos posibles**: [86.3]
- **Brutos posibles**: [86.3]
- **Neto mas cercano**: 86.3 (dif 27.7)
- **Stacks**: BTN=96.9, SB=43.9, BB=108.8, UTG=148.4, MP=50.0, CO=17.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 3.0 | BB f 0.0
- **flop**: SB x 0.0 | UTG b 3.3 | SB c 3.3
- **turn**: SB b 1.0 | UTG r 9.0 | SB c 9.0
- **river**: SB b 28.6 | UTG c 28.6

### H_1179 - 2026-09-18

- **Pot declarado**: 9.4
- **Combinaciones**: 2
- **Netos posibles**: [10.26, 11.21]
- **Brutos posibles**: [10.26, 11.21]
- **Neto mas cercano**: 10.26 (dif 0.86)
- **Stacks**: SB=84.6, BB=52.0, MP=103.8, CO=125.4, BTN=64.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB c 3.0
- **flop**: SB b 1.4 | BB c 1.4
- **turn**: SB x 0.0 | BB x 0.0
- **river**: SB x 0.0 | BB b 1.0 | SB c 1.0

### H_1190 - 2026-09-18

- **Pot declarado**: 1.5
- **Combinaciones**: 1
- **Netos posibles**: [2.5]
- **Brutos posibles**: [4.0]
- **Neto mas cercano**: 2.5 (dif 1.0)
- **Stacks**: CO=104.9, BTN=73.2, SB=99.0, BB=63.1, MP=41.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB f 0.0

### H_1196 - 2026-09-18

- **Pot declarado**: 9.7
- **Combinaciones**: 2
- **Netos posibles**: [5.22, 8.07]
- **Brutos posibles**: [8.22, 11.07]
- **Neto mas cercano**: 8.07 (dif -1.63)
- **Stacks**: UTG=90.9, MP=94.0, CO=100.0, BTN=123.4, SB=62.1, BB=38.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BB b 0.5 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB r 2.0 | CO f 0.0 | SB c 2.0
- **flop**: SB x 0.0 | BB b 3.0 | SB f 0.0

### H_1198 - 2026-09-18

- **Pot declarado**: 16.2
- **Combinaciones**: 1
- **Netos posibles**: [21.75]
- **Brutos posibles**: [21.75]
- **Neto mas cercano**: 21.75 (dif 5.55)
- **Stacks**: SB=89.9, BB=75.0, UTG=100.0, MP=142.0, CO=59.1, BTN=41.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | CO x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB x 0.0 | CO b 2.3 | BTN c 2.3 | SB c 2.3 | BB f 0.0
- **river**: SB x 0.0 | CO b 6.0 | BTN f 0.0 | SB c 6.0

### H_1224 - 2026-09-18

- **Pot declarado**: 16.5
- **Combinaciones**: 1
- **Netos posibles**: [20.14]
- **Brutos posibles**: [20.14]
- **Neto mas cercano**: 20.14 (dif 3.64)
- **Stacks**: SB=120.2, BB=27.8, MP=132.9, CO=17.4, BTN=101.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB x 0.0
- **flop**: SB b 1.4 | BB c 1.4 | CO c 1.4
- **turn**: SB x 0.0 | BB x 0.0 | CO b 2.0 | SB c 2.0 | BB c 2.0
- **river**: SB x 0.0 | BB x 0.0 | CO b 4.0 | SB c 4.0 | BB f 0.0

### H_1231 - 2026-09-18

- **Pot declarado**: 4.5
- **Combinaciones**: 2
- **Netos posibles**: [6.5]
- **Brutos posibles**: [19.9, 20.9]
- **Neto mas cercano**: 6.5 (dif 2.0)
- **Stacks**: CO=127.9, BTN=104.7, SB=100.0, BB=16.4, UTG=46.0, MP=114.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB f 0.0 | BB r 16.4 | UTG f 0.0

### H_1260 - 2026-09-18

- **Pot declarado**: 63.9
- **Combinaciones**: 1
- **Netos posibles**: [84.9]
- **Brutos posibles**: [84.9]
- **Neto mas cercano**: 84.9 (dif 21.0)
- **Stacks**: UTG=150.2, MP=85.8, CO=100.0, BTN=101.2, SB=104.6, BB=92.3
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.5 | MP f 0.0 | CO c 2.5 | BTN f 0.0 | SB f 0.0 | BB c 2.5
- **flop**: BB x 0.0 | UTG b 2.5 | CO r 7.5 | BB f 0.0 | UTG c 7.5
- **turn**: UTG x 0.0 | CO b 10.9 | UTG c 10.9
- **river**: UTG x 0.0 | CO b 21.3 | UTG c 21.3

## ACCION_AMBIGUA (61)

La `causa` describe por que hay mas de una traza. `DEVUELTA` no es un error de bote: la subida no se paga y las fichas extra se devuelven; el neto es el mismo. `REPARTO` y `NETO_IGUAL` tampoco cambian el bote neto, pero dejan el `amount` de alguna accion sin determinar. `REAL` es el unico caso en que el bote neto depende de la lectura. El sufijo `+SB` indica que la coincidencia usa la variante que descuenta la ciega del SB.

### DEVUELTA (subida no pagada; el neto no cambia) - 44

### H_0016 - 2026-07-27

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [6.0, 7.0]
- **Coincidencia**: neto = 3.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [5.0, 4.0]
- **Stacks**: MP=71.5, BTN=None, SB=67.7, BB=112.0, UTG=35.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | BTN f 0.0 | SB c 1.0 | BB r 4.0 | MP f 0.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | BTN f | SB c 1.00 | BB r parcial 5.00 | MP f | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | BTN f | SB c 1.00 | BB r absoluta 4.00 | MP f | SB f

### H_0024 - 2026-07-27

- **Pot declarado**: 28.7
- **Combinaciones**: 2
- **Netos posibles**: [28.69]
- **Brutos posibles**: [28.79, 30.09]
- **Coincidencia**: neto = 28.69 (dif -0.01)
- **Causa**: `DEVUELTA`
- **Diferencia**: turn BB r [4.8, 3.5]
- **Stacks**: SB=66.8, BB=124.4, UTG=78.2, BTN=47.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG b 1.0 | BTN c 1.0 | SB c 1.0 | BB x 0.0
- **flop**: SB x 0.0 | BB x 0.0 | UTG x 0.0 | BTN x 0.0
- **turn**: SB x 0.0 | BB b 1.3 | UTG r 3.4 | BTN c 3.4 | SB f 0.0 | BB r 3.5
- **river**: BB x 0.0 | UTG x 0.0 | BTN b 8.0 | BB c 8.0 | UTG f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG b absoluta 1.00 | BTN c 1.00 | SB c 1.00 | BB x | SB x | BB x | UTG x | BTN x | SB x | BB b absoluta 1.30 | UTG r absoluta 3.40 | BTN c 3.40 | SB f | BB r parcial 4.80 | BB x | UTG x | BTN b absoluta 8.00 | BB c 8.00 | UTG f
  2. SB p 0.50 | BB p 1.00 | UTG b absoluta 1.00 | BTN c 1.00 | SB c 1.00 | BB x | SB x | BB x | UTG x | BTN x | SB x | BB b absoluta 1.30 | UTG r absoluta 3.40 | BTN c 3.40 | SB f | BB r absoluta 3.50 | BB x | UTG x | BTN b absoluta 8.00 | BB c 8.00 | UTG f

### H_0051 - 2026-07-28

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 7.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [6.0, 5.0]
- **Stacks**: SB=48.0, BB=143.2, UTG=86.9, MP=168.4, BTN=42.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB c 1.00 | BB r parcial 6.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB c 1.00 | BB r absoluta 5.00 | SB f

### H_0100 - 2026-07-29

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: CO=40.7, BTN=133.7, SB=71.5, BB=132.3, UTG=24.7, MP=21.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB b parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB b absoluta 3.00 | BB f

### H_0109 - 2026-07-29

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 5.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [4.0, 3.0]
- **Stacks**: BB=35.0, UTG=124.2, MP=64.2, CO=133.8, BTN=24.0, SB=19.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 3.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r parcial 4.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r absoluta 3.00 | SB f

### H_0116 - 2026-07-29

- **Pot declarado**: 6.0
- **Combinaciones**: 2
- **Netos posibles**: [6.0]
- **Brutos posibles**: [15.5, 16.0]
- **Coincidencia**: neto = 6.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [12.5, 12.0]
- **Stacks**: UTG=50.7, MP=113.0, BTN=64.5, SB=101.1, BB=55.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN b 2.5 | SB r 12.0 | BB f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN b absoluta 2.50 | SB r parcial 12.50 | BB f | BTN f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN b absoluta 2.50 | SB r absoluta 12.00 | BB f | BTN f

### H_0119 - 2026-07-29

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [3.0, 3.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [2.5, 2.0]
- **Stacks**: BB=114.5, UTG=66.0, MP=102.1, BTN=48.8, SB=38.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB b 2.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b parcial 2.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b absoluta 2.00 | BB f

### H_0122 - 2026-07-29

- **Pot declarado**: 6.0
- **Combinaciones**: 2
- **Netos posibles**: [6.0]
- **Brutos posibles**: [12.0, 12.5]
- **Coincidencia**: neto = 6.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [9.0, 8.5]
- **Stacks**: BTN=117.0, SB=50.5, BB=103.6, UTG=62.1, MP=37.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN b 2.5 | SB r 8.5 | BB f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN b absoluta 2.50 | SB r parcial 9.00 | BB f | BTN f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN b absoluta 2.50 | SB r absoluta 8.50 | BB f | BTN f

### H_0128 - 2026-07-29

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [7.0, 7.5]
- **Coincidencia**: neto = 3.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [5.5, 5.0]
- **Stacks**: BTN=9.4, SB=100.3, BB=50.0, UTG=98.5, MP=73.4, CO=39.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB b 5.0 | BB f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN c 1.00 | SB b parcial 5.50 | BB f | BTN f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN c 1.00 | SB b absoluta 5.00 | BB f | BTN f

### H_0209 - 2026-07-31

- **Pot declarado**: 4.0
- **Combinaciones**: 2
- **Netos posibles**: [4.0]
- **Brutos posibles**: [9.0, 9.5]
- **Coincidencia**: neto = 4.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [6.5, 6.0]
- **Stacks**: MP=29.7, BTN=91.1, SB=120.6, BB=41.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | BTN c 1.0 | SB b 6.0 | BB f 0.0 | MP f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP c 1.00 | BTN c 1.00 | SB b parcial 6.50 | BB f | MP f | BTN f
  2. SB p 0.50 | BB p 1.00 | MP c 1.00 | BTN c 1.00 | SB b absoluta 6.00 | BB f | MP f | BTN f

### H_0232 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: SB=118.5, BB=107.1, UTG=79.3, MP=102.2, BTN=94.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | BTN f | SB b parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | MP f | BTN f | SB b absoluta 3.00 | BB f

### H_0239 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: CO=100.7, BTN=107.5, SB=50.0, BB=78.3, UTG=100.7, MP=115.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB b 3.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB b parcial 3.50
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB b absoluta 3.00

### H_0247 - 2026-07-31

- **Pot declarado**: 5.0
- **Combinaciones**: 2
- **Netos posibles**: [5.0]
- **Brutos posibles**: [14.0, 14.5]
- **Coincidencia**: neto = 5.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [11.5, 11.0]
- **Stacks**: CO=115.2, BTN=29.6, SB=104.0, BB=20.0, UTG=100.0, MP=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP b 2.0 | CO f 0.0 | BTN f 0.0 | SB r 11.0 | BB f 0.0 | MP f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP b absoluta 2.00 | CO f | BTN f | SB r parcial 11.50 | BB f | MP f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP b absoluta 2.00 | CO f | BTN f | SB r absoluta 11.00 | BB f | MP f

### H_0248 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [9.0, 10.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [9.0, 8.0]
- **Stacks**: MP=115.2, CO=29.6, BTN=107.0, SB=19.0, BB=100.0, UTG=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 8.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r parcial 9.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r absoluta 8.00 | SB f

### H_0262 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 7.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [6.0, 5.0]
- **Stacks**: BTN=147.7, SB=27.8, BB=103.7, UTG=126.2, MP=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB c 1.00 | BB r parcial 6.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB c 1.00 | BB r absoluta 5.00 | SB f

### H_0273 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 6.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [5.5, 5.0]
- **Stacks**: BTN=184.2, SB=104.7, BB=14.0, UTG=122.2, MP=109.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB b 5.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b parcial 5.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b absoluta 5.00 | BB f

### H_0275 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: UTG=171.2, MP=105.7, BTN=25.7, SB=121.2, BB=109.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b absoluta 3.00 | BB f

### H_0279 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 7.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [6.0, 5.0]
- **Stacks**: UTG=171.2, BTN=106.6, SB=25.2, BB=107.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | BTN f | SB c 1.00 | BB r parcial 6.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | BTN f | SB c 1.00 | BB r absoluta 5.00 | SB f

### H_0292 - 2026-07-31

- **Pot declarado**: 2.5
- **Combinaciones**: 2
- **Netos posibles**: [2.5]
- **Brutos posibles**: [6.5, 7.5]
- **Coincidencia**: neto = 2.5 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [6.0, 5.0]
- **Stacks**: BB=159.2, UTG=12.5, MP=115.1, CO=21.3, BTN=152.2, SB=112.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | SB f 0.0 | BB r 5.0 | UTG f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | SB f | BB r parcial 6.00 | UTG f
  2. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | SB f | BB r absoluta 5.00 | UTG f

### H_0298 - 2026-07-31

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: BB=169.5, UTG=120.5, MP=15.2, BTN=154.5, SB=111.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN f | SB b absoluta 3.00 | BB f

### H_0313 - 2026-08-01

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [28.2, 28.7]
- **Coincidencia**: neto = 3.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [26.7, 26.2]
- **Stacks**: MP=113.9, CO=50.0, BTN=119.1, SB=26.2, BB=199.9, UTG=175.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB b 26.2
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f

### H_0334 - 2026-08-09

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [7.0, 7.5]
- **Coincidencia**: neto = 3.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB b [5.5, 5.0]
- **Stacks**: BB=19.0, BTN=63.5, SB=124.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN c 1.0 | SB b 5.0 | BB f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | BTN c 1.00 | SB b parcial 5.50 | BB f | BTN f
  2. SB p 0.50 | BB p 1.00 | BTN c 1.00 | SB b absoluta 5.00 | BB f | BTN f

### H_0370 - 2026-09-13

- **Pot declarado**: 3.0
- **Combinaciones**: 2
- **Netos posibles**: [3.0]
- **Brutos posibles**: [15.2, 15.7]
- **Coincidencia**: neto = 3.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [13.7, 13.2]
- **Stacks**: MP=99.8, CO=56.4, BTN=119.5, SB=13.2, BB=68.888, UTG=135.788
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB r 13.2 | BB f 0.0 | CO f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | BB f | CO f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | BB f | CO f

### H_0421 - 2026-09-13

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB b [3.5, 3.0]
- **Stacks**: SB=90.0, BB=175.0, MP=18.0, CO=None, BTN=255.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB b 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB b parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB b absoluta 3.00 | BB f

### H_0424 - 2026-09-13

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [5.0, 6.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [5.0, 4.0]
- **Stacks**: CO=95.5, BTN=173.5, SB=9.0, BB=20.0, MP=252.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 4.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB c 1.00 | BB r parcial 5.00 | SB f
  2. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB c 1.00 | BB r absoluta 4.00 | SB f

### H_0478 - 2026-09-14

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 5.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [4.0, 3.0]
- **Stacks**: BB=109.0, UTG=100.0, MP=65.8, CO=50.0, BTN=163.6, SB=66.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 3.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r parcial 4.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB c 1.00 | BB r absoluta 3.00 | SB f

### H_0515 - 2026-09-14

- **Pot declarado**: 2.0
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [6.0, 7.0]
- **Coincidencia**: neto = 2.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [6.0, 5.0]
- **Stacks**: BB=104.5, MP=None, CO=105.1, BTN=54.0
- **Acciones**:
- **preflop**: BB p 1.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | BB r 5.0 | CO f 0.0
- **Lecturas alternativas** (2):
  1. BB p 1.00 | MP f | CO c 1.00 | BTN f | BB r parcial 6.00 | CO f
  2. BB p 1.00 | MP f | CO c 1.00 | BTN f | BB r absoluta 5.00 | CO f

### H_0527 - 2026-09-14

- **Pot declarado**: 33.3
- **Combinaciones**: 2
- **Netos posibles**: [33.34]
- **Brutos posibles**: [33.84, 36.84]
- **Coincidencia**: neto = 33.345 (dif 0.045)
- **Causa**: `DEVUELTA`
- **Diferencia**: flop BB r [19.3, 16.3]
- **Stacks**: SB=94.9, BB=58.9, MP=114.6, CO=16.8, BTN=32.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB b 3.0 | MP f 0.0 | CO r 7.0 | BB r 16.3 | CO c 8.1
- **turn**: BB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO c 1.00 | BTN f | SB f | BB x | BB b absoluta 3.00 | MP f | CO r absoluta 7.00 | BB r parcial 19.30 | CO c all-in 15.80 | BB x
  2. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO c 1.00 | BTN f | SB f | BB x | BB b absoluta 3.00 | MP f | CO r absoluta 7.00 | BB r absoluta 16.30 | CO c all-in 15.80 | BB x

### H_0536 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: SB=160.5, BB=69.4, CO=103.8, BTN=104.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | CO f | BTN f | SB r parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | CO f | BTN f | SB r absoluta 3.00 | BB f

### H_0662 - 2026-09-15

- **Pot declarado**: 23.9
- **Combinaciones**: 2
- **Netos posibles**: [24.04]
- **Brutos posibles**: [28.14, 29.14]
- **Coincidencia**: neto = 24.035 (dif 0.135)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [15.0, 14.0]
- **Stacks**: CO=114.5, BTN=120.7, SB=98.8, BB=108.7, UTG=71.0, MP=9.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 5.0 | CO f 0.0 | BTN c 5.0 | SB f 0.0 | BB r 14.0 | MP c 9.9 | BTN f 0.0
- **flop**: BB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 5.00 | CO f | BTN c 5.00 | SB f | BB r parcial 15.00 | MP c all-in 9.90 | BTN f | BB x
  2. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 5.00 | CO f | BTN c 5.00 | SB f | BB r absoluta 14.00 | MP c all-in 9.90 | BTN f | BB x

### H_0791 - 2026-09-15

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: SB=133.5, BB=95.3, CO=40.8, BTN=161.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | CO f | BTN f | SB r parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | CO f | BTN f | SB r absoluta 3.00 | BB f

### H_0831 - 2026-09-16

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: CO=115.4, BTN=9.5, SB=106.4, BB=95.6, MP=16.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r absoluta 3.00 | BB f

### H_0834 - 2026-09-16

- **Pot declarado**: 2.5
- **Combinaciones**: 2
- **Netos posibles**: [2.5]
- **Brutos posibles**: [5.5, 6.5]
- **Coincidencia**: neto = 2.5 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BTN r [5.0, 4.0]
- **Stacks**: MP=None, CO=53.6, BTN=50.0, SB=72.1, BB=101.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | BTN b 1.0 | MP f 0.0 | CO f 0.0 | BTN r 4.0 | SB f 0.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | BTN b absoluta 1.00 | MP f | CO f | BTN r parcial 5.00 | SB f | BB f
  2. SB p 0.50 | BB p 1.00 | BTN b absoluta 1.00 | MP f | CO f | BTN r absoluta 4.00 | SB f | BB f

### H_0837 - 2026-09-16

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: SB=94.0, BB=79.8, UTG=50.0, MP=114.0, CO=151.8, BTN=28.338
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r absoluta 3.00 | BB f

### H_0906 - 2026-09-17

- **Pot declarado**: 48.5
- **Combinaciones**: 4
- **Netos posibles**: [47.6, 48.6]
- **Brutos posibles**: [137.8, 138.8, 139.8]
- **Coincidencia**: neto = 48.6 (dif 0.1)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop CO r [114.0, 113.0]
- **Stacks**: SB=86.0, BB=22.8, MP=347.8, CO=None, BTN=115.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB f 0.0 | BB r 3.0 | MP c 3.0 | CO r 113.0 | BTN f 0.0 | BB c 18.8 | MP f 0.0
- **flop**: MP x 0.0
- **turn**: MP x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO c 1.00 | BTN c 1.00 | SB f | BB r parcial 4.00 | MP c 4.00 | CO r parcial 114.00 | BTN f | BB c all-in 22.80 | MP f | MP x | MP x
  2. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO c 1.00 | BTN c 1.00 | SB f | BB r parcial 4.00 | MP c 4.00 | CO r absoluta 113.00 | BTN f | BB c all-in 22.80 | MP f | MP x | MP x

### H_0910 - 2026-09-17

- **Pot declarado**: 4.0
- **Combinaciones**: 2
- **Netos posibles**: [4.0]
- **Brutos posibles**: [113.3, 114.3]
- **Coincidencia**: neto = 4.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [111.3, 110.3]
- **Stacks**: CO=101.7, BTN=39.2, SB=393.9, BB=110.3, UTG=98.2, MP=65.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB r 110.3 | MP f 0.0 | CO f 0.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN f | SB c 1.00 | MP f | CO f | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN f | SB c 1.00 | MP f | CO f | SB f

### H_0917 - 2026-09-17

- **Pot declarado**: 184.4
- **Combinaciones**: 2
- **Netos posibles**: [184.4]
- **Brutos posibles**: [215.0, 216.0]
- **Coincidencia**: neto = 184.4 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop MP r [122.3, 121.3]
- **Stacks**: BTN=90.7, SB=42.4, BB=364.5, MP=121.3, CO=97.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP c 1.0 | CO f 0.0 | BTN r 5.0 | SB f 0.0 | BB c 5.0 | MP r 121.3 | BTN c 90.7 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO f | BTN r absoluta 5.00 | SB f | BB c 5.00 | BTN c all-in 90.70 | BB f
  2. SB p 0.50 | BB p 1.00 | MP c 1.00 | CO f | BTN r absoluta 5.00 | SB f | BB c 5.00 | BTN c all-in 90.70 | BB f

### H_0930 - 2026-09-17

- **Pot declarado**: 12.0
- **Combinaciones**: 2
- **Netos posibles**: [12.0]
- **Brutos posibles**: [127.3, 128.3]
- **Coincidencia**: neto = 12.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BB r [119.3, 118.3]
- **Stacks**: CO=168.0, BTN=53.2, SB=591.9, BB=118.3, MP=77.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 3.0 | BTN c 3.0 | SB c 3.0 | BB r 118.3 | CO f 0.0 | BTN f 0.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO r absoluta 3.00 | BTN c 3.00 | SB c 3.00 | CO f | BTN f | SB f
  2. SB p 0.50 | BB p 1.00 | MP f | CO r absoluta 3.00 | BTN c 3.00 | SB c 3.00 | CO f | BTN f | SB f

### H_0931 - 2026-09-17

- **Pot declarado**: 102.6
- **Combinaciones**: 2
- **Netos posibles**: [102.7]
- **Brutos posibles**: [142.3, 146.6]
- **Coincidencia**: neto = 102.7 (dif 0.1)
- **Causa**: `DEVUELTA`
- **Diferencia**: flop CO r [92.1, 87.8]
- **Stacks**: UTG=164.0, MP=49.2, CO=587.9, BTN=131.3, SB=100.0, BB=77.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB x 0.0
- **flop**: BB x 0.0 | UTG x 0.0 | MP x 0.0 | CO b 4.3 | BB f 0.0 | UTG c 4.3 | MP r 48.2 | CO r 87.8 | UTG f 0.0
- **turn**: CO x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP c 1.00 | CO c 1.00 | BTN f | SB f | BB x | BB x | UTG x | MP x | CO b absoluta 4.30 | BB f | UTG c 4.30 | MP r absoluta 48.20 | CO r parcial 92.10 | UTG f | CO x
  2. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP c 1.00 | CO c 1.00 | BTN f | SB f | BB x | BB x | UTG x | MP x | CO b absoluta 4.30 | BB f | UTG c 4.30 | MP r absoluta 48.20 | CO r absoluta 87.80 | UTG f | CO x

### H_0939 - 2026-09-17

- **Pot declarado**: 10.0
- **Combinaciones**: 2
- **Netos posibles**: [10.0]
- **Brutos posibles**: [162.5, 163.0]
- **Coincidencia**: neto = 10.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [156.0, 155.5]
- **Stacks**: MP=149.9, CO=25.8, BTN=618.4, SB=155.5, BB=131.0, UTG=74.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 3.0 | CO f 0.0 | BTN c 3.0 | SB r 155.5 | BB f 0.0 | BTN f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 3.00 | CO f | BTN c 3.00 | BB f | BTN f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 3.00 | CO f | BTN c 3.00 | BB f | BTN f

### H_0945 - 2026-09-17

- **Pot declarado**: 5.0
- **Combinaciones**: 2
- **Netos posibles**: [5.0]
- **Brutos posibles**: [190.2, 190.7]
- **Coincidencia**: neto = 5.0 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [186.7, 186.2]
- **Stacks**: MP=170.6, CO=18.3, BTN=569.7, SB=186.2, BB=134.1, UTG=78.2
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN c 1.0 | SB r 186.2 | BB f 0.0 | MP f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN c 1.00 | BB f | MP f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN c 1.00 | BB f | MP f

### H_1086 - 2026-09-17

- **Pot declarado**: 1.5
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [4.0, 4.5]
- **Coincidencia**: neto_sin_sb = 1.5 (dif 0.0)
- **Causa**: `DEVUELTA+SB`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: BTN=87.8, SB=70.8, BB=97.5, UTG=135.6, MP=168.8, CO=66.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r parcial 3.50 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r absoluta 3.00 | BB f

### H_1188 - 2026-09-18

- **Pot declarado**: 1.9
- **Combinaciones**: 2
- **Netos posibles**: [2.0]
- **Brutos posibles**: [2.9, 3.4]
- **Coincidencia**: neto = 2.0 (dif 0.1)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop SB r [2.4, 1.9]
- **Stacks**: MP=132.6, CO=68.9, BTN=124.9, SB=64.10000000000001, BB=46.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 1.9 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r parcial 2.40 | BB f
  2. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r absoluta 1.90 | BB f

### H_1241 - 2026-09-18

- **Pot declarado**: 24.7
- **Combinaciones**: 4
- **Netos posibles**: [24.7, 26.6]
- **Brutos posibles**: [32.7, 33.6, 34.7, 35.6]
- **Coincidencia**: neto = 24.7 (dif 0.0)
- **Causa**: `DEVUELTA`
- **Diferencia**: preflop BTN r [22.0, 20.0]
- **Stacks**: CO=128.7, BTN=86.3, SB=112.3, BB=12.0, UTG=63.3, MP=112.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN r 2.0 | SB c 2.0 | BB r 12.0 | BTN r 20.0 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN r absoluta 2.00 | SB c 2.00 | BTN r parcial 22.00 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN r absoluta 2.00 | SB c 2.00 | BTN r absoluta 20.00 | SB f

### REPARTO (mismo bote; cambia quien aporta) - 11

### H_0104 - 2026-07-29

- **Pot declarado**: 19.4
- **Combinaciones**: 4
- **Netos posibles**: [18.05, 19.38]
- **Brutos posibles**: [18.75, 20.38]
- **Coincidencia**: neto = 19.38 (dif -0.02)
- **Causa**: `REPARTO`
- **Diferencia**: preflop BB r [4.0, 3.0]
- **Stacks**: UTG=31.0, MP=128.2, CO=72.5, BTN=132.3, SB=25.7, BB=9.7
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG p 1.0 | UTG x 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB c 1.0 | BB r 3.0 | UTG r 9.0 | SB f 0.0 | BB c 9.0
- **flop**: UTG x 0.0 | BB b 0.7
- **turn**: UTG x 0.0
- **river**: UTG x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG p 1.00 | UTG x | MP f | CO f | BTN f | SB c 1.00 | BB r parcial 4.00 | UTG r parcial 10.00 | SB f | BB c all-in 9.70 | UTG x | UTG x | UTG x
  2. SB p 0.50 | BB p 1.00 | UTG p 1.00 | UTG x | MP f | CO f | BTN f | SB c 1.00 | BB r absoluta 3.00 | UTG r parcial 10.00 | SB f | BB c all-in 9.70 | UTG x | UTG x | UTG x

### H_0127 - 2026-07-29

- **Pot declarado**: 16.5
- **Combinaciones**: 4
- **Netos posibles**: [16.43, 18.34]
- **Brutos posibles**: [16.43, 18.34]
- **Coincidencia**: neto = 16.435 (dif -0.065)
- **Causa**: `REPARTO`
- **Diferencia**: preflop BB r [7.0, 6.0]
- **Stacks**: CO=8.4, BTN=102.3, SB=50.0, BB=98.5, UTG=73.4, MP=39.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB f 0.0 | BB r 6.0 | CO r 8.4 | BB c 8.4
- **flop**: BB x 0.0
- **turn**: BB x 0.0
- **river**: BB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO c 1.00 | BTN f | SB f | BB r parcial 7.00 | BB c 8.40 | BB x | BB x | BB x
  2. SB p 0.50 | BB p 1.00 | MP f | CO c 1.00 | BTN f | SB f | BB r absoluta 6.00 | BB c 8.40 | BB x | BB x | BB x

### H_0223 - 2026-07-31

- **Pot declarado**: 46.5
- **Combinaciones**: 4
- **Netos posibles**: [46.45, 52.4]
- **Brutos posibles**: [46.45, 52.4]
- **Coincidencia**: neto = 46.455 (dif -0.045)
- **Causa**: `REPARTO`
- **Diferencia**: preflop BB r [10.0, 9.0]
- **Stacks**: MP=112.1, BTN=24.2, SB=84.8, BB=119.6, UTG=101.8
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | BTN r 3.0 | SB f 0.5 | BB r 9.0 | BTN r 24.2 | BB c 24.2
- **flop**: BB x 0.0
- **turn**: BB x 0.0
- **river**: BB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN r absoluta 3.00 | SB f | BB r parcial 10.00 | BB c 24.20 | BB x | BB x | BB x
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | BTN r absoluta 3.00 | SB f | BB r absoluta 9.00 | BB c 24.20 | BB x | BB x | BB x

### H_0407 - 2026-09-13

- **Pot declarado**: 167.5
- **Combinaciones**: 8
- **Netos posibles**: [167.5, 187.5, 188.5]
- **Brutos posibles**: [167.5, 187.5, 188.5]
- **Coincidencia**: neto = 167.5 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [10.5, 10.5, 10.0, 10.0]; preflop UTG r [25.0, 22.0, 25.0, 22.0]
- **Stacks**: MP=113.2, CO=184.3, BTN=7.5, SB=83.0, BB=52.0, UTG=142.9
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP f 0.0 | CO c 3.0 | BTN f 0.0 | SB r 10.0 | BB f 0.0 | UTG r 22.0 | CO f 0.0 | SB r 83.0 | UTG c 83.0
- **Lecturas alternativas** (4):
  1. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO c 3.00 | BTN f | SB r parcial 10.50 | BB f | UTG r parcial 25.00 | CO f | UTG c 83.00
  2. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO c 3.00 | BTN f | SB r parcial 10.50 | BB f | UTG r absoluta 22.00 | CO f | UTG c 83.00
  3. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO c 3.00 | BTN f | SB r absoluta 10.00 | BB f | UTG r parcial 25.00 | CO f | UTG c 83.00
  4. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO c 3.00 | BTN f | SB r absoluta 10.00 | BB f | UTG r absoluta 22.00 | CO f | UTG c 83.00

### H_0460 - 2026-09-14

- **Pot declarado**: 87.8
- **Combinaciones**: 4
- **Netos posibles**: [53.5, 58.5]
- **Brutos posibles**: [82.8, 87.8]
- **Coincidencia**: bruto = 87.8 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [12.5, 12.0]
- **Stacks**: UTG=79.9, MP=100.0, CO=68.4, BTN=50.0, SB=103.5, BB=80.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 2.5 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 12.0 | BB f 0.0 | UTG r 27.5 | SB c 18.0
- **flop**: SB x 0.0 | UTG b 29.3 | SB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG r absoluta 2.50 | MP f | CO f | BTN f | SB r parcial 12.50 | BB f | UTG r parcial 30.00 | SB c 30.00 | SB x | UTG b absoluta 29.30 | SB f
  2. SB p 0.50 | BB p 1.00 | UTG r absoluta 2.50 | MP f | CO f | BTN f | SB r absoluta 12.00 | BB f | UTG r parcial 30.00 | SB c 30.00 | SB x | UTG b absoluta 29.30 | SB f

### H_0465 - 2026-09-14

- **Pot declarado**: 109.2
- **Combinaciones**: 4
- **Netos posibles**: [107.1, 109.1]
- **Brutos posibles**: [107.1, 109.1]
- **Coincidencia**: neto = 109.1 (dif -0.1)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [4.5, 4.0]
- **Stacks**: MP=106.9, CO=100.0, BTN=63.9, SB=55.8, BB=101.5, UTG=77.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 4.0 | BB r 11.0 | SB c 8.0
- **flop**: SB x 0.0 | BB b 7.5 | SB c 7.5
- **turn**: SB b 36.3 | BB c 36.3
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r parcial 4.50 | BB r parcial 12.00 | SB c 12.00 | SB x | BB b absoluta 7.50 | SB c 7.50 | SB b absoluta 36.30 | BB c 36.30
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r absoluta 4.00 | BB r parcial 12.00 | SB c 12.00 | SB x | BB b absoluta 7.50 | SB c 7.50 | SB b absoluta 36.30 | BB c 36.30

### H_0602 - 2026-09-15

- **Pot declarado**: 48.8
- **Combinaciones**: 4
- **Netos posibles**: [48.8, 53.8]
- **Brutos posibles**: [48.8, 53.8]
- **Coincidencia**: neto = 48.8 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop BB r [10.0, 9.0]
- **Stacks**: MP=190.6, CO=25.4, BTN=52.5, SB=132.3, BB=100.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO r 2.5 | BTN f 0.0 | SB f 0.0 | BB r 9.0 | CO r 25.4 | BB c 15.4
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | MP f | CO r absoluta 2.50 | BTN f | SB f | BB r parcial 10.00 | BB c 25.40
  2. SB p 0.50 | BB p 1.00 | MP f | CO r absoluta 2.50 | BTN f | SB f | BB r absoluta 9.00 | BB c 25.40

### H_0923 - 2026-09-17

- **Pot declarado**: 145.1
- **Combinaciones**: 4
- **Netos posibles**: [69.85, 72.7]
- **Brutos posibles**: [142.25, 145.1]
- **Coincidencia**: bruto = 145.1 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [2.5, 2.0]; preflop MP c [2.5, 2.0]
- **Stacks**: UTG=171.0, MP=143.9, CO=281.0, BTN=108.1, SB=152.3, BB=97.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP c 1.0 | CO c 1.0 | BTN f 0.0 | SB r 2.0 | BB f 0.0 | MP c 2.0 | CO r 14.0 | SB c 13.0 | MP c 13.0
- **flop**: SB x 0.0 | MP b 14.5 | CO r 86.9 | SB f 0.0 | MP f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN f | SB r parcial 2.50 | BB f | MP c 2.50 | CO r parcial 15.00 | SB c 15.00 | MP c 15.00 | SB x | MP b absoluta 14.50 | CO r absoluta 86.90 | SB f | MP f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP c 1.00 | CO c 1.00 | BTN f | SB r absoluta 2.00 | BB f | MP c 2.00 | CO r parcial 15.00 | SB c 15.00 | MP c 15.00 | SB x | MP b absoluta 14.50 | CO r absoluta 86.90 | SB f | MP f

### H_1212 - 2026-09-18

- **Pot declarado**: 20.2
- **Combinaciones**: 4
- **Netos posibles**: [13.3, 15.2]
- **Brutos posibles**: [18.3, 20.2]
- **Coincidencia**: bruto = 20.2 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [3.5, 3.0]
- **Stacks**: CO=118.6, BTN=59.0, SB=100.5, BB=160.9, UTG=100.0, MP=41.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 3.0 | BB r 7.0 | SB c 5.0
- **flop**: SB b 5.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r parcial 3.50 | BB r parcial 8.00 | SB c 8.00 | SB b absoluta 5.00 | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO f | BTN f | SB r absoluta 3.00 | BB r parcial 8.00 | SB c 8.00 | SB b absoluta 5.00 | BB f

### H_1228 - 2026-09-18

- **Pot declarado**: 42.8
- **Combinaciones**: 4
- **Netos posibles**: [41.8, 42.75]
- **Brutos posibles**: [101.8, 103.75]
- **Coincidencia**: neto = 42.75 (dif -0.05)
- **Causa**: `REPARTO`
- **Diferencia**: preflop SB r [3.5, 3.0]; preflop UTG c [3.5, 3.0]
- **Stacks**: BB=124.3, UTG=113.7, MP=100.0, CO=19.0, BTN=50.0, SB=104.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | CO b 1.0 | UTG c 1.0 | MP f 0.0 | CO x 0.0 | BTN c 1.0 | SB r 3.0 | BB f 0.0 | UTG c 3.0 | CO r 4.0 | BTN f 0.0 | SB c 2.0 | UTG c 2.0
- **flop**: SB x 0.0 | UTG x 0.0 | CO b 13.0 | SB c 13.0 | UTG f 0.0
- **turn**: SB b 62.0 | CO c 1.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | CO b absoluta 1.00 | UTG c 1.00 | MP f | CO x | BTN c 1.00 | SB r parcial 3.50 | BB f | UTG c 3.50 | CO r parcial 5.00 | BTN f | SB c 5.00 | UTG c 5.00 | SB x | UTG x | CO b absoluta 13.00 | SB c 13.00 | UTG f | SB b absoluta 62.00 | CO c all-in 1.00
  2. SB p 0.50 | BB p 1.00 | CO b absoluta 1.00 | UTG c 1.00 | MP f | CO x | BTN c 1.00 | SB r absoluta 3.00 | BB f | UTG c 3.00 | CO r parcial 5.00 | BTN f | SB c 5.00 | UTG c 5.00 | SB x | UTG x | CO b absoluta 13.00 | SB c 13.00 | UTG f | SB b absoluta 62.00 | CO c all-in 1.00

### H_1270 - 2026-09-18

- **Pot declarado**: 90.8
- **Combinaciones**: 4
- **Netos posibles**: [90.8, 96.8]
- **Brutos posibles**: [90.8, 96.8]
- **Coincidencia**: neto = 90.8 (dif 0.0)
- **Causa**: `REPARTO`
- **Diferencia**: preflop BB r [16.0, 15.0]
- **Stacks**: CO=179.0, BTN=144.3, SB=26.3, BB=105.7, UTG=44.9, MP=49.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG r 3.0 | MP f 0.0 | CO f 0.0 | BTN c 3.0 | SB f 0.0 | BB r 15.0 | UTG r 44.9 | BTN f 0.0 | BB c 28.9
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO f | BTN c 3.00 | SB f | BB r parcial 16.00 | BTN f | BB c 44.90
  2. SB p 0.50 | BB p 1.00 | UTG r absoluta 3.00 | MP f | CO f | BTN c 3.00 | SB f | BB r absoluta 15.00 | BTN f | BB c 44.90

### NETO_IGUAL (mismo neto; cambian importes igualados) - 5

### H_0146 - 2026-07-29

- **Pot declarado**: 123.7
- **Combinaciones**: 2
- **Netos posibles**: [123.8]
- **Brutos posibles**: [126.9, 127.4]
- **Coincidencia**: neto = 123.8 (dif 0.1)
- **Causa**: `NETO_IGUAL`
- **Diferencia**: preflop SB r [15.5, 15.0]; preflop BTN c [15.5, 15.0]; turn BTN c [35.4, 35.9]
- **Stacks**: SB=101.2, BB=79.7, UTG=95.1, MP=143.7, BTN=61.4
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 2.5 | BTN c 2.5 | SB r 15.0 | BB f 0.0 | MP f 0.0 | BTN c 15.0
- **flop**: SB b 10.5 | BTN c 10.5
- **turn**: SB b 39.0 | BTN c 35.9
- **river**: SB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 2.50 | BTN c 2.50 | SB r parcial 15.50 | BB f | MP f | BTN c 15.50 | SB b absoluta 10.50 | BTN c 10.50 | SB b absoluta 39.00 | BTN c all-in 35.40 | SB x
  2. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 2.50 | BTN c 2.50 | SB r absoluta 15.00 | BB f | MP f | BTN c 15.00 | SB b absoluta 10.50 | BTN c 10.50 | SB b absoluta 39.00 | BTN c all-in 35.90 | SB x

### H_0181 - 2026-07-30

- **Pot declarado**: 37.1
- **Combinaciones**: 2
- **Netos posibles**: [37.05]
- **Brutos posibles**: [37.85, 38.35]
- **Coincidencia**: neto = 37.05 (dif -0.05)
- **Causa**: `NETO_IGUAL`
- **Diferencia**: preflop SB b [6.5, 6.0]; preflop BTN c [6.5, 6.0]; flop BTN c [12.0, 12.5]
- **Stacks**: SB=110.5, BB=41.3, UTG=32.5, MP=119.8, CO=88.1, BTN=18.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN c 1.0 | SB b 6.0 | BB f 0.0 | UTG f 0.0 | BTN c 6.0
- **flop**: SB b 13.3 | BTN c 12.5
- **turn**: SB x 0.0
- **river**: SB x 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | BTN c 1.00 | SB b parcial 6.50 | BB f | UTG f | BTN c 6.50 | SB b absoluta 13.30 | BTN c all-in 12.00 | SB x | SB x
  2. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | BTN c 1.00 | SB b absoluta 6.00 | BB f | UTG f | BTN c 6.00 | SB b absoluta 13.30 | BTN c all-in 12.50 | SB x | SB x

### H_0773 - 2026-09-15

- **Pot declarado**: 38.9
- **Combinaciones**: 2
- **Netos posibles**: [38.95]
- **Brutos posibles**: [43.25, 43.75]
- **Coincidencia**: neto = 38.95 (dif 0.05)
- **Causa**: `NETO_IGUAL`
- **Diferencia**: preflop SB r [6.5, 6.0]; preflop UTG c [6.5, 6.0]; river UTG c [7.3, 7.8]
- **Stacks**: BB=113.9, UTG=20.0, MP=113.4, CO=76.1, BTN=259.0, SB=126.1
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG c 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 6.0 | BB f 0.0 | UTG c 6.0
- **flop**: SB x 0.0 | UTG x 0.0
- **turn**: SB b 6.2 | UTG c 6.2
- **river**: SB b 12.1 | UTG c 7.8
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | BTN f | SB r parcial 6.50 | BB f | UTG c 6.50 | SB x | UTG x | SB b absoluta 6.20 | UTG c 6.20 | SB b absoluta 12.10 | UTG c all-in 7.30
  2. SB p 0.50 | BB p 1.00 | UTG c 1.00 | MP f | CO f | BTN f | SB r absoluta 6.00 | BB f | UTG c 6.00 | SB x | UTG x | SB b absoluta 6.20 | UTG c 6.20 | SB b absoluta 12.10 | UTG c all-in 7.80

### H_1137 - 2026-09-18

- **Pot declarado**: 38.0
- **Combinaciones**: 4
- **Netos posibles**: [38.0]
- **Brutos posibles**: [46.0, 46.5, 49.0, 49.5]
- **Coincidencia**: neto = 38.0 (dif 0.0)
- **Causa**: `NETO_IGUAL`
- **Diferencia**: preflop SB r [4.5, 4.5, 4.0, 4.0]; preflop BB c [4.5, 4.5, 4.0, 4.0]; flop SB r [27.0, 24.0, 27.0, 24.0]; flop BB c [15.5, 15.5, 16.0, 16.0]
- **Stacks**: MP=101.9, CO=93.2, BTN=118.6, SB=192.2, BB=20.0
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | MP f 0.0 | CO f 0.0 | BTN f 0.0 | SB r 4.0 | BB c 4.0
- **flop**: SB b 3.0 | BB r 15.0 | SB r 24.0 | BB c 1.0
- **Lecturas alternativas** (4):
  1. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r parcial 4.50 | BB c 4.50 | SB b absoluta 3.00 | BB r absoluta 15.00 | SB r parcial 27.00 | BB c all-in 15.50
  2. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r parcial 4.50 | BB c 4.50 | SB b absoluta 3.00 | BB r absoluta 15.00 | SB r absoluta 24.00 | BB c all-in 15.50
  3. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r absoluta 4.00 | BB c 4.00 | SB b absoluta 3.00 | BB r absoluta 15.00 | SB r parcial 27.00 | BB c all-in 16.00
  4. SB p 0.50 | BB p 1.00 | MP f | CO f | BTN f | SB r absoluta 4.00 | BB c 4.00 | SB b absoluta 3.00 | BB r absoluta 15.00 | SB r absoluta 24.00 | BB c all-in 16.00

### H_1150 - 2026-09-18

- **Pot declarado**: 40.4
- **Combinaciones**: 2
- **Netos posibles**: [40.38]
- **Brutos posibles**: [45.77, 46.27]
- **Coincidencia**: neto = 40.375 (dif -0.025)
- **Causa**: `NETO_IGUAL`
- **Diferencia**: preflop SB r [10.5, 10.0]; preflop CO c [10.5, 10.0]; flop CO c [9.0, 9.5]
- **Stacks**: MP=100.9, CO=19.5, BTN=106.3, SB=163.8, BB=50.0, UTG=21.5
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP r 2.5 | CO c 2.5 | BTN f 0.0 | SB r 10.0 | BB f 0.0 | MP f 0.0 | CO c 10.0
- **flop**: SB b 14.9 | CO c 9.5
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 2.50 | CO c 2.50 | BTN f | SB r parcial 10.50 | BB f | MP f | CO c 10.50 | SB b absoluta 14.90 | CO c all-in 9.00
  2. SB p 0.50 | BB p 1.00 | UTG f | MP r absoluta 2.50 | CO c 2.50 | BTN f | SB r absoluta 10.00 | BB f | MP f | CO c 10.00 | SB b absoluta 14.90 | CO c all-in 9.50

### REAL (el bote neto cambia) - 1

### H_0451 - 2026-09-14

- **Pot declarado**: 21.0
- **Combinaciones**: 4
- **Netos posibles**: [11.0, 13.0]
- **Brutos posibles**: [20.0, 21.0, 22.0]
- **Coincidencia**: bruto = 21.0 (dif 0.0)
- **Causa**: `REAL`
- **Diferencia**: preflop BB r [6.0, 5.0]; preflop CO r [14.0, 15.0]
- **Stacks**: BB=88.4, UTG=100.0, MP=71.4, CO=61.6, BTN=100.0, SB=64.6
- **Acciones**:
- **preflop**: SB p 0.5 | BB p 1.0 | UTG f 0.0 | MP f 0.0 | CO c 1.0 | BTN f 0.0 | SB c 1.0 | BB r 5.0 | CO r 14.0 | SB f 0.0 | BB f 0.0
- **Lecturas alternativas** (2):
  1. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | SB c 1.00 | BB r parcial 6.00 | CO r absoluta 14.00 | SB f | BB f
  2. SB p 0.50 | BB p 1.00 | UTG f | MP f | CO c 1.00 | BTN f | SB c 1.00 | BB r absoluta 5.00 | CO r parcial 15.00 | SB f | BB f
