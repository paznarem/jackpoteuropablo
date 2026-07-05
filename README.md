# Lotería Semanal — EuroJackpot + Lotto 6aus49
<!-- Documento operativo para Claude Code. Leer antes de cualquier acción. -->

## Contexto

Pablo juega en Sachsen Lotto (online) con cadencia **variable** (1 o 2 sorteos por semana de cada juego, él decide cada semana):

1. **EuroJackpot**: martes y/o viernes, System 5Z+3E (3 combinaciones, 6,60€/sorteo online, incluye 0,60€ de Bearbeitungsgebühr). Combinación diferente cada sorteo.
2. **Lotto 6aus49**: miércoles y/o sábado, Normalschein 1 tipp (6 números, 1,80€/sorteo = 1,20€ + 0,60€ gebühr).

**Gasto según cadencia: ~8,40–16,80€/semana (~440–875€/año).** Al ritmo reciente (2+2 por semana): ~874€/año.

Modelo para ambos juegos: **filtros estructurales + penalización por popularidad sobre base uniforme** (conscious selection). No hay predicción posible: el objetivo es maximizar el valor esperado evitando combinaciones que compartirían premio con mucha gente, no acertar más.

## Regla de oro

**Las combinaciones se generan SIEMPRE con `loteria.py`, nunca "a mano".** Auditoría del 2026-07-04: los tickets generados manualmente por el LLM estaban sesgados (el 7 salió 5× frente a 1,4 esperado, p=0,01 — siendo el número MÁS penalizado del modelo; el 32, 7× frente a 2,9). Un LLM es un mal generador aleatorio; el script usa RNG real y registra la semilla de cada ticket.

## Comandos

Pablo dice → Claude Code ejecuta:

- **"genera [martes|viernes]"** → calcular la fecha del próximo martes/viernes y `python3 loteria.py genera ej --fecha YYYY-MM-DD`
- **"genera lotto [miércoles|sábado]"** → `python3 loteria.py genera lotto --fecha YYYY-MM-DD`
- **"genera todo"** → ambos juegos para las fechas que indique
- **"resultado EJ: N N N N N + E E"** → `python3 loteria.py resultado ej --numeros "N-N-N-N-N" --euros "E-E"`. Si hay varios EJ pendientes, añadir `--fecha` (acepta `25.5.26`). Si el script detecta premio, pide el importe REAL cobrado: preguntárselo a Pablo y repetir con `--premio X,XX` (para clases con Superzahl del lotto, añadir `--clase`)
- **"resultado lotto: N N N N N N"** → `python3 loteria.py resultado lotto --numeros "N-N-N-N-N-N"`. La Superzahl no se modela (no la controla Pablo), pero si le dio premio se registra con `--premio` y `--clase`
- **"resumen"** → `python3 loteria.py resumen`
- **"recalibra"** → actualizar frequencies.json (draw_history.csv propio + archivo oficial de resultados) y `last_updated`. Solo afecta a la generación si `weighting='frequency'`
- El script avisa automáticamente al registrar un resultado si se alcanza un **milestone (25/50/75/100 por juego)** → ejecutar `python3 loteria.py audita` y comentar los hallazgos sin que Pablo lo pida

## Estructura de archivos

```
├── README.md              ← este archivo
├── loteria.py             ← generación, comprobación, resumen y auditoría
├── config.json            ← parámetros del sistema (fuente de verdad)
├── frequencies.json       ← conteos históricos (referencia; la generación es base uniforme)
├── pending_tickets.json   ← combinaciones pendientes de resultado (con semilla RNG)
├── tracking.csv           ← historial completo (ambos juegos, columna "game")
└── draw_history.csv       ← números sorteados reales (se alimenta con cada "resultado")
```

## Modelo de generación

