# -*- coding: utf-8 -*-
"""Auditoria reproducible de la calidad estrategica HU/MW. Solo lectura.

Reproduce, con definiciones explicitas, las mediciones principales de
`DOCS/AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md`:

  - divergencias entre lectura legacy y contrato preflop;
  - cobertura de Call_OR y de 4B;
  - distribucion de priors posicionales y uso de FLAT_PRIOR;
  - etiquetas legacy frente al contrato estricto;
  - equity estatica frente a equity con runout;
  - metrica multiway sobre la base total y la fiable;
  - rutas de produccion y consumidores.

El script no escribe en `data/`, no ejecuta `--apply`, no activa writers y no
cambia `MULTIWAY_SOPORTADO`. Cada metrica declara denominador, filtros,
definicion, origen y funcion responsable. Si una cifra del informe no se
reproduce, el estado es `DOES_NOT_REPRODUCE`; no se ajusta nada para forzarla.

Uso:
    python tools/auditar_estrategia_reproducible.py
    python tools/auditar_estrategia_reproducible.py --json
"""
from __future__ import print_function

import argparse
import collections
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

with contextlib.redirect_stdout(io.StringIO()):
    from motor import learn, multiway, preflop, rules
    from motor.asistente_live import (
        _pf_rival_pos, _pf_table_lookup, _preflop_raises, _preflop_spot,
    )
    from motor.decision import runout_equity
    from motor.player_ranges import ProfileRangeModel
    from motor.preflop_contract import (
        actions_of, first_decision, table_plan,
    )
    from motor.situation import equity_vs_range

STREETS = ("flop", "turn", "river")
REPORT_DOC = "DOCS/AUDITORIA_ESTRATEGICA_MULTIWAY_2026-11-13.md"
DATA_FILES = (
    "data/hands_db.jsonl",
    "data/preflop_matrices.json",
    "data/behavior.json",
    "data/postflop_ranges.json",
    "data/profile_ranges.json",
    "data/decisions.jsonl",
    "data/observations.json",
)


def _git(*args):
    try:
        return subprocess.check_output(
            ["git"] + list(args), cwd=ROOT, stderr=subprocess.STDOUT
        ).decode("utf-8", "replace").strip()
    except Exception:
        return None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_meta(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"path": path, "exists": False}
    return {
        "path": path,
        "exists": True,
        "bytes": os.path.getsize(full),
        "sha256": _sha256(full),
    }


def _prefix_before(actions, pos):
    out = []
    for action in actions:
        if action.get("pos") == pos:
            break
        out.append(action)
    return out


def _legacy_limp(prefix, pos):
    limp = False
    raise_seen = False
    for action in prefix:
        if action.get("pos") == pos:
            continue
        if action.get("action") == "r":
            raise_seen = True
        elif action.get("action") == "c" and not raise_seen:
            limp = True
    return limp


def _hero_pos(hand):
    for player in hand.get("players") or []:
        if (player.get("cards") or "").strip():
            return player.get("pos")
    return None


def _active_at(hand, street):
    order = ("preflop", "flop", "turn", "river")
    out = set()
    streets = hand.get("streets") or {}
    for current in order:
        for action in ((streets.get(current) or {}).get("actions") or []):
            if isinstance(action, dict) and action.get("action") == "f" \
                    and action.get("pos"):
                out.add(action["pos"])
        if current == street:
            break
    return {
        player.get("pos")
        for player in (hand.get("players") or [])
        if player.get("active") and player.get("pos") not in out
    }


def _postflop_action_keys(hands):
    all_keys = set()
    villain_keys = set()
    for hand in hands:
        hid = hand.get("hand_id")
        hero = _hero_pos(hand)
        for street in STREETS:
            actions = ((hand.get("streets") or {}).get(street) or {}).get(
                "actions") or []
            for action in actions:
                pos = action.get("pos")
                if not pos:
                    continue
                all_keys.add((hid, pos))
                if pos != hero:
                    villain_keys.add((hid, pos))
    return all_keys, villain_keys


