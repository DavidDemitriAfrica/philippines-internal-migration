# Codebook — Philippine Internal Migration Dataset (v0.1, work in progress)

All files are UTF-8 CSV. Every number is traceable to a named PSA source file
via `data/provenance.jsonl` (original URL + Internet Archive URL + sha256).
Nothing is interpolated: where a source is missing, the value is empty and a
flag says why.

## Geographic identifiers

`psgc10` — 10-digit Philippine Standard Geographic Code (1Q-2025 vintage),
structure RRPPPMMBBB. `unit_id` — "province or HUC" statistical unit: 5-digit
PSGC province prefix for provinces; full `psgc10` for HUCs, NCR LGUs, City of
Isabela, City of Cotabato; `19999` = BARMM Special Geographic Area; composite
ids (`19087+19088`, `12047+19999`, `MKT+TAG`) are synthetic combined units
used where boundary changes make components non-comparable over a period.

## municipal_master.csv (1,642 rows)

The one-file version, for users who do not want to merge anything: identity
columns from `municipalities.csv`, census populations 1960-2020 from
`population_census_municipal.csv` plus the 2024 count, `births_YYYY` /
`deaths_YYYY` for 2017-2024 from `vital_statistics_municipal.csv`, and
`net_migration` / `netmig_rate_per_1000_yr` / `flag` from
`net_migration_municipal_2020_2024.csv`. It contains no new information;
every column is documented in its source file's section below and carries
the same caveats.

## municipalities.csv (1,642 rows)

One row per city/municipality in the 1Q-2025 PSGC. Columns: psgc10, psgc9
(pre-2019 correspondence code), name, level (City/Mun), city_class (HUC/CC/ICC),
income_class, province (statistical province context; NCR LGUs carry the
region), region, old_names (PSA-recorded former names).

## population_census_municipal.csv (1,634 rows)

