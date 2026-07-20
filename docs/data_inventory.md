# Data inventory, gaps, and acquisition TODOs

Status date: 2026-07-19. Everything acquired is listed in `data/provenance.jsonl`.

## Acquired

| Domain | Coverage | Source route |
|---|---|---|
| Census population, municipal | 2000, 2010, 2015, 2020 | 2020 CPH Table B via Wayback (psa.gov.ph blocks this machine) |
| Census population, province/HUC | 2010–2024 (restated to 2024 boundaries) | 2024 POPCEN Table A via Wayback |
| 2015 census, barangay-level | Regions IV-A, V, VII, IX, XI only | archived per-region files (R04A/R05/R07/R09/R11); rest TODO |
| Births & deaths, municipal | 2017–2024 (births 2018 missing; 2019 preliminary) | PSA VSD statistical tables (Wayback) + OpenSTAT API |
| Births & deaths, province/HUC | 2013–2023 | OpenSTAT API |
| Deaths by province | 2006–2015 | PSA deaths-by-cause file (all-cause extractable) |
| PSGC register + changes | 1Q-2025; changes 1977–present | Wayback |
| Election vote counts, municipal | 2013–2025 (5 cycles) | OpenHalalan (GitHub) |
| Province boundaries | 2023 PSGC vintage | faeldon/philippines-json-maps |
| 2020 CPH migration SR tables | region level | Wayback |
| PSY Table 1.1 provincial pops incl. **1995 & 2007** | 1990–2015, verified 81/81 vs panel folds | Wayback |
| 2010 CPH regional PDFs (barangay-level 2010) | 17 regions, text PDFs | identified in archive — future barangay-2010 dataset |
| 2018 NMS summary tables | region level, percent distributions | Wayback |

## Gaps & how to close them

1. **2024 POPCEN municipal counts (Table B)** — *worked around, replacement
   still wanted.* The residual now uses a pinned Wikipedia transcription of
   Table B verified exactly (118/118 units) against PSA's official Table A;
   the primary file remains preferable for publication. Exact source URL
   (from the archived release page):
   `https://psa.gov.ph/system/files/phcd/3_Table B - Population and Annual PGR
   by Province, City, and Municipality - By Region - rev_0.xlsx`.
   **Action: download in a normal browser** and save as
   `data/raw/census/2024popcen_tableB_muni.xlsx`; `run_all.py` switches to it
   automatically. (Per-region barangay-level 2024 files are linked on the same
   release page — grab those too for a future barangay product.)
2. **Municipal vital statistics 1990–2016 + full-year 2018 births + 2019
   final** — PDF-era Vital Statistics Reports. Action: eFOI request at
   foi.gov.ph to PSA-CRVS for machine-readable municipal tabulations of
   registered births/deaths by usual residence, 1990–2016, 2018, 2019 final.
   (FOI portal also blocks this machine — file from a browser.)
3. **1995 & 2007 MUNICIPAL census counts** — exhaustively hunted (Report 2A
   skips mid-decade; QuickStat XLS are single-year; NSCB archived pages cover
   only 8 municipalities in the right era; 2007 press attachments are age-table
   PDFs for ~35 provinces). They survive only in print/PDF-era publications →
   PSA Library / eFOI. Province-level 1995/2007 ARE now in the dataset (PSY
   Table 1.1, verified).
4. **Province-to-province O-D matrices** — 2010 CPH Table 12 series ("Domestic
   and International Migrants"), 2020 CPH migration report if published, or
   IPUMS-International microdata (2010 10% sample; requires registered
   download). Needed for gravity model + formal validation.
5. **COMELEC registered-voter counts by municipality per cycle** — COMELEC
   posts "Number of Registered Voters" PDFs/XLS per election; site behind
   Cloudflare. Alternative: NAMFREL/press mirrors; or add `registered_voters`
   if present in future OpenHalalan scrapes.
6. **DepEd per-school enrollment** — deped.gov.ph is Cloudflare-blocked and
   the archived dataset-page XLSX links (SY2014-15, SY2015-16 enrolment) were
   never successfully crawled (404 at crawl time). Action: download from
   DepEd's site in a browser, or FOI to DepEd; files then join by school
   division → municipality.
7. **Remaining 2015 barangay files** (12 regions) — same archived series as
   the five already fetched, for a future barangay-level product.

## New sources added (2026-07-19, second pass)

| Source | What | Status |
|---|---|---|
| Meta Social Connectedness Index (HDX) | 81×81 province friendship-tie matrix | acquired (`data/raw/sci/`), gravity demo in atlas |
| IOM DTM Philippines (HDX) | displacement rounds incl. Haiyan 2013-14 | acquired (`data/raw/dtm/`), event-study context |
| GADM 4.1 PH admin1 | code/name/centroid lookups for SCI | acquired |
| 2020 CPH Report 2A attachment (51 MB, archived) | barangay-level 2020 population | identified, not yet pulled — barangay product |
| 2015 POPCEN per-region barangay files | 5 of 17 regions archived | partial |
| Google Open Buildings 2.5D Temporal | building counts/area 2016-2023, ~4m | identified; PH tiles on GCS, aggregate to municipalities (few GB, streamable) — next proxy panel |
| WorldPop constrained annual rasters | modeled annual pop 100m | identified; comparison layer only (modeled) |
| VIIRS night lights (EOG/NASA Black Marble) | annual radiance panel | requires free registration (user-gated) |

## Access-route notes

- psa.gov.ph, rsso*.psa.gov.ph, foi.gov.ph: **Cloudflare 403** from this
  machine (datacenter IP). Workaround: Internet Archive (CDX index + `id_`
  raw fetches). Post-mid-2025 PSA files are mostly *not* archived (crawlers
  also blocked) — hence gap #1.
- openstat.psa.gov.ph PxWeb API: **works directly** (`pipeline/openstat.py`).
- GitHub (OpenHalalan, boundary files): works directly.