def _prior_audit(hand_by_id, keys):
    model = ProfileRangeModel.load()
    flat = 0
    table = 0
    flat_sources = collections.Counter()
    for hid, pos in sorted(keys):
        hand = hand_by_id[hid]
        spot, action = _preflop_spot(hand, pos)
        vs = _pf_rival_pos(hand, pos, spot)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model._prior_grid(action, pos, vs)
        if any("FLAT_PRIOR" in str(item.message) for item in caught):
            flat += 1
            flat_sources[(action, pos, vs)] += 1
        else:
            table += 1
    return {
        "players": len(keys),
        "flat": flat,
        "table": table,
        "pct_flat": (100.0 * flat / len(keys)) if keys else 0.0,
        "flat_sources": flat_sources,
    }


def _effective_combos(model, args):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        vec = np.asarray(model.prob_vec(*args), dtype=float)
    values = vec[vec > 0.0]
    if values.size == 0:
        return 0.0
    return float((values.sum() ** 2) / (values * values).sum())


def _counter_dict(counter, limit=None):
    items = counter.most_common(limit) if limit else counter.most_common()
    return [
        {"key": list(key) if isinstance(key, tuple) else key, "n": int(n)}
        for key, n in items
    ]


def _same(value, expected):
    if isinstance(expected, float):
        return isinstance(value, (int, float)) and abs(value - expected) < 1e-9
    return value == expected


def _add(metrics, name, value, expected=None, section="", denominator="",
         filters="", definition="", source="", function="", note=""):
    if expected is None:
        status = "INFO"
    elif _same(value, expected):
        status = "REPRODUCED"
    else:
        status = "DOES_NOT_REPRODUCE"
    metrics.append({
        "name": name,
        "section": section,
        "value": value,
        "expected": expected,
        "status": status,
        "denominator": denominator,
        "filters": filters,
        "definition": definition,
        "source": source,
        "function": function,
        "note": note,
    })


def preflop_audit(hands):
    events = 0
    raw_b = collections.Counter()
    plan_counts = collections.Counter()
    strict_categories = collections.Counter()
    spot_pairs = collections.Counter()
    legacy_plan_diff = collections.Counter()
    training_diff = collections.Counter()
    coverage = collections.Counter()
    plan_unresolved = collections.Counter()

    for hand in hands:
        actions = actions_of(hand)
        for action in actions:
            if action.get("action") == "b":
                amount = action.get("amount") or 0.0
                raw_b["total"] += 1
                raw_b["gt_1bb" if amount > 1.0 else "le_1bb"] += 1
        for event in learn.preflop_events(hand):
            events += 1
            prefix = _prefix_before(actions, event.pos)
            plan = table_plan(prefix, event.pos)
            if plan.status == "resolved":
                key = plan.table_raise or plan.table_call or "unknown"
                plan_counts[key] += 1
            else:
                plan_unresolved[(plan.status, plan.reason)] += 1

            strict = first_decision(hand, event.pos)
            strict_categories[(strict.status, strict.denom,
                               strict.category)] += 1

            if strict.status == "resolved":
                old_spot = _preflop_spot(hand, event.pos)
                new_spot = (strict.denom, strict.category)
                if old_spot != new_spot:
                    spot_pairs[(old_spot, new_spot)] += 1

                vs = strict.context.last_aggressor \
                    if strict.context.raises_before else ""
                if strict.denom == "facing_open":
                    _r, _s, raise_status = _pf_table_lookup(
                        "3B", event.pos, vs)
                    _r, _s, call_status = _pf_table_lookup(
                        "Call_OR", event.pos, vs)
                    coverage[("facing_open", raise_status,
                              call_status)] += 1
                elif strict.denom == "facing_3bet":
                    _r, _s, raise_status = _pf_table_lookup(
                        "4B", event.pos, vs)
                    _r, _s, call_status = _pf_table_lookup(
                        "Call_3B", event.pos, vs)
                    coverage[("facing_3bet", raise_status,
                              call_status)] += 1

            old_n, old_vs, _old_amount = _preflop_raises(prefix, event.pos)
            old_limp = _legacy_limp(prefix, event.pos)
            if plan.status != "resolved":
                legacy_plan_diff["unresolved"] += 1
            else:
                n_diff = old_n != plan.raises_before
                limp_diff = old_limp != (plan.limps_before > 0)
                vs_diff = old_vs != plan.vs_pos
                if n_diff:
                    legacy_plan_diff["n_diff"] += 1
                if limp_diff:
                    legacy_plan_diff["limp_diff"] += 1
                if vs_diff:
                    legacy_plan_diff["vs_diff"] += 1
                if n_diff and vs_diff:
                    legacy_plan_diff["n_and_vs"] += 1
                if n_diff and not vs_diff:
                    legacy_plan_diff["n_only"] += 1
                if n_diff and not limp_diff and not vs_diff:
                    legacy_plan_diff["n_only_no_limp"] += 1
                if n_diff or limp_diff or vs_diff:
                    legacy_plan_diff["any"] += 1
                else:
                    legacy_plan_diff["same"] += 1

            legacy = first_decision(hand, event.pos, legacy=True)
            if not strict.resolved:
                training_diff["unresolved"] += 1
            elif (strict.training_category, strict.training_denom) != \
                    (event.category, event.denom):
                training_diff["different"] += 1
            else:
                training_diff["same"] += 1

    return {
        "events": events,
        "raw_b": raw_b,
        "plan_counts": plan_counts,
        "plan_unresolved": plan_unresolved,
        "strict_categories": strict_categories,
        "spot_pairs": spot_pairs,
        "legacy_plan_diff": legacy_plan_diff,
        "training_diff": training_diff,
        "coverage": coverage,
    }