1. **Base uniforme** por número. (Hasta v1.3 se ponderaba por frecuencia histórica; se retiró porque no aporta señal —los sorteos son uniformes— y porque penalizaba sin motivo a las eurozahlen 11/12, que solo existen desde 2022-03 y tenían conteos ~45% menores por pura antigüedad.)
2. **× penalización por popularidad** (Cook & Clotfelter 1993, Baker & McHale 2011, Roger & Broihanne 2007): no cambia la probabilidad de acertar (es fija), maximiza el valor esperado evitando repartir premio.
   - `main_1_to_31` ×0,85: sesgo de fechas (cumpleaños); >50% de jugadores usan calendario
   - `main_7_specific` ×0,70: número sobrejugado globalmente
   - `main_13_specific` ×1,10: infrajugado por superstición
   - `main_32_to_50` ×1,15: infrajugados por no caber en fechas
   - `euro_7_specific` ×0,80: mismo sesgo en eurozahlen
3. **Filtros estructurales** (rechazo y remuestreo, máx. 500 intentos; si se agotan el script ABORTA con error — filtros incompatibles, como pasó con `sum_min=100` el 2026-05-26 — nunca degrada en silencio):

| Filtro | EJ (5 de 50) | Lotto (6 de 49) | Racional |
|---|---|---|---|
| decenas cubiertas | 3–4 | ≥4 | evitar patrones visuales jugados |
| pares | 1–4 | 2–4 | evitar todo-par/todo-impar (populares) |
| suma | 80–200 | 120–200 | cortar colas extremas “bonitas” |
| pares consecutivos | ≤1 | ≤1 | las secuencias se juegan mucho |
| números en 1–31 | ≤3 | ≤3 | anti-boleto-de-cumpleaños |

Notas de calibración:
- `sum_max` EJ subió de 179→200 (2026-07-04): el corte en 179 rechazaba combinaciones de números altos que son justo las MENOS populares (iba contra el propio objetivo del modelo). Ojo: `decades_min=3` sigue rechazando clusters altos tipo {35,41,44,47,50}; se acepta como compromiso, revisar en milestone 50.
- `sum_min` lotto subió de 100→120 (2026-05-26): 100 era inalcanzable combinado con birthday≤3 + decades≥4. Revisar en milestone 25/50 si discrimina (la auditoría lo mide).
- Los filtros aceptan solo una parte del espacio de sorteos (~la mitad en EJ, ~1 de cada 5 en lotto; `audita` da las cifras exactas). Eso significa que **la mayoría de sorteos reales caen fuera de los filtros y es NORMAL**: no reducen la probabilidad de acertar, son una apuesta de EV sobre con cuánta gente compartirías premio.

## Tabla de premios EuroJackpot (probabilidades verificadas)

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

## Tabla de premios Lotto 6aus49

| Kl | Aciertos | Premio medio |
|----|----------|-------------|
| 1 | 6 + SZ | Jackpot (~10M€+) |
| 2 | 6 | ~1.000.000€ |
| 3 | 5 + SZ | ~10.000€ |
| 4 | 5 | ~3.500€ |
| 5 | 4 + SZ | ~200€ |
| 6 | 4 | ~45€ |
| 7 | 3 + SZ | ~20€ |
| 8 | 3 | ~10€ |
| 9 | 2 + SZ | ~6€ |

La Superzahl es la última cifra de la Losnummer y no se controla → el sistema solo cuenta aciertos de los 6 principales; el premio real (que depende de la SZ del boleto) se registra con `--premio`/`--clase`.

## Expectativas anuales (corregidas 2026-07-04)

Las cifras de v1.0–v1.2 estaban infladas ~2× (EJ) y ~2× (lotto) por un error de cálculo. Valores exactos por combinatoria, solo clases "realistas" (las 1–4 de EJ y 6 aciertos de lotto dominan el EV teórico pero prácticamente nunca caen):

### EuroJackpot a 104 sorteos/año (System 5Z+3E, 686,40€)
- Kl.12 (2+1): ~6,3 premios → ~51€
- Kl.11 (1+2): ~1,7 premios → ~17€
- Kl.10 (3+0): ~1,0 premios → ~16€
- Kl.8+9: ~0,8 premios → ~14€
- Kl.5–7: <0,1 premios → ~6€ (aportan EV pero casi nunca caen)
- **Total: ~103€ → recuperación ~15%**