Census population per municipality for the **1960, 1970, 1980, 1990, 2000,
2010, 2015, and 2020** censuses. 2000-2020 come from the 2020 CPH Table B
("Population and Annual Growth Rates by Province, City, and Municipality");
1960-1990 come from 2020 CPH Report No. 2A Table 1 ("Population Enumerated in
Various Census by City/Municipality: 1960-2020"), element-wise verified
against Table B on the four overlapping censuses (6,536 cells; the 47
disagreements are documented boundary restatements — the six N. Cotabato SGA
mothers, Burdeos/Panukulan, Dumalneg — and carry `hist_flag`). Report 2A also
supplies restated 1960-2020 series for the eight SGA municipalities under
their barangay-cluster designations (mapped to chartered names per the BARMM
MMA Acts) and historical values for LGUs dissolved before 2020 (e.g. Bacon,
Sorsogon). Coverage: 1,352 municipalities have 1960 values; 1,594 have 1990.
Boundaries are **as of the 2020 census** (Report 2A vintage restates the SGA
transfer only).
`name_src`/`province_src` = names as printed in the source; `match_method` =
how the row was matched to the PSGC (cur:exact / cur:stripped / cur:based /
old:* / name_unique_national). The 8 BARMM Special Geographic Area
municipalities (created 2021-2023) have no rows here — their territory was
enumerated under North Cotabato municipalities in 2020 (see psgc_changes.csv).
Mid-decade POPCEN counts (1975, 1995, 2007) are not in this table (Report 2A
T1 lists decennial+2015+2020 only); archived per-province releases could add
them later. National sums are within 0.003% of published
totals (small "not shown separately" remainders).

## vital_statistics_municipal.csv (~13k rows)

Registered live births (by usual residence of mother) and registered deaths
(by usual residence), both sexes, per municipality per year, 2017-2024.
Sources: PSA VSD statistical tables 2017-2022 (XLSX), OpenSTAT 2023-2024.
Flags: `preliminary` for 2019 (PSA released only preliminary municipal
tables). Known gaps: births 2018 municipal never published as XLSX (deaths
2018 present); years ≤2016 municipal published only in PDF-era Vital
Statistics Reports (eFOI request TODO). **Registered ≠ occurred**: under- and
late registration vary by area (worst in BARMM) and are NOT adjusted; PSA
publishes no municipal completeness estimates.

## psgc_changes.csv (4,688 events)

PSA's Summary of Changes to the PSGC (1977-2000, 2001-present sheets):
municipality creations, cityhood conversions and reversions, renames,
transfers, mergers, with legal basis and dates. `level` classifies events as
province / city_muni / barangay.

## net_migration_province.csv

Residual net migration by province/HUC unit for intercensal periods
2015-2020 (2015-08-01 → 2020-05-01) and 2020-2024 (2020-05-01 → 2024-07-01):

    net_migration = (pop_end − pop_start) − (births_est − deaths_est)

- 2015-2020 uses original-boundary census counts (2020 CPH Table B aggregates)
  with same-vintage VS; 2020-2024 uses PSA's 2024 POPCEN Table A series, which
  restates 2010/2015/2020 populations to 2024 boundaries.
- births_est/deaths_est: annual registered counts weighted by the fraction of
  the calendar year inside the period (uniform within-year allocation —
  documented approximation; monthly tables exist for refinement).
- `netmig_rate_per_1000_yr` = net_migration / mid-period population / period
  length × 1000.
- `flag` carries unit-specific caveats: the BARMM civil-registration gap
  (PSA's 2020 CPH found 77% of BARMM's household population had a registered
  birth against 96.6% nationally — the residual absorbs the gap as spurious
  in-migration; see the UNICEF/PSA figures cited in the README), boundary
  restatements (Makati/Taguig EMBO transfer; Cotabato→SGA), non-computable
  units with the missing years listed.
- The **national sum of residuals is not zero**: it absorbs international
  migration, census coverage differences, and vital-registration
  incompleteness (2015-2020: +2.81M; 2020-2024: +0.54M). Interpret levels
  with this closure error in mind; comparisons across units are more
  reliable than any single level.
  Formal validation against census migration questions is pending the
  province-to-province O-D tables (see docs/data_inventory.md TODOs).

## net_migration_municipal_2020_2024.csv (1,642 rows; 1,626 estimates)

Municipal residual net migration, 2020-05-01 → 2024-07-01. 2020 base = 2020
CPH Table B; 2024 population = **verified transcription** of PSA's 2024 POPCEN
Table B via English Wikipedia's LGU list (pinned revision 1364613900,
2026-07-17), accepted because municipal sums reconcile **exactly (118/118
units)** with PSA's official Table A totals held in our raw store; the primary
Table B XLSX is a drop-in replacement (see docs/data_inventory.md gap #1).
16 rows carry `EXCLUDED` flags instead of estimates: Makati & Taguig (EMBO
barangay transfer breaks 2020 comparability), the six North Cotabato
municipalities that ceded barangays to the BARMM SGA, and the eight SGA
municipalities (no 2020 base). Flags also mark BARMM under-registration and
|rate| > 50/1,000/yr small-area extremes. Note: PSA's Summary-of-Changes sheet
ends in 2019; post-2019 boundary events are documented from the PSGC datafile
and the laws cited in the codebook, not the changelog.

## proxy_mayor_votes_municipal.csv

Total mayoral votes per city/municipality per election (2016, 2019, 2022,
2025), from OpenHalalan. Cross-sectional log-log correlation with census
population 0.93–0.98; growth-on-growth correlation with census growth **0.18**
and with the municipal residual (same window, 2022→2025 votes vs 2020–2024
rate) **0.08** — electoral turnout is a poor migration proxy at 5-year
municipal horizons. Published for reuse, with that warning.

## validation_region_nms.csv & validation

- **No reliable external net-migration benchmark exists** at any subnational
  level: NMS 2018 regional nets (Table 4) do not sum to zero (+388k) because
  origin-based surveys under-capture out-migrants; census "residence 5 years
  ago" releases publish gross flows by type, not O-D nets. Correlations with
  the residual are near zero and are reported as such, with the diagnosis.
- **Internal reliability**: unit rates persist across independent periods
  (2015-2020 vs 2020-2024: Pearson r = 0.62, Spearman 0.51); national totals
  reconcile with PSA aggregates; the geography matches known urbanization
  (Cavite/Laguna/Bulacan in, NCR core and remote uplands out; Tacloban's
  post-Haiyan growth collapse and Marawi's siege-period stagnation are visible
  in data/clean/atlas/).

## atlas/ (data/clean/atlas/)

Ranked rate tables (both levels/periods) and event tables for Haiyan (Eastern
Visayas) and Marawi with annualized census growth by sub-period plus the
2020-2024 residual.

## vital_statistics_provincial.csv (1,558 rows)

Geographic-province panel (HUCs folded into host provinces; NCR one unit;
Maguindanao undivided; Cotabato incl. the future-SGA barangays), 2006-2024:
deaths 2006-2012 from PSA's deaths-by-cause tables (HUCs folded at source —
verified: Benguet 2013 = Benguet + Baguio exactly); births+deaths 2013-2024
from the unit series folded with the same geography. Splice check on the
overlap years: 242/246 cells equal, 4 differ by 1-3 deaths (publication
revisions). Births before 2013 were never published at this level in
reachable open sources (flagged; eFOI TODO).

## population_barangay_2010.csv (42,527 rows) & the 2010→2020 barangay panel

Barangay populations from the 2010 census, extracted from the 17 archived
regional press-release PDFs (text extraction with bold-overprint dedup,
column-aware row reconstruction, page-header province contexts). For every
municipality the barangay sum is compared against the official 2010
municipal count: **1,528 of 1,621 municipalities (94.3%) reconcile
exactly**; rows in the other 93 carry a flag and a
`muni_sum_verified=false` column and are excluded from the merged panel.
`population_barangay_2020.csv` now carries a `pop2010` column for the 35,634
barangays that are PSGC-matched in both censuses within verified
municipalities — the finest-grained population-change dataset available for
the Philippines.

## population_barangay_2020.csv (42,041 rows)

Total and household population per barangay, 2020 CPH ("as of 01 May 2020"),
all 17 regions, from the archived per-region PSA files (incl. the BARMM
"Interim Province" = future SGA barangays; Manila resolved through its
sub-municipal districts). National sum reconciles with the official total to
0.02%. 90.8% of rows carry a barangay-level `psgc10` (exact or
paren-stripped name match within the municipality block); the rest are
flagged (spelling variants, ambiguous within-municipality names) — never
dropped. A future pass can close the tail with the PSGC old-names column.

## Interim files (data/interim/)

Machine artifacts of the build; regenerate with `python pipeline/run_all.py`.