def routes_audit():
    def read(rel):
        with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()

    asis = read("motor/asistente_live.py")
    rec = read("motor/recommend_loop.py")
    test = read("motor/test_multiway_soportado.py")

    references = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "motor")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            try:
                text = io.open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            if "recommend_loop" not in text and "recommend(" not in text:
                continue
            for no, line in enumerate(text.splitlines(), 1):
                if "recommend_loop" in line or re.search(r"\brecommend\s*\(",
                                                          line):
                    references.append({
                        "file": rel,
                        "line": no,
                        "text": line.strip(),
                    })

    return {
        "multiway_soportado": bool(rules.MULTIWAY_SOPORTADO),
        "politica": rules.POLITICA_MULTIWAY,
        "asistente_live_calls_rules_plan": "rules_plan(" in asis,
        "asistente_live_calls_select_best": "rules_select_best(" in asis,
        "asistente_live_uses_prob_vec": "range_model.prob_vec(" in asis,
        "asistente_live_uses_prob_vec_player": "prob_vec_player(" in asis,
        "asistente_live_uses_player_omega": "player_omega(" in asis,
        "asistente_live_imports_recommend": bool(
            re.search(r"from\s+\.recommend_loop\s+import\s+recommend\b", asis)
        ),
        "asistente_live_imports_equity_vs_rival": "_equity_vs_rival" in asis,
        "recommend_loop_defines_recommend": "def recommend(" in rec,
        "recommend_loop_builds_union": ".union(" in rec,
        "recommend_loop_has_multiway_builder": "_build_multiway_range" in rec,
        "test_allows_union": "union(" in test and "NO SOPORTADO" in test,
        "recommend_references": references,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="emitir el informe completo como JSON")
    args = parser.parse_args(argv)

    all_hands = learn.load_hands()
    reliable_hands = learn.load_hands(reliable_only=True)
    all_by_id = {hand.get("hand_id"): hand for hand in all_hands}

    metrics = []
    _add(metrics, "manos_total", len(all_hands), None, "datos",
         "lineas validas de hands_db.jsonl", "sin filtro",
         "manos con players y streets", "data/hands_db.jsonl",
         "learn.load_hands(reliable_only=False)")
    _add(metrics, "manos_fiables", len(reliable_hands), 877, "datos",
         "ventana fiable", "reliable_only=True",
         "manos fiables usadas por los modelos", "data/hands_db.jsonl",
         "learn.load_hands(reliable_only=True)")

    for name, hands in (("all", all_hands), ("reliable", reliable_hands)):
        result = multiway.metrica_politica(hands)
        _add(metrics, "multiway_%s_numerador" % name, result["numerador"],
             399 if name == "all" else 210, "multiway",
             "%s decisiones no-fold del hero" % result["denominador"],
             "se excluyen folds del hero",
             "decisiones del hero en multiway",
             "data/hands_db.jsonl", "multiway.metrica_politica")
        _add(metrics, "multiway_%s_denominador" % name,
             result["denominador"], 894 if name == "all" else 506,
             "multiway", "decisiones no-fold del hero",
             "se excluyen folds del hero",
             "denominador de politica multiway",
             "data/hands_db.jsonl", "multiway.metrica_politica")
        _add(metrics, "multiway_%s_porcentaje" % name,
             round(result["porcentaje"], 4),
             44.6309 if name == "all" else 41.5020, "multiway",
             "%d decisiones no-fold" % result["denominador"],
             "se excluyen folds del hero",
             "numerador / denominador de politica multiway",
             "data/hands_db.jsonl", "multiway.metrica_politica")

    pre = preflop_audit(all_hands)
    events = pre["events"]
    _add(metrics, "preflop_eventos", events, 7107, "preflop",
         "primeras decisiones preflop", "base completa",
         "eventos de primera decision por jugador",
         "data/hands_db.jsonl", "learn.preflop_events")
    _add(metrics, "preflop_b_total", pre["raw_b"]["total"], 178, "preflop",
         "acciones b crudas", "base completa", "acciones 'b' en preflop",
         "data/hands_db.jsonl", "actions_of")
    _add(metrics, "preflop_b_gt_1bb", pre["raw_b"]["gt_1bb"], 162, "preflop",
         "acciones b con amount > 1 BB", "base completa",
         "aperturas b de importe > BB", "data/hands_db.jsonl", "actions_of")

    plan_value = {
        "OR": pre["plan_counts"].get("OR", 0),
        "ROL": pre["plan_counts"].get("ROL", 0),
        "facing_open": pre["plan_counts"].get("3B", 0),
        "4B": pre["plan_counts"].get("4B", 0),
        "unresolved": sum(pre["plan_unresolved"].values()),
    }
    _add(metrics, "preflop_plan_distribucion", plan_value,
         {"OR": 3065, "ROL": 1563, "facing_open": 2329,
          "4B": 147, "unresolved": 3},
         "preflop", "%d eventos" % events,
         "prefijo estricto antes de cada primera decision",
         "table_plan sobre el prefijo de acciones; OR/ROL/facing_open/4B",
         "data/hands_db.jsonl", "preflop_contract.table_plan",
         "La lectura table_plan no reproduce la distribucion del informe.")

    facing_open = sum(n for key, n in pre["coverage"].items()
                      if key[0] == "facing_open")
    facing_open_exact = sum(n for key, n in pre["coverage"].items()
                            if key[0] == "facing_open"
                            and key[1] == "exact" and key[2] == "exact")
    facing_open_no_call = sum(n for key, n in pre["coverage"].items()
                              if key[0] == "facing_open"
                              and key[2] in ("missing",
                                             "fallback_other_vs"))
    _add(metrics, "preflop_facing_open", facing_open, 2329, "preflop",
         "%d decisiones con denom facing_open" % facing_open,
         "first_decision estricto; denom=facing_open",
         "decisiones que enfrentan una apertura",
         "data/hands_db.jsonl", "preflop_contract.first_decision")
    _add(metrics, "preflop_facing_open_exactas", facing_open_exact, 1249,
         "preflop", "%d decisiones facing_open" % facing_open,
         "3B exacta y Call_OR exacta",
         "cobertura exacta de raise y call", "data/hands_db.jsonl",
         "asistente_live._pf_table_lookup")
    _add(metrics, "preflop_call_or_sin_cobertura", facing_open_no_call, 1080,
         "preflop", "%d decisiones facing_open" % facing_open,
         "Call_OR missing o fallback",
         "spots sin tabla de call exacta", "data/hands_db.jsonl",
         "asistente_live._pf_table_lookup")

    facing_3bet = sum(n for key, n in pre["coverage"].items()
                      if key[0] == "facing_3bet")
    four_missing = sum(n for key, n in pre["coverage"].items()
                       if key[0] == "facing_3bet"
                       and key[1] == "missing" and key[2] == "missing")
    _add(metrics, "preflop_facing_3bet", facing_3bet, 147, "preflop",
         "%d decisiones con denom facing_3bet" % facing_3bet,
         "first_decision estricto; denom=facing_3bet",
         "decisiones que enfrentan un 3-bet", "data/hands_db.jsonl",
         "preflop_contract.first_decision")
    _add(metrics, "preflop_4bet_sin_tablas", four_missing, 78, "preflop",
         "%d decisiones facing_3bet" % facing_3bet,
         "4B y Call_3B missing",
         "spots de 4-bet sin tabla exacta", "data/hands_db.jsonl",
         "asistente_live._pf_table_lookup")

    _add(metrics, "preflop_spot_divergencias_total",
         sum(pre["spot_pairs"].values()), 468, "preflop", "%d eventos" % events,
         "_preflop_spot legacy != first_decision estricto",
         "diferencias totales de etiqueta del rival",
         "data/hands_db.jsonl",
         "asistente_live._preflop_spot / preflop_contract.first_decision")
    pair_468 = pre["spot_pairs"].get(
        (("facing_open", "call_open"), ("no_raise", "limp")), 0)
    _add(metrics, "preflop_spot_par_call_open_a_limp", pair_468, 468,
         "preflop", "%d eventos" % events,
         "par legacy (facing_open,call_open) -> (no_raise,limp)",
         "el 468 del informe es este par, no el total de divergencias",
         "data/hands_db.jsonl",
         "asistente_live._preflop_spot / preflop_contract.first_decision")

    diff = pre["legacy_plan_diff"]
    _add(metrics, "preflop_legacy_plan_total", diff.get("any", 0), 468,
         "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "n_raises, limp o vs_pos distinto de table_plan",
         "divergencias entre _preflop_raises+limp y plan estricto",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")
    _add(metrics, "preflop_legacy_plan_n_y_vs", diff.get("n_and_vs", 0), 431,
         "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "n_raises y vs_pos distintos",
         "divergencias dobles de estado del hero",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")
    _add(metrics, "preflop_legacy_plan_solo_n", diff.get("n_only", 0), 37,
         "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "solo n_raises distinto", "divergencias simples de conteo",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")

    _add(metrics, "preflop_legacy_plan_n_diff", diff.get("n_diff", 0), None,
         "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "n_raises distinto", "detalle de la medicion anterior",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")
    _add(metrics, "preflop_legacy_plan_limp_diff", diff.get("limp_diff", 0),
         None, "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "limp distinto", "detalle de la medicion anterior",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")
    _add(metrics, "preflop_legacy_plan_vs_diff", diff.get("vs_diff", 0),
         None, "preflop", "%d eventos resueltos" % (events - diff.get(
             "unresolved", 0)),
         "vs_pos distinto", "detalle de la medicion anterior",
         "data/hands_db.jsonl",
         "asistente_live._preflop_raises / preflop_contract.table_plan")

    _add(metrics, "preflop_training_diff", pre["training_diff"].get(
        "different", 0), 54, "preflop", "%d eventos" % events,
         "categoria estricta de entrenamiento != preflop_events legacy",
         "diferencias de categoria de entrenamiento",
         "data/hands_db.jsonl",
         "preflop_contract.first_decision / learn.preflop_events")
    _add(metrics, "preflop_training_unresolved", pre["training_diff"].get(
        "unresolved", 0), 44, "preflop", "%d eventos" % events,
         "first_decision estricto no resuelto",
         "eventos que el contrato no puede clasificar",
         "data/hands_db.jsonl",
         "preflop_contract.first_decision")

    all_keys, villain_keys = _postflop_action_keys(all_hands)
    prior_all = _prior_audit(all_by_id, all_keys)
    prior_villains = _prior_audit(all_by_id, villain_keys)
    _add(metrics, "prior_jugadores_con_acciones_postflop",
         prior_all["players"], 2396, "postflop",
         "%d pares (hand_id,pos) con accion postflop" % prior_all["players"],
         "incluye al hero; sin filtrar active",
         "jugadores con al menos una accion postflop",
         "data/hands_db.jsonl", "_postflop_action_keys")
    _add(metrics, "prior_flat_prior", prior_all["flat"], 1881, "postflop",
         "%d jugadores con accion postflop" % prior_all["players"],
         "_prior_grid emite warning FLAT_PRIOR",
         "uso del prior plano del modelo preflop",
         "data/profile_ranges.json", "ProfileRangeModel._prior_grid")
    _add(metrics, "prior_tabla_posicional", prior_all["table"], 515,
         "postflop", "%d jugadores con accion postflop" % prior_all["players"],
         "_prior_grid encuentra tabla simple o de par",
         "prior posicional disponible", "data/preflop_matrices.json",
         "ProfileRangeModel._prior_grid")
    _add(metrics, "prior_villanos_con_acciones_postflop",
         prior_villains["players"], 1992, "postflop",
         "%d pares (hand_id,pos) de no-hero" % prior_villains["players"],
         "excluye al hero; sin filtrar active",
         "villanos con al menos una accion postflop",
         "data/hands_db.jsonl", "_postflop_action_keys",
         "El informe usa 2.396 para 'villanos', pero esa base incluye al "
         "hero. El subconjunto de villanos es 1.992.")
    _add(metrics, "prior_flat_prior_villanos", prior_villains["flat"], 1572,
         "postflop", "%d villanos con accion postflop"
         % prior_villains["players"],
         "_prior_grid emite warning FLAT_PRIOR; excluye hero",
         "uso del prior plano en villanos",
         "data/profile_ranges.json", "ProfileRangeModel._prior_grid",
         "El 1.881 del informe incluye al hero; en villanos es 1.572/1.992.")
    _add(metrics, "prior_flat_prior_pct", round(prior_all["pct_flat"], 4),
         78.5058, "postflop", "%d jugadores" % prior_all["players"],
         "FLAT_PRIOR / total", "porcentaje de prior plano",
         "data/profile_ranges.json", "ProfileRangeModel._prior_grid")

    model = ProfileRangeModel.load()
    effective = {
        "3bet_UTG_missing": _effective_combos(
            model, ("TIBURON", "facing_open", "3bet", "UTG", "")),
        "call_open_CO_vs_BTN_missing": _effective_combos(
            model, ("TIBURON", "facing_open", "call_open", "CO", "BTN")),
        "limp_BB_missing": _effective_combos(
            model, ("TIBURON", "no_raise", "limp", "BB", "")),
    }
    _add(metrics, "prior_combos_efectivos", effective, None, "postflop",
         "1326 combos; (sum w)^2 / sum w^2", "prior FLAT_PRIOR",
         "combos efectivos tras normalizar el rango",
         "data/profile_ranges.json", "ProfileRangeModel.prob_vec")

    equity_cases = [
        ("flush_draw", ["Ah", "Kh"], ["Qh", "7h", "2c"]),
        ("overpair", ["As", "Ad"], ["Qh", "7h", "2c"]),
        ("gutshot", ["9s", "8s"], ["Qh", "7h", "2c"]),
    ]
    equity_detail = {}
    for name, hero, board in equity_cases:
        static = equity_vs_range(hero, board)[0]
        showdown = runout_equity(hero, board, n_runouts=200,
                                 n_combos=200, seed=7)
        equity_detail[name] = {
            "static": static,
            "runout": showdown,
            "delta": showdown - static,
        }
        _add(metrics, "equity_%s_static" % name, round(static, 6), None,
             "equity", "rango uniforme", "board actual, sin runout",
             "equity actual del hero", "data/hands_db.jsonl",
             "situation.equity_vs_range")
        _add(metrics, "equity_%s_runout" % name, round(showdown, 6), None,
             "equity", "200 runouts, 200 combos, seed 7",
             "rango uniforme", "equity a showdown con turn/river",
             "data/hands_db.jsonl", "decision.runout_equity")

    _add(metrics, "equity_flush_draw_static", round(
        equity_detail["flush_draw"]["static"], 4), 0.5962, "equity",
        "rango uniforme", "board actual", "equity actual del proyecto",
        "data/hands_db.jsonl", "situation.equity_vs_range")
    _add(metrics, "equity_flush_draw_runout", round(
        equity_detail["flush_draw"]["runout"], 4), 0.7264, "equity",
        "200 runouts", "rango uniforme", "equity a showdown",
        "data/hands_db.jsonl", "decision.runout_equity")
    _add(metrics, "equity_overpair_static", round(
        equity_detail["overpair"]["static"], 4), 0.9662, "equity",
        "rango uniforme", "board actual", "equity actual del proyecto",
        "data/hands_db.jsonl", "situation.equity_vs_range")
    _add(metrics, "equity_overpair_runout", round(
        equity_detail["overpair"]["runout"], 4), 0.8557, "equity",
        "200 runouts", "rango uniforme", "equity a showdown",
        "data/hands_db.jsonl", "decision.runout_equity")
    _add(metrics, "equity_gutshot_static", round(
        equity_detail["gutshot"]["static"], 4), 0.1818, "equity",
        "rango uniforme", "board actual", "equity actual del proyecto",
        "data/hands_db.jsonl", "situation.equity_vs_range")
    _add(metrics, "equity_gutshot_runout", round(
        equity_detail["gutshot"]["runout"], 4), 0.3048, "equity",
        "200 runouts", "rango uniforme", "equity a showdown",
        "data/hands_db.jsonl", "decision.runout_equity")

    routes = routes_audit()
    _add(metrics, "multiway_soportado", routes["multiway_soportado"], False,
         "rutas", "1 flag", "rules.MULTIWAY_SOPORTADO",
         "flag de soporte multiway", "motor/rules.py", "rules")
    _add(metrics, "asistente_live_usa_prob_vec_player",
         routes["asistente_live_uses_prob_vec_player"], False, "rutas",
         "asistente_live.py", "busqueda de texto",
         "la ruta live usa prob_vec_player",
         "motor/asistente_live.py", "auditoria estatica")
    _add(metrics, "asistente_live_importa_recommend",
         routes["asistente_live_imports_recommend"], False, "rutas",
         "asistente_live.py", "busqueda de texto",
         "la ruta live importa recommend",
         "motor/asistente_live.py", "auditoria estatica")
    _add(metrics, "recommend_loop_usa_union",
         routes["recommend_loop_builds_union"], True, "rutas",
         "recommend_loop.py", "busqueda de texto",
         "el constructor multiway usa union",
         "motor/recommend_loop.py", "auditoria estatica")

    coverage_summary = preflop.audit_engine_coverage()
    coverage_counts = {
        key: len(value) for key, value in coverage_summary.items()
    }
    _add(metrics, "preflop_tablas_cobertura", coverage_counts,
         {"exact": 107, "alias": 1, "intentional_missing": 2,
          "impossible_missing": 82, "coverage_gap": 30,
          "unclassified_missing": 0}, "preflop", "consultas del motor",
         "inventario de claves", "cobertura estatica de tablas",
         "data/preflop_matrices.json", "preflop.audit_engine_coverage")

    data_meta = [_file_meta(path) for path in DATA_FILES]
    header = {
        "script": "tools/auditar_estrategia_reproducible.py",
        "report": REPORT_DOC,
        "commit": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "python": sys.version.split()[0],
        "data": data_meta,
    }
    details = {
        "preflop_plan_counts": _counter_dict(pre["plan_counts"]),
        "preflop_plan_unresolved": _counter_dict(pre["plan_unresolved"]),
        "preflop_strict_categories": _counter_dict(pre["strict_categories"]),
        "preflop_coverage": _counter_dict(pre["coverage"]),
        "preflop_spot_pairs": _counter_dict(pre["spot_pairs"], 20),
        "legacy_plan_diff": dict(pre["legacy_plan_diff"]),
        "training_diff": dict(pre["training_diff"]),
        "prior_all": {
            "players": prior_all["players"],
            "flat": prior_all["flat"],
            "table": prior_all["table"],
            "pct_flat": prior_all["pct_flat"],
            "top_flat_sources": _counter_dict(
                prior_all["flat_sources"], 12),
        },
        "prior_villains": {
            "players": prior_villains["players"],
            "flat": prior_villains["flat"],
            "table": prior_villains["table"],
            "pct_flat": prior_villains["pct_flat"],
        },
        "equity": equity_detail,
        "routes": routes,
    }
    payload = {"meta": header, "metrics": metrics, "details": details}

    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2,
                         sort_keys=True))
        return 0

    print("=" * 78)
    print("AUDITORIA REPRODUCIBLE HU/MW  (solo lectura)")
    print("=" * 78)
    print("commit: %s" % (header["commit"] or "NO GIT"))
    print("arbol: %s" % ("SUCIO" if header["dirty"] else "LIMPIO"))
    print("python: %s" % header["python"])
    print("informe: %s" % REPORT_DOC)
    print("")
    print("DATOS")
    for item in data_meta:
        if item["exists"]:
            print("  %-30s %10d bytes  %s" % (
                item["path"], item["bytes"], item["sha256"][:16]))
        else:
            print("  %-30s AUSENTE" % item["path"])
    print("")
    print("METRICAS")
    for item in metrics:
        expected = "" if item["expected"] is None else \
            " expected=%r" % (item["expected"],)
        print("  [%-18s] %-36s value=%r%s"
              % (item["status"], item["name"], item["value"], expected))
        print("      denom=%s | filtro=%s" % (
            item["denominator"], item["filters"]))
        print("      def=%s | fuente=%s | fn=%s"
              % (item["definition"], item["source"], item["function"]))
        if item["note"]:
            print("      nota=%s" % item["note"])
    print("")
    print("DETALLE PREFLOP")
    print("  plan_counts:", dict(pre["plan_counts"]))
    print("  plan_unresolved:", dict(pre["plan_unresolved"]))
    print("  legacy_plan_diff:", dict(pre["legacy_plan_diff"]))
    print("  training_diff:", dict(pre["training_diff"]))
    print("  top spot_pairs:")
    for key, n in pre["spot_pairs"].most_common(12):
        print("    %6d  %s -> %s" % (n, key[0], key[1]))
    print("")
    print("DETALLE PRIOR")
    print("  todos     : %d jugadores, flat=%d, tabla=%d (%.2f%%)"
          % (prior_all["players"], prior_all["flat"], prior_all["table"],
             prior_all["pct_flat"]))
    print("  villanos  : %d jugadores, flat=%d, tabla=%d (%.2f%%)"
          % (prior_villains["players"], prior_villains["flat"],
             prior_villains["table"], prior_villains["pct_flat"]))
    print("  flat top  :")
    for key, n in prior_all["flat_sources"].most_common(8):
        print("    %6d  %s" % (n, key))
    print("  combos efectivos:", effective)
    print("")
    print("DETALLE EQUITY")
    for name, value in equity_detail.items():
        print("  %-12s static=%.6f runout=%.6f delta=%+.6f"
              % (name, value["static"], value["runout"], value["delta"]))
    print("")
    print("RUTAS")
    print("  MULTIWAY_SOPORTADO=%r politica=%r" % (
        routes["multiway_soportado"], routes["politica"]))
    print("  asistente_live: plan=%r select_best=%r prob_vec=%r "
          "prob_vec_player=%r omega=%r"
          % (routes["asistente_live_calls_rules_plan"],
             routes["asistente_live_calls_select_best"],
             routes["asistente_live_uses_prob_vec"],
             routes["asistente_live_uses_prob_vec_player"],
             routes["asistente_live_uses_player_omega"]))
    print("  asistente_live importa recommend=%r; _equity_vs_rival=%r"
          % (routes["asistente_live_imports_recommend"],
             routes["asistente_live_imports_equity_vs_rival"]))
    print("  recommend_loop: define recommend=%r builder=%r union=%r"
          % (routes["recommend_loop_defines_recommend"],
             routes["recommend_loop_has_multiway_builder"],
             routes["recommend_loop_builds_union"]))
    print("  referencias recommend/union (primeras 12):")
    for ref in routes["recommend_references"][:12]:
        print("    %s:%d  %s" % (ref["file"], ref["line"], ref["text"]))
    print("")
    print("No se ha escrito en data/, no se ha ejecutado --apply, "
          "no se ha cambiado MULTIWAY_SOPORTADO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
