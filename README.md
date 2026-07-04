# Lotería Semanal — EuroJackpot + Lotto 6aus49
<!-- Documento operativo para Claude Code. Leer antes de cualquier acción. -->

## Contexto

Pablo juega semanalmente a dos loterías en Sachsen Lotto (online):

1. **EuroJackpot**: 2x/semana (martes + viernes), System 5Z+3E (3 combinaciones, 6,60€/sorteo online —incluye Bearbeitungsgebühr—). Combinación diferente cada sorteo. ~13,20€/semana.
2. **Lotto 6aus49**: 1x/semana (miércoles O sábado, Pablo elige el día), Normalschein 1 tipp (6 números, 1,80€/sorteo). ~1,80€/semana.

**Gasto total: ~15€/semana (~780€/año).**

Ambos juegos usan el mismo modelo híbrido: filtros estructurales + ponderación por frecuencia histórica + penalización por popularidad (conscious selection).

## Comandos

Pablo puede decir:
- **"genera [martes|viernes]"** → generar combinación EuroJackpot (5+3E), guardarla en pending_tickets.json
- **"genera lotto [miércoles|sábado]"** → generar combinación Lotto 6aus49 (6 números), guardarla en pending_tickets.json
- **"genera todo"** → generar ambos (EuroJackpot para el próximo sorteo + Lotto para el día que indique)
- **"resultado EJ: N N N N N + E E"** → comprobar el ticket EuroJackpot pendiente y mover a tracking.csv. Si solo hay un EJ pendiente se asume ese; si hay varios, Pablo precisa el sorteo (ej. **"resultado eurojackpot del 25.5.26: N N N N N + E E"**, formato fecha `D.M.YY`)
- **"resultado lotto: N N N N N N"** → comprobar el ticket Lotto pendiente y mover a tracking.csv. Mismo criterio: si hay varios, Pablo precisa el sorteo (ej. **"resultado lotto del 28.5.26: N N N N N N"**). Nota: la Superzahl no se comprueba (no la controla Pablo)
- **"resumen"** → mostrar stats acumuladas de AMBOS juegos desde tracking.csv
- **"recalibra"** → buscar resultados recientes online, actualizar frequencies.json
- En todos los casos: **SIEMPRE** después de escribir en tracking.csv, contar filas POR JUEGO y comprobar si se ha alcanzado un milestone (25, 50, 75, 100). Si sí → ejecutar la revisión correspondiente automáticamente sin que Pablo lo pida

## Estructura de archivos

```
loteria-semanal/
├── README.md                  ← este archivo
├── frequencies.json           ← pesos de generación para AMBOS juegos
├── pending_tickets.json       ← combinaciones pendientes de resultado
├── tracking.csv               ← historial completo (ambos juegos, columna "game")
└── config.json                ← parámetros del sistema
```

## config.json (crear al inicio)

```json
{
  "system": "5+3E",
  "combos_per_ticket": 3,
  "cost_per_draw": 6.00,
  "cost_weekly": 13.20,
  "draws_per_week": 2,
  "filters": {
    "decades_min": 3,
    "decades_max": 4,
    "even_min": 1,
    "even_max": 4,
    "sum_min": 80,
    "sum_max": 179,
    "max_consecutive_pairs": 1,
    "max_birthday_range_numbers": 3
  },
  "popularity_penalties": {
    "main_1_to_31": 0.85,
    "main_7_specific": 0.70,
    "main_13_specific": 1.10,
    "main_32_to_50": 1.15,
    "euro_7_specific": 0.80
  },
  "review_milestones": [25, 50, 75, 100],
  "alert_no_prize_streak": 15
}
```

### Explicación de popularity_penalties

Basado en literatura académica sobre "conscious selection" (Cook & Clotfelter 1993, Baker & McHale 2011, Roger & Broihanne 2007). El objetivo NO es aumentar probabilidad de acertar (es fija), sino **maximizar el valor esperado** evitando combinaciones populares que dividirían el premio entre muchos ganadores.