### Lotto 6aus49 (por sorteo 1,80€)
- 3 aciertos: ~0,018/sorteo (~0,9 premios por 52 sorteos) → ~10€
- resto (2+SZ, 4, 5 aciertos): ~11€ en EV
- **Total: ~21€ por 52 sorteos → recuperación ~23%** (por 104: ~43€)

### Combinado (cadencia 2+2): ~146€ sobre ~874€ → **recuperación ~17%**

Esto es la **vara de medir de los milestones**, no una promesa: la pérdida esperada es ~83% de lo jugado (es lotería). Estado real a 2026-07-04: 90,60€ jugados, 12,40€ cobrados (13,7%) — dentro de lo normal.

Matiz importante: como las clases son pari-mutuel, la ventaja del modelo anti-popular (si existe) NO aparece como más premios, sino como **importes por premio superiores a la media de la clase**. `audita` rastrea exactamente eso (primer dato: Kl.11 cobrado a 12,40€ vs ~10€ de media, +24%).

## Costes y Bearbeitungsgebühr (verificado 2026-07-04 en sachsenlotto.de)

- 1 sorteo por Spielauftrag: 0,60€ de tasa. **2 o más sorteos en el mismo Spielauftrag: 1,00€ fija en total.** Dauerspiel: 0,50€/mes por juego.
- Precios reales del System 5Z+3E EJ (confirmados por Pablo 2026-07-05): individual 6,60€; 1 semana (2 sorteos) 13€; 2 semanas 25€; 3 semanas 37€; 4 semanas 49€; **5 semanas (10 sorteos) 61€ → 6,10€/sorteo**. Jugando 104 sorteos/año: 686€ (individual) vs ~634€ (Scheine de 5 semanas) → **ahorro ~52€/año solo en EJ**; el Dauerspiel (0,50€/mes) lo dejaría en ~630€.
- Comprando sorteo a sorteo al ritmo 2+2/semana se pagan ~125€/año solo en tasas — comparable a TODO el retorno esperado (~146€).
- Un Spielauftrag mensual por juego (misma combinación toda la Laufzeit) baja las tasas a ~24€/año (Dauerspiel: ~12€): **ahorro ~100€/año**.
- Estadísticamente, repetir la misma combinación en varios sorteos es EXACTAMENTE igual de bueno que cambiarla (sorteos independientes, misma probabilidad y mismo EV cada vez; y la combinación del sistema sigue siendo anti-popular todo el mes). La única pega es psicológica: si una semana no juegas y "tus" números salen.
- **Decisión pendiente de Pablo**: mantener combinación nueva por sorteo (ritual, +100€/año en tasas) o pasar a Schein multisemana/Dauerspiel.

## Calendario de revisión

El script avisa del milestone al registrar resultados; entonces Claude ejecuta `python3 loteria.py audita`, que cubre automáticamente:
integridad de datos, sesgo de uso de números del generador (vs baseline MC), perfil de rechazo de cada filtro, filtros vs sorteos reales, importe real vs media de clase, y retorno vs baseline corregida.

### Cada 25 sorteos (por juego)
1. `audita` + comentar hallazgos a Pablo
2. Retorno real vs ~15% (EJ) / ~23% (lotto). Con n=25, desviaciones hasta ±2× son ruido normal — no tocar parámetros por eso
3. Revisar si `sum_min` lotto discrimina lo suficiente (pendiente desde 2026-05-26)
4. Popularity_penalties: ¿los premios cobrados vienen con reparto excepcional o por encima de la media de clase?

### Cada 50 sorteos
1. Recalibrar frequencies.json (draw_history propio + archivo oficial) — informativo mientras `weighting='uniform'`
2. Buscar datos/estudios recientes de conscious selection en Alemania
3. Revisar la tensión filtros↔EV (decades_min vs clusters altos; ver Notas de calibración)
4. Documentar cambios aquí con fecha y razón

