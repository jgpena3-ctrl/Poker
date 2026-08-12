"""
test_live — toma un pantallazo, lee la mesa e imprime resultados.
Presiona Enter para repetir, Ctrl+C para salir.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import ImageGrab
from lector_estado import StateReader
from lector_unificado import CardReader

PLAYER_LABELS = ['hero', 'p1', 'p2', 'p3', 'p4', 'p5']

print('=== Inicializando lectores...')
t0 = time.perf_counter()
reader = StateReader()
card_reader = CardReader()
print(f'  Listo en {(time.perf_counter()-t0)*1000:.0f}ms')

while True:
    print()
    input('Presiona Enter para capturar (Ctrl+C para salir)...')

    print('=== Capturando pantalla...')
    pil = ImageGrab.grab()
    img_arr = np.array(pil.convert('RGB'))
    print(f'  Resolución: {pil.size[0]}x{pil.size[1]}')

    print('=== Leyendo estado de la mesa...')
    t0 = time.perf_counter()
    state = reader.read_all(pil)
    cards = card_reader.read_all(img_arr)
    state['hero_cards'] = cards['hero']
    state['community'] = cards['community']
    dt = (time.perf_counter() - t0) * 1000
    print(f'  Hecho en {dt:.0f}ms')

    print()
    print('=' * 60)
    print('RESULTADOS')
    print('=' * 60)

    pot = state.get('pot')
    print(f'  Pot:              {pot if pot is not None else "-"}')

    btn = state.get('btn')
    print(f'  Dealer:           {btn if btn else "-"}')

    hero_cards = state.get('hero_cards', [])
    hero_str = ' '.join(c if c else '?' for c in hero_cards) if hero_cards else '-'
    print(f'  Hero cards:       {hero_str}')

    community = state.get('community', [])
    com_str = ' '.join(
        f'{c["rank"]}{c["suit"]}' if c and c.get('rank') else '?'
        for c in community
    ) if community else '-'
    print(f'  Community:        {com_str}')

    print()
    print('  Jugador     Stake     Bet       Estado')
    print('  ' + '-' * 48)
    for p in PLAYER_LABELS:
        stake = state.get(f'{p}_stake')
        bet = state.get(f'{p}_bet')
        st = state.get(f'{p}_state', '—')
        stake_str = f'{stake:.1f}' if stake is not None else '-'
        bet_str = f'{bet:.1f}' if bet is not None else '-'
        print(f'  {p:10s} {stake_str:>8s} {bet_str:>8s} {st or "-"}')

    print()
    print('=' * 60)