- `main_1_to_31` (×0.85): sesgo de fechas (cumpleaños, aniversarios). 50%+ de jugadores juegan al menos parcialmente con números de calendario.
- `main_7_specific` (×0.70): número globalmente sobrejugado durante décadas en múltiples culturas.
- `main_13_specific` (×1.10): infrajugado por superstición occidental.
- `main_32_to_50` (×1.15): infrajugados por no caber en fechas.
- `euro_7_specific` (×0.80): aplica el mismo sesgo al campo de Eurozahlen.
- `max_birthday_range_numbers` (3): rechaza combinaciones con 4+ números en 1-31 (típico boleto de cumpleaños).

**Estos factores son conservadores y deben revisarse en cada milestone (25/50/75/100 sorteos).**

## frequencies.json (crear al inicio)

Última actualización: 2026-05-25. EuroJackpot basado en 655 sorteos (2018-2026). Lotto 6aus49 basado en datos históricos desde 1955 (fuente: Sachsen Lotto).

```json
{
  "last_updated": "2026-05-25",
  "eurojackpot": {
    "total_draws": 655,
    "main_numbers": {
      "1":66,"2":69,"3":63,"4":61,"5":57,"6":62,"7":64,"8":76,"9":66,"10":53,
      "11":75,"12":65,"13":67,"14":62,"15":71,"16":70,"17":78,"18":69,"19":59,"20":76,
      "21":81,"22":62,"23":76,"24":64,"25":47,"26":62,"27":60,"28":52,"29":69,"30":74,
      "31":67,"32":63,"33":57,"34":80,"35":76,"36":60,"37":69,"38":66,"39":68,"40":54,
      "41":71,"42":60,"43":66,"44":60,"45":70,"46":66,"47":62,"48":55,"49":71,"50":58
    },
    "euro_numbers": {
      "1":108,"2":105,"3":122,"4":117,"5":125,"6":112,
      "7":123,"8":112,"9":123,"10":123,"11":62,"12":78
    }
  },
  "lotto6aus49": {
    "total_draws": "~6800 (desde 1955)",
    "numbers": {
      "1":814,"2":803,"3":833,"4":804,"5":796,"6":858,"7":811,"8":771,"9":817,"10":792,
      "11":822,"12":772,"13":739,"14":773,"15":774,"16":815,"17":789,"18":797,"19":811,"20":766,
      "21":749,"22":815,"23":781,"24":789,"25":843,"26":848,"27":820,"28":761,"29":792,"30":790,
      "31":836,"32":798,"33":826,"34":778,"35":782,"36":797,"37":801,"38":830,"39":785,"40":789,
      "41":819,"42":803,"43":847,"44":805,"45":724,"46":768,"47":800,"48":797,"49":832
    }
  }
}
```

## pending_tickets.json (ejemplo)

```json
[
  {
    "game": "eurojackpot",
    "draw_date": "2026-05-27",
    "draw_day": "martes",
    "numbers": [8, 17, 23, 34, 41],
    "euros": [3, 5, 9],
    "combos": [[3,5],[3,9],[5,9]],
    "generated_at": "2026-05-26T20:00:00"
  },
  {
    "game": "lotto6aus49",
    "draw_date": "2026-05-28",
    "draw_day": "miércoles",
    "numbers": [13, 32, 38, 41, 43, 49],
    "generated_at": "2026-05-26T20:00:00"
  }
]
```

## tracking.csv (formato)

```csv
date,game,day,my_numbers,my_euros,draw_numbers,draw_euros,hits_main,hits_euro,best_class,prize_eur,cost_eur
```

Ejemplos:
```csv
2026-05-27,eurojackpot,mar,8-17-23-34-41,3-5-9,12-23-34-41-48,3-9,3,2,Kl.7,60.00,6.00
2026-05-28,lotto6aus49,mie,13-32-38-41-43-49,,12-23-32-38-41-44,,4,,Kl.5,98.50,1.80
```

Notas:
- Columna `game`: "eurojackpot" o "lotto6aus49"
- Para lotto6aus49: `my_euros` y `draw_euros` van vacíos, `hits_euro` vacío
- `hits_main` y `hits_euro` (EJ): mejores aciertos entre las 3 combos del system
- `best_class`: mejor premio conseguido (Kl.1 a Kl.12/Kl.9, o "—" si nada)
- Si hay múltiples premios en las 3 combos del EJ, registrar TODOS sumados en prize_eur

## Algoritmo de generación