### Cada 104 sorteos (~1 año)
1. Informe completo: gasto, retorno, distribución por clase vs expectativa
2. Revisar precios/reglas (¿sigue la gebühr en 0,60/1,00? ¿cambió el bombo?)
3. Auditoría del modelo completo con la literatura nueva que haya

### Alertas automáticas (las comprueba el script al registrar)
- **EJ: 58 sorteos seguidos sin premio** (p<5% bajo azar; el umbral 15 anterior saltaba con p=46%: ruido)
- **Lotto: 155 sorteos** (P(premio)/sorteo es solo 1,9%; rachas larguísimas son normales)
- Cambio de reglas de cualquiera de los juegos → adaptar sistema

## Decisiones tomadas

- **EuroJackpot**: System 5Z+3E (3 combos, 6,60€/sorteo online), combinación diferente cada sorteo — *en revisión: Schein multisemana ahorraría ~100€/año, ver Costes*
- **Lotto 6aus49**: Normalschein 1 tipp (1,80€/sorteo), 1–2×/semana a elección
- **Cadencia flexible**: no hay draws_per_week fijo; el gasto anual varía con lo que Pablo decida jugar
- **Base uniforme + popularidad** (v1.3): la frecuencia histórica no predice y metía sesgos espurios
- **Cambiar números entre sorteos NO mejora nada estadísticamente** (independencia de sorteos); se hace por preferencia, no por ventaja
- Los paquetes de Sachsen Lotto NO convienen (Zufallstipp obligatorio, mezclan juegos)

## Historial de cambios

- **2026-05-25 v1.0**: Sistema inicial EuroJackpot con filtros estructurales y ponderación por frecuencia
- **2026-05-25 v1.1**: Añadidas popularity_penalties (Cook & Clotfelter 1993, Baker & McHale 2011)
- **2026-05-25 v1.2**: Añadido Lotto 6aus49. Frecuencias de Sachsen Lotto. Tracking unificado
- **2026-05-26 v1.2.1**: Smoke test de filtros. `sum_min` lotto 100→120 (inalcanzable por interacción birthday≤3 + decades≥4 + consec≤1). Pendiente revisar discriminación en milestone 25/50
- **2026-07-04 v1.3**: Revisión completa del sistema.
  - **loteria.py**: el pseudocódigo del README pasa a script ejecutable (RNG real con semilla registrada, validación de fechas, sin fallback silencioso). Motivo: auditoría detectó sesgo severo en la generación manual por LLM (nº7 5× vs 1,4 esperado p=0,01; nº32 7× vs 2,9 p=0,02) que además invertía la penalización anti-popular
  - **Base uniforme** en vez de frecuencia histórica (`config.weighting`): la frecuencia era ruido de muestreo y las eurozahlen 11/12 quedaban infrarrepresentadas ~45% por existir solo desde 2022-03
  - **Expectativas corregidas**: estaban infladas ~2× (EJ ~103€/15%, no 198€/29%; lotto ~23%, no 41%). El retorno real acumulado (13,7%) es normal con la vara correcta
  - **Alerta de racha**: 15→58 (EJ) / 155 (lotto), umbral p<5% (15 saltaba con p=46%: alarmas falsas constantes)
  - **`sum_max` EJ 179→200**: el corte anterior rechazaba combinaciones altas anti-populares (contradicción con el objetivo EV)
  - **draw_history.csv**: histórico propio de números sorteados (se alimenta con cada resultado; base para recalibrar sin transcripciones manuales)
  - **Tasas verificadas** en sachsenlotto.de: 0,60€/1 sorteo, 1,00€ fija por 2+ sorteos, Dauerspiel 0,50€/mes → Schein mensual ahorraría ~100€/año. Decisión pendiente
  - Documentación sincronizada con config.json (coste 6,60€, cadencia variable, lotto 6.527 sorteos no "~6800")
