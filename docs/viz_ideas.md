# Visualization brainstorm

Status legend: ✅ built · 🔜 planned next · 💡 idea

| # | Idea | What it shows | Status |
|---|---|---|---|
| 1 | Municipal choropleth, residual 2020–2024 | the core dataset at a glance | ✅ figure + interactive Pages map |
| 2 | Two-period provincial choropleth pair | suburbanization → post-COVID reversal | ✅ |
| 3 | Event-study forest plot | Pinatubo/Bohol/Haiyan×2/Marawi/Odette in one look | ✅ `figures/event_studies_forest.png` |
| 4 | Demographic center of gravity, 1960–2020 | frontier era vs Manila-ward drift in one path | ✅ built; cut from the site per feedback (kept in figures/) |
| 5 | NMS validation scatter | why no external benchmark works | ✅ |
| 6 | Bump chart: 20 largest cities by rank, 1960–2020 | rise of Davao/Cebu suburbs, decline of older centers | 🔜 straight from the census panel |
| 7 | Small multiples: growth-rate curves for 6 named corridors (Cavite ring, Cebu metro, Davao, Iloilo, Tacloban, Marawi) | corridor stories the atlas tells in prose | 🔜 |
| 8 | "Municipal ages": year each LGU hit half its 2020 population | a settlement-age map of the country | 💡 fun, one map |
| 9 | Animated time-lapse GIF, growth vs national 1960→2024 | eight windows of redistribution in ten seconds | ✅ `figures/growth_timelapse.gif` |
| 9b | Interactive slider map, 8 municipal census windows (site) | scrub 1960→2024 with a per-window note | ✅ site `#history` (redesigned 2026-07: flow particles removed — decorative, implied unrecorded routes; slider is now municipal-only for consistent units) |
| 9c | Province small multiples: 1990–95, 1995–2000, 2000–07, 2007–10 | the two decades split by the paper-only 1995/2007 censuses | ✅ `figures/growth_windows_prov.png` |
| 9d | Window thumbnails as the history-map control | all 8 windows visible at once; click to explore (small multiples beat sliders for comparison) | ✅ site `#history`, built by `make_site_data.py` |
| 13 | Region diverging bars, both windows | regional ranking + the post-2020 flips, NCR labeled | ✅ `figures/region_bars.png` |
| 14 | NCR dumbbell, 2015–20 → 2020–24 per city | the capital's flip from losing to gaining, city by city | ✅ `figures/ncr_dumbbell.png` |
| 15 | Sideways hero map with metro cutaways | the whole archipelago wide, not tall; Manila/Cebu/Davao readable | ✅ `figures/hero_municipal_sideways.png` (README hero + og:image) |
| 16 | Capital-shares time series 1960–2020 | NCR peaked ~1990; its ring passed it 2015–2020 | ✅ `figures/capital_shares.png` |
| 10 | Birth-registration visibility strip (province × year) | makes the BARMM caveat visible rather than asserted | ✅ `figures/birth_registration_strip.png` |
| 11 | Streamgraph of regional population shares, 1960–2020 | Mindanao's rise, NCR's plateau | 💡 |
| 12 | Flow-style arrows from SCI gravity residuals | which province pairs are more connected than distance predicts | 💡 careful: connectedness ≠ flows |

Design ground rules (all built figures follow them): validated diverging/sequential
palettes, no dual axes, direct labels over legends where possible, caveat
annotations on the figure itself (BARMM dagger, coverage notes).