```python
import random

def get_popularity_factor(num, config, is_euro=False):
    """Multiplicador de popularidad para penalizar números sobrejugados"""
    p = config["popularity_penalties"]
    if is_euro:
        if num == 7:
            return p["euro_7_specific"]
        return 1.0
    # Main numbers
    if num == 7:
        return p["main_7_specific"]
    if num == 13:
        return p["main_13_specific"]
    if num <= 31:
        return p["main_1_to_31"]
    return p["main_32_to_50"]

def weighted_sample(population, frequencies, config, k, is_euro=False):
    """Muestreo sin reemplazo ponderado por frecuencia × popularidad"""
    pop = list(population)
    w = [frequencies[str(x)] * get_popularity_factor(x, config, is_euro) for x in pop]
    chosen = []
    for _ in range(k):
        total = sum(w)
        r = random.random() * total
        cumsum = 0
        for i in range(len(pop)):
            cumsum += w[i]
            if r <= cumsum:
                chosen.append(pop[i])
                pop.pop(i)
                w.pop(i)
                break
    return sorted(chosen)

def passes_filters(nums, config):
    filters = config["filters"]
    # Decenas: 3-4
    decades = len(set((n - 1) // 10 for n in nums))
    if decades < filters["decades_min"] or decades > filters["decades_max"]:
        return False
    # Par/impar: no todo igual
    even = sum(1 for n in nums if n % 2 == 0)
    if even < filters["even_min"] or even > filters["even_max"]:
        return False
    # Suma: 80-179
    s = sum(nums)
    if s < filters["sum_min"] or s > filters["sum_max"]:
        return False
    # Consecutivos: máx 1 par
    sn = sorted(nums)
    cp = sum(1 for i in range(4) if sn[i+1] - sn[i] == 1)
    if cp > filters["max_consecutive_pairs"]:
        return False
    # Anti-cumpleaños: rechazar 4+ números en 1-31
    birthday_range = sum(1 for n in nums if n <= 31)
    if birthday_range > filters["max_birthday_range_numbers"]:
        return False
    return True

def generate_ticket(frequencies, config):
    for _ in range(500):
        nums = weighted_sample(range(1, 51), frequencies["main_numbers"], config, 5)
        if passes_filters(nums, config):
            euros = weighted_sample(range(1, 13), frequencies["euro_numbers"], config, 3, is_euro=True)
            return nums, euros
    # Fallback sin filtros
    nums = weighted_sample(range(1, 51), frequencies["main_numbers"], config, 5)
    euros = weighted_sample(range(1, 13), frequencies["euro_numbers"], config, 3, is_euro=True)
    return nums, euros
```

## Comprobación de premios — EuroJackpot

```python
from itertools import combinations

EJ_PRIZE_TABLE = {
    (5,2): ("Kl.1", 30_000_000), (5,1): ("Kl.2", 800_000), (5,0): ("Kl.3", 150_000),
    (4,2): ("Kl.4", 4_000), (4,1): ("Kl.5", 230), (4,0): ("Kl.6", 100),
    (3,2): ("Kl.7", 60), (3,1): ("Kl.8", 20), (2,2): ("Kl.9", 17),
    (3,0): ("Kl.10", 16), (1,2): ("Kl.11", 10), (2,1): ("Kl.12", 8),
}

def check_eurojackpot(my_nums, my_euros_3, draw_nums, draw_euros):
    """Comprobar las 3 combinaciones del System 5+3E"""
    results = []
    for euro_pair in combinations(my_euros_3, 2):
        mn = len(set(my_nums) & set(draw_nums))
        me = len(set(euro_pair) & set(draw_euros))
        prize = EJ_PRIZE_TABLE.get((mn, me))
        if prize:
            results.append({"class": prize[0], "prize": prize[1], "euros_used": list(euro_pair)})
    return results
```

## Generación y comprobación — Lotto 6aus49

### Reglas
- 6 números del 1 al 49
- Superzahl (0-9): última cifra de la Losnummer, NO la elige el jugador → no la modelamos
- Normalschein: 1,20€/tipp + 0,60€ gebühr = 1,80€/sorteo
- Sorteos: miércoles y sábado (Pablo juega 1 por semana, a su elección)

