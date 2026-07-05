#!/usr/bin/env python3
"""Sistema de lotería de Pablo — EuroJackpot (System 5Z+3E) + Lotto 6aus49.

Subcomandos:
  genera    ej|lotto --fecha YYYY-MM-DD|D.M.YY [--seed N]
  resultado ej|lotto --numeros "N-N-..." [--euros "E-E"] [--fecha ...] [--premio X.XX] [--clase Kl.X]
  resumen
  audita    [--tickets N]

Todo el estado vive en config.json, frequencies.json, pending_tickets.json,
tracking.csv y draw_history.csv, en el mismo directorio que este script.
"""
import argparse
import csv
import json
import math
import random
import sys
from datetime import date, datetime
from itertools import combinations
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG_F = BASE / "config.json"
FREQS_F = BASE / "frequencies.json"
PENDING_F = BASE / "pending_tickets.json"
TRACKING_F = BASE / "tracking.csv"
HISTORY_F = BASE / "draw_history.csv"

VERSION = "loteria.py v1.3"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
GAME = {"ej": "eurojackpot", "lotto": "lotto6aus49"}

# Tablas de premios (medias históricas; el importe real es pari-mutuel y se
# registra con --premio). Probabilidades verificadas 2026-07-04.
EJ_PRIZE_TABLE = {
    (5, 2): ("Kl.1", 30_000_000), (5, 1): ("Kl.2", 800_000), (5, 0): ("Kl.3", 150_000),
    (4, 2): ("Kl.4", 4_000), (4, 1): ("Kl.5", 230), (4, 0): ("Kl.6", 100),
    (3, 2): ("Kl.7", 60), (3, 1): ("Kl.8", 20), (2, 2): ("Kl.9", 17),
    (3, 0): ("Kl.10", 16), (1, 2): ("Kl.11", 10), (2, 1): ("Kl.12", 8),
}
EJ_REALISTIC = {"Kl.5", "Kl.6", "Kl.7", "Kl.8", "Kl.9", "Kl.10", "Kl.11", "Kl.12"}
# lotto: aciertos -> (clase sin SZ, media sin SZ, clase con SZ, media con SZ)
LOTTO_PRIZE = {
    6: ("Kl.2", 1_000_000, "Kl.1", 10_000_000),
    5: ("Kl.4", 3_500, "Kl.3", 10_000),
    4: ("Kl.6", 45, "Kl.5", 200),
    3: ("Kl.8", 10, "Kl.7", 20),
    2: (None, 0, "Kl.9", 6),
}


# ---------------------------------------------------------------- utilidades
def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_fecha(s):
    """Acepta ISO (2026-07-03) o formato de Pablo (3.7.26)."""
    s = s.strip()
    if "." in s:
        d, m, y = (int(x) for x in s.split("."))
        return date(y + 2000 if y < 100 else y, m, d)
    return date.fromisoformat(s)


def parse_nums(s):
    return sorted(int(x) for x in s.replace(",", "-").replace(" ", "-").split("-") if x)


