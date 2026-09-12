# Detailed local results

The current campaign is `bench/results/wsl-2026-09-12/`. Its raw source hashes, inputs, decisions and timing repetitions are committed alongside the plotting script. Earlier JSON files outside that directory are historical records.

## Parser failures

The fixed corpus contains 116 clearances: 68 base examples and 48 extended examples. The full parser command contract includes vertical speed. Fourteen extended examples fail exact matching. This table is generated from `parser_cases.json`.

| Case ID | Category | Input | Expected commands | Observed commands |
|---:|---|---|---|---|
| 69 | paraphrase | BAW57 make your heading zero nine zero | `HDG BAW57 90` | `HDG BAW57MAKEYOUR 90` |
| 70 | paraphrase | EZY21 pick up speed to three hundred knots | `SPD EZY21 300` | `SPD EZY21PICKUP 3` |
| 71 | paraphrase | DLH88 when ready descend flight level one two zero | `ALT DLH88 12000` | `ALT DLH88WHENREADY 12000` |
| 72 | paraphrase | ryanair niner route direct to delta | `ADDWPT RYR9 DELTA` | `ADDWPT RYR9ROUTE DELTA` |
| 73 | paraphrase | speedbird five seven climb now to flight level three five zero | `ALT BAW57 35000` | (empty) |
| 75 | paraphrase | AFR1234 slow down to two three zero knots | `SPD AFR1234 230` | (empty) |
| 76 | paraphrase | BAW57 stop climb at flight level two eight zero | `ALT BAW57 28000` | (empty) |
| 79 | bruit_stt | uh air france one two three four er climb flight level three two zero please | `ALT AFR1234 32000` | `ALT UHAIRFRANCE1234ER 32000` |
| 80 | bruit_stt | speedbird five seven speedbird five seven turn left heading two one zero | `HDG BAW57 210` | `HDG BAW57SPEEDBIRD57 210` |
| 81 | bruit_stt | easyjet two one good evening climb flight level one eight zero | `ALT EZY21 18000` | `ALT EZY21GOODEVENING 18000` |
| 82 | bruit_stt | AFR1234 roger climb flight level two four zero | `ALT AFR1234 24000` | `ALT AFR1234ROGER 24000` |
| 85 | francais_ext | DLH88 directe BALMO | `ADDWPT DLH88 BALMO` | (empty) |
| 89 | chiffres_ext | BAW57 reduce speed two hundred fifty knots | `SPD BAW57 250` | `SPD BAW57 2` |
| 115 | negatif_ext | AFR1234 monter niveau cinq cents | (empty) | `ALT AFR1234 500` |

Of the 24 negative cases, 1 emits a command. Case 115 interprets a French level phrase as an allowed altitude instead of rejecting the expected out-of-range instruction. This is a semantic interpretation failure; a range check on the emitted number alone does not catch it.

The corpus reuses development inputs. Accuracy on these examples is not an estimate of accuracy on unseen controller speech. The historical LLM corpus changes the command contract by omitting vertical-speed commands, so its aggregate is not an identical-task comparison.

## Timing summaries

All timings retain five repetitions and discard one warmup per configuration. The parser statistic is the median of batch-average costs: each batch duration divided by the number of clearances. Quartiles use linear interpolation. The IQR is a spread statistic, not a confidence interval.

| Parser corpus prefix | Median (ms/clearance) | Q1 | Q3 | IQR |
|---:|---:|---:|---:|---:|
| 16 | 0.03284263 | 0.03265356 | 0.03921806 | 0.00656450 |
| 68 | 0.03385825 | 0.03291857 | 0.03572021 | 0.00280163 |
| 116 | 0.03309297 | 0.03202517 | 0.03448499 | 0.00245982 |

| BlueSky aircraft | Median simulation/wall-time ratio | Q1 | Q3 | IQR |
|---:|---:|---:|---:|---:|
| 5 | 156.445993 | 151.004564 | 159.821215 | 8.816651 |
| 25 | 146.392242 | 145.719337 | 147.918073 | 2.198736 |
| 100 | 125.033312 | 118.574732 | 129.838539 | 11.263807 |

BlueSky measures only `bluesky_runtime.advance(10)` after initialization, reset, creation and aircraft-count verification. It excludes traffic setup, command parsing, the application conflict-analysis loop, browser rendering and all voice services. The actual simulated advance is used in the ratio. The cache and settings are isolated by the benchmark; `bench/bluesky.cfg` records the configuration.

## Geometry coverage

The campaign checks 1,500 random same-altitude pairs against a direct time grid. It contains only seven positive predictions and five initial losses of separation. There are no disagreements in these cases, but this small positive subset gives weak coverage of conflict detection. It does not validate vertical filtering, turns or climbs. Threshold-adjacent grid cases are flagged explicitly; none were flagged in this sample.

The maximum difference between reported distance and grid distance is 0.0474607365 NM. Reported distance is rounded, and the reference grid itself is discrete. The separate set of 200 constructed examples meets its recorded criteria; its maximum reference closest distance is 0.0799997513 NM. These are checks of the stated constructions and assumptions, not an operational certification.

## Functional validation

- [Python test output](../bench/results/wsl-2026-09-12/pytest.txt) and [JUnit details](../bench/results/wsl-2026-09-12/pytest.xml).
- [Ruff output](../bench/results/wsl-2026-09-12/ruff.txt).
- [Frontend dependency installation and production build](../bench/results/wsl-2026-09-12/frontend-build.txt).
- [Application startup](../bench/results/wsl-2026-09-12/app-startup.txt) and [HTTP smoke checks](../bench/results/wsl-2026-09-12/app-smoke.json).
- [Measurement execution log](../bench/results/wsl-2026-09-12/execution.txt).
- [Full environment](../bench/results/wsl-2026-09-12/environment.json).

Absolute local paths in text logs are replaced with placeholders. Test/build durations are not portfolio performance comparisons. Hosted Actions status remains unobserved until the branch is published.

The frontend build reports four dependency advisories and a bundle-size warning. BlueSky reports missing RTree helpers and BADA data; the measured OpenAP path completes. Dependency fixes, model-service deployment and operational validation remain outside this documentation change.

## Not measured in this campaign

| Component | Status and reason |
|---|---|
| Speech-recognition WER and latency | non mesuré: no configured speech provider and corpus replay |
| LLM command accuracy | non mesuré: no configured language-model service |
| TTS intelligibility and speed | non mesuré: no configured synthesis service |
| Complete voice-loop success and latency | non mesuré: the three model services were not configured |
| ROMEO deployment parity | non mesuré: this campaign ran only on the local WSL machine |
| Human usefulness | non mesuré: no new user study |

The earlier campaigns remain under `bench/results/`, `validation/` and the academic reports. Their reported values are not repeated as newly verified README results.

## Replaying the HTTP startup check

Use the pinned application environment from the README and build the frontend first. In one terminal, launch the application with model services explicitly directed to an unavailable local port:

```bash
ATC_APP_NOBROWSER=1 ATC_APP_PORT=18080 \
ATC_STT_URL=http://127.0.0.1:1 ATC_LLM_URL=http://127.0.0.1:1 \
ATC_TTS_URL=http://127.0.0.1:1 python src/atc_app.py
```

In another terminal, check the UI and traffic state, then stop the application with Ctrl+C in its terminal:

```bash
curl --fail http://127.0.0.1:18080/
curl --fail http://127.0.0.1:18080/api/state
```

The recorded checks require an HTML root element and a JSON state object. They do not exercise the voice providers or interactive browser controls.