### Filtros para 6aus49 (adaptados del EuroJackpot)
- **Decenas**: cubrir 4-5 decenas de las 5 posibles (1-10, 11-20, 21-30, 31-40, 41-49)
- **Par/impar**: 2-4 pares (no todo par ni todo impar, ni 1/5 ni 5/1)
- **Suma**: entre 120-200 (rango central para 6 números de 49). Nota: inicialmente fijada en 100-200, pero un smoke test (2026-05-26) demostró que sum<120 es inalcanzable bajo `birthday≤3` + `decades≥4` + `consec≤1` (los 3 altos mínimos suman 99 y los bajos no pueden compensar). Ajustado a 120 para que el límite refleje la realidad. Revisar en milestone 25/50: si `sum_min` apenas rechaza tickets, afinarlo más.
- **Consecutivos**: máximo 1 par consecutivo
- **Anti-cumpleaños**: máximo 3 números en rango 1-31
- **Popularity penalties**: mismos factores que EuroJackpot (×0.85 para 1-31, ×0.70 para 7, ×1.10 para 13, ×1.15 para 32-49)

### Algoritmo
```python
def passes_filters_6aus49(nums, config):
    filters = config["filters_6aus49"]
    decades = len(set((n - 1) // 10 for n in nums))
    if decades < 4: return False
    even = sum(1 for n in nums if n % 2 == 0)
    if even < 2 or even > 4: return False
    s = sum(nums)
    if s < 120 or s > 200: return False
    sn = sorted(nums)
    cp = sum(1 for i in range(5) if sn[i+1] - sn[i] == 1)
    if cp > 1: return False
    birthday = sum(1 for n in nums if n <= 31)
    if birthday > 3: return False
    return True

def generate_lotto_ticket(frequencies, config):
    for _ in range(500):
        nums = weighted_sample(range(1, 50), frequencies["lotto6aus49"]["numbers"], config, 6)
        if passes_filters_6aus49(nums, config):
            return nums
    return weighted_sample(range(1, 50), frequencies["lotto6aus49"]["numbers"], config, 6)
```

### Tabla de premios Lotto 6aus49 (sin Superzahl)

| Kl | Aciertos | Premio medio |
|----|----------|-------------|
| 1 | 6 + Superzahl | Jackpot (~10M€+) |
| 2 | 6 | ~1.000.000€ |
| 3 | 5 + Superzahl | ~10.000€ |
| 4 | 5 | ~3.500€ |
| 5 | 4 + Superzahl | ~200€ |
| 6 | 4 | ~45€ |
| 7 | 3 + Superzahl | ~20€ |
| 8 | 3 | ~10€ |
| 9 | 2 + Superzahl | ~6€ |

Nota: como Pablo no controla la Superzahl, para comprobar premios solo contamos aciertos de los 6 números principales. Si acierta X números, el premio depende de si además coincide la Superzahl (que se verifica contra el boleto real).

```python
LOTTO_PRIZE_TABLE = {
    6: ("Kl.2", 1_000_000),  # Sin Superzahl. Con Superzahl sería Kl.1 (Jackpot)
    5: ("Kl.4", 3_500),       # Sin SZ. Con SZ sería Kl.3
    4: ("Kl.6", 45),          # Sin SZ. Con SZ sería Kl.5
    3: ("Kl.8", 10),          # Sin SZ. Con SZ sería Kl.7
    2: ("—", 0),              # Sin SZ nada. Con SZ sería Kl.9 (6€)
}

def check_lotto(my_nums, draw_nums):
    mn = len(set(my_nums) & set(draw_nums))
    return LOTTO_PRIZE_TABLE.get(mn, ("—", 0))
```

## Tabla de premios (referencia rápida)

| Kl | Aciertos | 1 en | Premio medio |
|----|----------|------|-------------|
| 1 | 5+2 | 139.838.160 | Jackpot |
| 2 | 5+1 | 6.991.908 | ~800.000€ |
| 3 | 5+0 | 3.107.515 | ~150.000€ |
| 4 | 4+2 | 621.503 | ~4.000€ |
| 5 | 4+1 | 31.075 | ~230€ |
| 6 | 4+0 | 13.811 | ~100€ |
| 7 | 3+2 | 14.125 | ~60€ |
| 8 | 3+1 | 706 | ~20€ |
| 9 | 2+2 | 985 | ~17€ |
| 10 | 3+0 | 314 | ~16€ |
| 11 | 1+2 | 188 | ~10€ |
| 12 | 2+1 | 49 | ~8€ |