def read_tracking():
    with open(TRACKING_F, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv_line(path, values):
    row = ",".join(str(v) for v in values)
    if "," in "".join(str(v) for v in values):
        sys.exit(f"ERROR interno: un campo contiene coma: {values}")
    text = path.read_text(encoding="utf-8")
    sep = "" if text.endswith("\n") else "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(sep + row + "\n")


# ------------------------------------------------------------- modelo
def weight_for(n, cfg, freq_map, is_euro=False):
    """Peso de muestreo: base (uniforme o frecuencia) × factor de popularidad."""
    p = cfg["popularity_penalties"]
    base = 1.0 if cfg.get("weighting", "uniform") == "uniform" else float(freq_map[str(n)])
    if is_euro:
        return base * (p["euro_7_specific"] if n == 7 else 1.0)
    if n == 7:
        return base * p["main_7_specific"]
    if n == 13:
        return base * p["main_13_specific"]
    if n <= 31:
        return base * p["main_1_to_31"]
    return base * p["main_32_to_50"]


def violations(nums, f):
    """Lista de filtros que incumple la combinación (vacía = pasa)."""
    v = []
    d = len({(n - 1) // 10 for n in nums})
    if d < f["decades_min"]:
        v.append("decades_min")
    if "decades_max" in f and d > f["decades_max"]:
        v.append("decades_max")
    e = sum(1 for n in nums if n % 2 == 0)
    if e < f["even_min"] or e > f["even_max"]:
        v.append("even")
    s = sum(nums)
    if s < f["sum_min"]:
        v.append("sum_min")
    if s > f["sum_max"]:
        v.append("sum_max")
    sn = sorted(nums)
    if sum(1 for i in range(len(sn) - 1) if sn[i + 1] - sn[i] == 1) > f["max_consecutive_pairs"]:
        v.append("consec")
    if sum(1 for n in nums if n <= 31) > f["max_birthday_range_numbers"]:
        v.append("birthday")
    return v


def sample(rng, pool, weights, k):
    pop = list(pool)
    w = list(weights)
    out = []
    for _ in range(k):
        i = rng.choices(range(len(pop)), weights=w)[0]
        out.append(pop.pop(i))
        w.pop(i)
    return sorted(out)


def game_params(gkey, cfg, freqs):
    if gkey == "eurojackpot":
        return range(1, 51), 5, freqs["eurojackpot"]["main_numbers"], cfg["eurojackpot"]["filters"]
    return range(1, 50), 6, freqs["lotto6aus49"]["numbers"], cfg["lotto6aus49"]["filters"]


def gen_ticket(rng, gkey, cfg, freqs, max_attempts=500):
    """Genera una combinación que pasa los filtros. Sin fallback silencioso:
    si los filtros fueran incompatibles (como el sum_min=100 de 2026-05-26),
    aborta con error en vez de degradar."""
    pool, k, fmap, filt = game_params(gkey, cfg, freqs)
    weights = [weight_for(n, cfg, fmap) for n in pool]
    for attempt in range(1, max_attempts + 1):
        nums = sample(rng, pool, weights, k)
        if not violations(nums, filt):
            break
    else:
        sys.exit(f"ERROR: {max_attempts} intentos sin pasar los filtros de {gkey}. "
                 "Filtros incompatibles entre sí: revisar config.json. NO se ha generado nada.")
    out = {"numbers": nums, "attempts": attempt}
    if gkey == "eurojackpot":
        emap = freqs["eurojackpot"]["euro_numbers"]
        ew = [weight_for(n, cfg, emap, is_euro=True) for n in range(1, 13)]
        euros = sample(rng, range(1, 13), ew, 3)
        out["euros"] = euros
        out["combos"] = [sorted(p) for p in combinations(euros, 2)]
    return out


# ------------------------------------------------- valor esperado teórico
def p_main_ej(m):
    return math.comb(5, m) * math.comb(45, 5 - m) / math.comb(50, 5)


def p_euro_pair(e):
    return math.comb(2, e) * math.comb(10, 2 - e) / math.comb(12, 2)


def p_lotto(k):
    return math.comb(6, k) * math.comb(43, 6 - k) / math.comb(49, 6)


def expected_rate(gkey):
    """Retorno esperado por € jugado, solo clases 'realistas' (EJ Kl.5-12;
    lotto 2-5 aciertos). Es la vara de medir de los milestones."""
    if gkey == "eurojackpot":
        per_combo = sum(p_main_ej(m) * p_euro_pair(e) * avg
                        for (m, e), (kl, avg) in EJ_PRIZE_TABLE.items() if kl in EJ_REALISTIC)
        return 3 * per_combo / 6.60
    per_draw = sum(p_lotto(k) * (0.9 * avg_no + 0.1 * avg_sz)
                   for k, (_, avg_no, _, avg_sz) in LOTTO_PRIZE.items() if k <= 5)
    return per_draw / 1.80


def p_prize_per_draw(gkey):
    if gkey == "lotto6aus49":
        return sum(p_lotto(k) for k in (3, 4, 5, 6))
    # EJ System 5+3E: P(alguna de las 3 combos con premio)
    # 3+ aciertos: hay clase con cualquier nº de euros
    p = p_main_ej(5) + p_main_ej(4) + p_main_ej(3)
    # 2 aciertos: premio si ≥1 de los 3 euros sale (Kl.12/Kl.9)
    p += p_main_ej(2) * (1 - math.comb(9, 2) / math.comb(12, 2))
    # 1 acierto: premio solo si los 2 euros sorteados están entre los 3 (Kl.11)
    p += p_main_ej(1) * (math.comb(3, 2) / math.comb(12, 2))
    return p


# ------------------------------------------------------------- comprobación
def check_ej(my_nums, my_euros, draw_nums, draw_euros):
    """Devuelve (hits_main, hits_euro_max, [(clase, media, par), ...])."""
    mn = len(set(my_nums) & set(draw_nums))
    results = []
    he = 0
    for pair in combinations(sorted(my_euros), 2):
        e = len(set(pair) & set(draw_euros))
        he = max(he, e)
        hit = EJ_PRIZE_TABLE.get((mn, e))
        if hit:
            results.append((hit[0], hit[1], list(pair)))
    return mn, he, results


def kl_num(kl):
    return int(kl.split(".")[1])


# ================================================================ comandos
def cmd_genera(args):
    cfg, freqs = load_json(CONFIG_F), load_json(FREQS_F)
    gkey = GAME[args.juego]
    d = parse_fecha(args.fecha)
    dia = DIAS[d.weekday()]
    if dia not in cfg[gkey]["draw_days"]:
        sys.exit(f"ERROR: {d.isoformat()} es {dia}; {gkey} se sortea {' y '.join(cfg[gkey]['draw_days'])}.")
    pending = load_json(PENDING_F)
    if any(t["game"] == gkey and t["draw_date"] == d.isoformat() for t in pending):
        sys.exit(f"ERROR: ya hay un ticket {gkey} pendiente para {d.isoformat()}. No se genera otro.")

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 10**9)
    rng = random.Random(seed)
    t = gen_ticket(rng, gkey, cfg, freqs)

    ticket = {"game": gkey, "draw_date": d.isoformat(), "draw_day": dia, "numbers": t["numbers"]}
    if gkey == "eurojackpot":
        ticket["euros"] = t["euros"]
        ticket["combos"] = t["combos"]
    ticket["generated_at"] = datetime.now().isoformat(timespec="seconds")
    ticket["seed"] = seed
    ticket["generator"] = VERSION
    pending.append(ticket)
    pending.sort(key=lambda x: (x["draw_date"], x["game"]))
    save_json(PENDING_F, pending)

    print(f"{gkey} — sorteo {d.isoformat()} ({dia})")
    print(f"  números: {'-'.join(map(str, t['numbers']))}")
    if gkey == "eurojackpot":
        print(f"  euros:   {'-'.join(map(str, t['euros']))}  (combos: {t['combos']})")
    print(f"  semilla: {seed}  intentos: {t['attempts']}  → guardado en pending_tickets.json")


def cmd_resultado(args):
    cfg = load_json(CONFIG_F)
    gkey = GAME[args.juego]
    pending = load_json(PENDING_F)
    cands = [t for t in pending if t["game"] == gkey]
    if args.fecha:
        want = parse_fecha(args.fecha).isoformat()
        cands = [t for t in cands if t["draw_date"] == want]
    if not cands:
        sys.exit(f"ERROR: no hay ticket {gkey} pendiente" + (f" para {want}" if args.fecha else "") + ".")
    if len(cands) > 1:
        fechas = ", ".join(t["draw_date"] for t in cands)
        sys.exit(f"ERROR: hay varios {gkey} pendientes ({fechas}); precisa --fecha.")
    ticket = cands[0]

    draw = parse_nums(args.numeros)
    n_needed = 5 if gkey == "eurojackpot" else 6
    top = 50 if gkey == "eurojackpot" else 49
    if len(draw) != n_needed or len(set(draw)) != n_needed or not all(1 <= n <= top for n in draw):
        sys.exit(f"ERROR: se esperan {n_needed} números distintos entre 1 y {top}: {draw}")

    premio = None if args.premio is None else float(str(args.premio).replace(",", "."))

    if gkey == "eurojackpot":
        if not args.euros:
            sys.exit("ERROR: falta --euros \"E-E\" del sorteo.")
        draw_e = parse_nums(args.euros)
        if len(draw_e) != 2 or len(set(draw_e)) != 2 or not all(1 <= n <= 12 for n in draw_e):
            sys.exit(f"ERROR: se esperan 2 eurozahlen distintas entre 1 y 12: {draw_e}")
        mn, he, results = check_ej(ticket["numbers"], ticket["euros"], draw, draw_e)
        best = min((r[0] for r in results), key=kl_num, default="none")
        teorico = sum(r[1] for r in results)
        for kl, avg, pair in results:
            print(f"  combo euros {pair}: {kl} (media ~{avg}€)")
        if results and premio is None:
            print(f"PREMIO detectado: {len(results)} combo(s), mejor clase {best}, media teórica ~{teorico}€.")
            print("Pásame el importe REAL cobrado y repite con --premio X.XX (no se ha escrito nada).")
            sys.exit(2)
        row_e = ("-".join(map(str, ticket["euros"])), "-".join(map(str, draw_e)), he)
    else:
        mn = len(set(ticket["numbers"]) & set(draw))
        hit = LOTTO_PRIZE.get(mn)
        best = hit[0] if hit and hit[0] else "none"
        teorico = hit[1] if hit else 0
        if best != "none" and premio is None:
            print(f"PREMIO detectado: {mn} aciertos → {best} (media ~{teorico}€; con Superzahl sería {hit[2]}).")
            print("Pásame el importe REAL cobrado y repite con --premio X.XX (no se ha escrito nada).")
            sys.exit(2)
        row_e = ("", "-".join(map(str, draw)), "")

    if premio is None:
        premio = 0.0
    if args.clase:
        best = args.clase
    if premio > 0 and best == "none":
        sys.exit("ERROR: --premio > 0 pero ninguna clase detectada; indica --clase (p. ej. Kl.9 con Superzahl).")

    cost = cfg[gkey]["cost_per_draw"]
    if gkey == "eurojackpot":
        values = [ticket["draw_date"], gkey, ticket["draw_day"],
                  "-".join(map(str, ticket["numbers"])), row_e[0],
                  "-".join(map(str, draw)), row_e[1],
                  mn, row_e[2], best, f"{premio:.2f}", f"{cost:.2f}"]
        hist = [ticket["draw_date"], gkey, "-".join(map(str, draw)), row_e[1]]
    else:
        values = [ticket["draw_date"], gkey, ticket["draw_day"],
                  "-".join(map(str, ticket["numbers"])), "",
                  "-".join(map(str, draw)), "", mn, "", best, f"{premio:.2f}", f"{cost:.2f}"]
        hist = [ticket["draw_date"], gkey, "-".join(map(str, draw)), ""]

    append_csv_line(TRACKING_F, values)
    append_csv_line(HISTORY_F, hist)
    pending = [t for t in pending if not (t["game"] == gkey and t["draw_date"] == ticket["draw_date"])]
    save_json(PENDING_F, pending)

    print(f"{gkey} {ticket['draw_date']}: {mn} aciertos"
          + (f" + {row_e[2]} euros" if gkey == "eurojackpot" else "")
          + f" → {best}, {premio:.2f}€ (coste {cost:.2f}€). Registrado.")

    # --- comprobaciones automáticas post-escritura ---
    rows = read_tracking()
    n_game = sum(1 for r in rows if r["game"] == gkey)
    if n_game in cfg["review_milestones"]:
        print(f"\n*** MILESTONE: {gkey} llega a {n_game} sorteos → ejecutar `python3 loteria.py audita` ***")
    streak = 0
    for r in reversed([r for r in rows if r["game"] == gkey]):
        if float(r["prize_eur"]) == 0:
            streak += 1
        else:
            break
    threshold = cfg["alert_no_prize_streak"][gkey]
    if streak >= threshold:
        print(f"*** ALERTA: {streak} sorteos de {gkey} sin premio (umbral p<5%: {threshold}) → revisar sistema ***")


def cmd_resumen(_args):
    cfg = load_json(CONFIG_F)
    rows = read_tracking()
    print(f"RESUMEN — {len(rows)} sorteos registrados")
    tot_c = tot_p = 0.0
    for gkey in ("eurojackpot", "lotto6aus49"):
        g = [r for r in rows if r["game"] == gkey]
        if not g:
            continue
        cost = sum(float(r["cost_eur"]) for r in g)
        prize = sum(float(r["prize_eur"]) for r in g)
        tot_c += cost
        tot_p += prize
        won = [r for r in g if float(r["prize_eur"]) > 0]
        streak = 0
        for r in reversed(g):
            if float(r["prize_eur"]) == 0:
                streak += 1
            else:
                break
        rate = expected_rate(gkey)
        nm = [m for m in cfg["review_milestones"] if m > len(g)]
        print(f"\n{gkey}: {len(g)} sorteos, gasto {cost:.2f}€, premios {prize:.2f}€ "
              f"({len(won)} premiados) → retorno {prize / cost * 100:.1f}%")
        print(f"  esperado (clases bajas): {rate * 100:.1f}%  |  racha actual sin premio: {streak}"
              f" (alerta a {cfg['alert_no_prize_streak'][gkey]})"
              + (f"  |  próximo milestone: {nm[0]} (faltan {nm[0] - len(g)})" if nm else ""))
        for r in won:
            print(f"  premio: {r['date']} {r['best_class']} {float(r['prize_eur']):.2f}€")
    if tot_c:
        print(f"\nTOTAL: gasto {tot_c:.2f}€, premios {tot_p:.2f}€ → retorno {tot_p / tot_c * 100:.1f}%")
    pending = load_json(PENDING_F)
    today = date.today().isoformat()
    overdue = [t for t in pending if t["draw_date"] <= today]
    print(f"Pendientes: {len(pending)}"
          + (f" — ¡{len(overdue)} con sorteo ya celebrado sin resultado: "
             + ", ".join(f"{t['game']} {t['draw_date']}" for t in overdue) + "!" if overdue else ""))


def cmd_audita(args):
    cfg, freqs = load_json(CONFIG_F), load_json(FREQS_F)
    rows = read_tracking()
    pending = load_json(PENDING_F)
    NT = args.tickets
    rng = random.Random(20260704)  # semilla fija: auditoría reproducible

    print("== 1. Integridad de frequencies.json ==")
    s_main = sum(freqs["eurojackpot"]["main_numbers"].values())
    s_euro = sum(freqs["eurojackpot"]["euro_numbers"].values())
    n_ej = freqs["eurojackpot"]["total_draws"]
    print(f"  EJ main {s_main} (= {n_ej}×5: {'OK' if s_main == n_ej * 5 else 'MAL'}), "
          f"euro {s_euro} (= {n_ej}×2: {'OK' if s_euro == n_ej * 2 else 'MAL'})")
    s_lo = sum(freqs["lotto6aus49"]["numbers"].values())
    n_lo = freqs["lotto6aus49"]["total_draws"]
    print(f"  Lotto {s_lo} (= {n_lo}×6: {'OK' if s_lo == n_lo * 6 else 'MAL'})")

    print(f"\n== 2. Sesgo del generador (baseline MC {NT} tickets, weighting={cfg.get('weighting', 'uniform')}) ==")
    for gkey in ("eurojackpot", "lotto6aus49"):
        pool, k, fmap, filt = game_params(gkey, cfg, freqs)
        inc, euro_inc, rej = {n: 0 for n in pool}, {n: 0 for n in range(1, 13)}, {}
        for _ in range(NT):
            t = gen_ticket(rng, gkey, cfg, freqs)
            for n in t["numbers"]:
                inc[n] += 1
            for n in t.get("euros", []):
                euro_inc[n] += 1
        # perfil de rechazo de filtros sobre candidatos crudos
        weights = [weight_for(n, cfg, fmap) for n in pool]
        NRAW = 20000
        raw_fail = 0
        for _ in range(NRAW):
            v = violations(sample(rng, pool, weights, k), filt)
            if v:
                raw_fail += 1
                for x in v:
                    rej[x] = rej.get(x, 0) + 1
        played = [parse_nums(r["my_numbers"]) for r in rows if r["game"] == gkey]
        pend = [t["numbers"] for t in pending if t["game"] == gkey]
        tickets = played + pend
        print(f"  {gkey}: paso de filtros {100 - raw_fail / NRAW * 100:.0f}%; rechazos/100 candidatos: "
              + ", ".join(f"{k_}={v / NRAW * 100:.0f}" for k_, v in sorted(rej.items(), key=lambda x: -x[1])))
        if not tickets:
            continue

        def overuse(tkts, baseline_inc, domain):
            n = len(tkts)
            flagged = []
            for num in domain:
                p = baseline_inc[num] / NT
                obs = sum(1 for t in tkts if num in t)
                pv = sum(math.comb(n, i) * p**i * (1 - p)**(n - i) for i in range(obs, n + 1))
                if pv < 0.05 and obs >= 2:
                    flagged.append((pv, num, obs, p * n))
            return ", ".join(f"nº{num} {obs}× vs {e:.1f} (p={pv:.3f})"
                             for pv, num, obs, e in sorted(flagged)) or "ninguno"

        print(f"    {len(tickets)} tickets ({len(played)} jugados + {len(pend)} pendientes); "
              f"sobreuso con p<5%: {overuse(tickets, inc, pool)}")
        if gkey == "eurojackpot":
            e_played = [parse_nums(r["my_euros"]) for r in rows if r["game"] == gkey]
            e_pend = [t["euros"] for t in pending if t["game"] == gkey]
            print(f"    eurozahlen sobreusadas (p<5%): {overuse(e_played + e_pend, euro_inc, range(1, 13))}")
        print(f"    (de ~{len(list(pool))} números, ~{len(list(pool)) * 0.05:.0f} falsos positivos esperados por azar; "
              "preocupa si se repiten entre auditorías)")

    print("\n== 3. Filtros vs sorteos reales (draw_history.csv) ==")
    with open(HISTORY_F, encoding="utf-8") as f:
        hist = list(csv.DictReader(f))
    n_rej = 0
    filter_counts = {}
    for h in hist:
        gkey = h["game"]
        filt = cfg[gkey]["filters"]
        v = violations(parse_nums(h["draw_numbers"]), filt)
        if v:
            n_rej += 1
            for x in v:
                filter_counts[x] = filter_counts.get(x, 0) + 1
    print(f"  {n_rej}/{len(hist)} sorteos reales habrían sido rechazados; culpables: "
          + ", ".join(f"{k_}×{v}" for k_, v in sorted(filter_counts.items(), key=lambda x: -x[1])))
    for gkey, pool_top, k in (("eurojackpot", 50, 5), ("lotto6aus49", 49, 6)):
        acc = sum(1 for _ in range(50000)
                  if not violations(rng.sample(range(1, pool_top + 1), k), cfg[gkey]["filters"]))
        print(f"  espacio aceptado {gkey}: {acc / 500:.0f}% — recordatorio: los filtros son una apuesta de EV "
              "(evitar co-ganadores), no cambian la probabilidad de acertar")

    print("\n== 4. Premios: importe real vs media de clase (señal del modelo anti-popular) ==")
    won = [r for r in rows if float(r["prize_eur"]) > 0]
    if not won:
        print("  sin premios aún")
    for r in won:
        if r["game"] == "eurojackpot":
            _, _, res = check_ej(parse_nums(r["my_numbers"]), parse_nums(r["my_euros"]),
                                 parse_nums(r["draw_numbers"]), parse_nums(r["draw_euros"]))
            teo = sum(x[1] for x in res)
        else:
            hit = LOTTO_PRIZE.get(len(set(parse_nums(r["my_numbers"])) & set(parse_nums(r["draw_numbers"]))))
            teo = hit[1] if hit else 0
        real = float(r["prize_eur"])
        print(f"  {r['date']} {r['best_class']}: real {real:.2f}€ vs media ~{teo}€ "
              f"({'+' if real >= teo else ''}{(real / teo - 1) * 100:.0f}%)" if teo else
          f"  {r['date']} {r['best_class']}: real {real:.2f}€ (clase con Superzahl, sin media modelada)")
    print("  (si el modelo anti-popular funciona, con el tiempo la media de esta columna debe ser >0%)")

    print("\n== 5. Retorno vs baseline corregida ==")
    for gkey in ("eurojackpot", "lotto6aus49"):
        g = [r for r in rows if r["game"] == gkey]
        if not g:
            continue
        cost = sum(float(r["cost_eur"]) for r in g)
        prize = sum(float(r["prize_eur"]) for r in g)
        print(f"  {gkey}: retorno {prize / cost * 100:.1f}% vs esperado {expected_rate(gkey) * 100:.1f}% "
              f"(P(premio)/sorteo: {p_prize_per_draw(gkey) * 100:.1f}%) — con <50 sorteos, desviaciones ±2× son ruido")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("genera", help="generar combinación y guardarla en pendientes")
    g.add_argument("juego", choices=["ej", "lotto"])
    g.add_argument("--fecha", required=True, help="fecha del sorteo (ISO o D.M.YY)")
    g.add_argument("--seed", type=int, help="semilla RNG (reproducibilidad)")
    g.set_defaults(fn=cmd_genera)
    r = sub.add_parser("resultado", help="comprobar sorteo, mover pendiente a tracking")
    r.add_argument("juego", choices=["ej", "lotto"])
    r.add_argument("--numeros", required=True, help='números del sorteo "N-N-N-N-N(-N)"')
    r.add_argument("--euros", help='eurozahlen del sorteo "E-E" (solo EJ)')
    r.add_argument("--fecha", help="fecha del sorteo si hay varios pendientes")
    r.add_argument("--premio", help="importe REAL cobrado (obligatorio si hay premio)")
    r.add_argument("--clase", help="forzar clase (p. ej. Kl.9 por Superzahl)")
    r.set_defaults(fn=cmd_resultado)
    s = sub.add_parser("resumen", help="estadísticas acumuladas de ambos juegos")
    s.set_defaults(fn=cmd_resumen)
    a = sub.add_parser("audita", help="auditoría de milestone (sesgos, filtros, retorno)")
    a.add_argument("--tickets", type=int, default=20000, help="tamaño del baseline MC")
    a.set_defaults(fn=cmd_audita)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