## Expectativas anuales

### EuroJackpot (104 sorteos, 3 combos/sorteo)
- Kl.12: ~13 premios → ~104€
- Kl.11: ~3,4 premios → ~34€
- Kl.10: ~2 premios → ~32€
- Kl.8-9: ~1,5 premios → ~28€
- **Total esperado: ~198€/año sobre ~686€ gasto (ROI ~29%)**

### Lotto 6aus49 (52 sorteos, 1 combo/sorteo)
- Kl.8 (3 aciertos): ~3 premios → ~30€
- Kl.6 (4 aciertos): ~0,2 premios → ~9€
- **Total esperado: ~39€/año sobre ~94€ gasto (ROI ~41%)**

### Combinado
- **Gasto total: ~780€/año**
- **Retorno esperado: ~237€/año (ROI ~30%)**

## Calendario de revisión

Claude Code debe comprobar automáticamente al escribir en tracking.csv:

### Cada 25 sorteos (~3 meses)
1. Calcular ROI real vs esperado (29%)
2. Contar premios por Klasse vs expectativa
3. Si desviación >30% en cualquier categoría → avisar a Pablo
4. **Revisar popularity_penalties**: comprobar si los valores actuales han generado tickets demasiado sesgados o no. Si en los 25 sorteos hubo premios bajos sin reparto excepcional, los factores funcionan. Si hubo premios compartidos masivamente, considerar endurecer factores.

### Cada 50 sorteos (~6 meses)
1. Buscar resultados recientes del EuroJackpot online
2. Recalcular frecuencias y actualizar frequencies.json
3. Informar si algún número cambió significativamente
4. **Revisión completa de popularity_penalties**: 
   - Buscar online estudios o datos recientes sobre conscious selection en EuroJackpot Alemania específicamente
   - Comparar el reparto de premios en los 50 últimos sorteos con la distribución teórica
   - Si el sistema actual está demasiado conservador o agresivo, ajustar los multiplicadores
   - Documentar los cambios en este README con fecha y razón

### Cada 104 sorteos (~1 año)
1. Informe completo: gasto, ganancia, ROI, distribución
2. Comparar con expectativa teórica
3. Revisar si precios han cambiado
4. **Auditoría completa del modelo**: ¿siguen siendo válidos todos los filtros y penalizaciones? ¿Hay nueva literatura académica sobre selección de números en loterías que aplicar?

### Alertas automáticas
- **15 sorteos seguidos sin premio** → revisar filtros Y popularity_penalties
- **Cambio de reglas EuroJackpot** → adaptar sistema

## Decisiones tomadas

- **EuroJackpot**: System 5+3E (3 combos, 6€/sorteo), combinación diferente cada sorteo
- **Lotto 6aus49**: Normalschein 1 tipp (1,80€/sorteo), 1x/semana día variable (mié o sáb)
- **Modelo híbrido** para ambos: filtros estructurales + frecuencia histórica + penalización por popularidad
- Penalización por popularidad basada en literatura académica de "conscious selection"
- No hay predicción: los filtros eliminan combinaciones improbables, no predicen ganadoras
- Los paquetes de Sachsen Lotto NO convienen (Zufallstipp obligatorio, mezclan juegos)

## Historial de cambios

- **2026-05-25 v1.0**: Sistema inicial EuroJackpot con filtros estructurales y ponderación por frecuencia
- **2026-05-25 v1.1**: Añadidas popularity_penalties (Cook & Clotfelter 1993, Baker & McHale 2011)
- **2026-05-25 v1.2**: Añadido Lotto 6aus49 como juego complementario. Mismo modelo híbrido. Frecuencias de Sachsen Lotto (datos desde 1955). Tracking unificado en un solo CSV.
- **2026-05-26 v1.2.1**: Smoke test de filtros. Ajustado `sum_min` de Lotto 6aus49 de 100 → 120 (el valor original era inalcanzable por interacción con birthday≤3 + decades≥4 + consec≤1). Pendiente revisar en milestone 25/50 si el filtro discrimina lo suficiente.
