# A municipal-resolution internal migration dataset for the Philippines from open official data

*Dataset-paper skeleton (target: Scientific Data / Data in Brief / Asian
Population Studies / Philippine Review of Economics). Status: v0.2 — provincial
(2015–2020, 2020–2024) and municipal (2020–2024) residual series complete;
validation suite run and diagnosed; remaining [TODO]s are marked.*

## Abstract (draft)

Published Philippine internal migration data are census-timed, based on 5-year
recall questions, and released at province/region level. We construct and
release the first public dataset of residual-method net internal migration
estimates for Philippine provinces and highly urbanized cities (2015–2020,
2020–2024) together with the harmonized municipal-level inputs — census
populations (2000–2020), registered births and deaths (2017–2024), a
1,642-municipality PSGC register with a 4,688-event boundary changelog — and a
higher-frequency electoral-turnout proxy panel (2016–2025). Every value traces
to a named PSA/COMELEC source file. The core file provides municipal residual
net migration for 2020–2024 (1,626 municipalities; 2024 counts verified
against official totals).

## 1. Background & Summary

**What is published today.** For a country of 114 million with one of Asia's
fastest urban transitions, published evidence on internal migration is thin:

- PSA publishes **no net migration rates at any subnational level** — FOI
  responses (2022–2024, foi.gov.ph) direct requesters to census recall
  tables released at province/region level, census-timed, on 5-year recall.
- The **first and only dedicated national migration survey** in the
  country's statistical history is the 2018 NMS (PSA & UPPI, ~45,000
  households) — representative only to the regional level, and its published
  regional *net* flows do not sum to zero (+388k), a bias we diagnose in §4.
- The best global harmonized product, the **Human Internal Migration
  Database** (Dyrting & Taylor 2024, PLoS One), covers the Philippines at
  admin-1 only (2000 & 2010 IPUMS samples); modeled products (WorldPop
  admin-1 flow surfaces, Sorichetta et al. 2016 Sci Data; global gridded
  net-migration estimates, de Sherbinin et al.; Niva et al. 2023 [verify])
  are interpolations, not observations.
- Domestic literature: the PIDS pandemic report (MPRA 111917) compared 2020
  counts to projections as a one-off; PIDS DP 2023-20 models determinants
  from NMS microdata; the UNESCO country overview (2023) synthesizes the
  same coarse sources. **No study publishes municipal-level estimates, and no
  public province-to-province O-D matrix exists in any reachable open
  source** — we verified the latter exhaustively across PSA releases, the
  archived NSO web estate, and per-province census reports.

This dataset addresses that gap. Contributions: (i) municipal input panels
harmonized to a single PSGC vintage with documented boundary events; (ii)
residual net migration by province/HUC for two intercensal windows, including
the first estimates using the 2024 POPCEN; (iii) explicit uncertainty flags
(registration completeness — the BARMM civil-registration gap in particular —
and boundary breaks);
(iv) a reproducible open pipeline with a provenance ledger. Full related-work
notes: `paper/notes/related_work.md`.

## 2. Methods

### 2.1 Sources
Census counts (2020 CPH Table B; 2024 POPCEN Table A [+Table B TODO]); vital
statistics (VSD statistical tables 2017–2022; OpenSTAT 2023–2024; provincial
tables 2013–2023); PSGC 1Q-2025 datafile + Summary of Changes; OpenHalalan
vote counts (proxy). Acquisition routes and the Cloudflare/Internet-Archive
detour are documented in the repo; all files sha256-logged.

### 2.2 Harmonization
Name→PSGC resolution (layered matcher; 100% of census rows, >99.9% VS rows,
100% of proxy rows resolve uniquely); units = PSA "province or HUC" convention;
synthetic combined units where boundary events break comparability
(Maguindanao split; Cotabato→SGA; Makati→Taguig EMBO). PSA's 2024 Table A
restatement provides boundary-consistent 2010–2024 populations at unit level.

### 2.3 Residual method
NetMig = ΔP − (B − D); reference-date alignment by fraction-of-year weighting
of annual registered counts [monthly refinement TODO]. Known biases:
registration incompleteness (the residual absorbs it; the national closure
error is reported: +2.81M for 2015–2020, +0.54M for 2020–2024, which also
includes true international migration and census coverage differences).

## 3. Data Records

Table of files (data/clean/*) with row counts and fields — see CODEBOOK.md.
Zenodo DOI [TODO]. License ODbL.

## 4. Technical Validation

- National totals reconcile with PSA-published aggregates (<0.01–0.03%);
  the 2024 municipal transcription reconciles exactly (118/118 units) with
  PSA's official Table A.
- **External benchmarks fail for identifiable reasons**: NMS 2018 regional
  net migration does not sum to zero (+388k; origin-based surveys
  under-capture out-migrants) and correlates near-zero with the residual
  (r=0.07); census releases publish gross flows by type, not O-D nets
  (public province-level O-D matrices do not exist in any reachable open
  source — itself a finding). The two strongest signals agree across
  instruments: NCR strongly negative, CALABARZON strongly positive.
- **Internal reliability**: cross-period persistence of unit rates r=0.62
  (Spearman 0.51, n=115); geography matches known urbanization corridors and
  the Haiyan/Marawi event signatures (atlas tables).
- Proxy panel: the mayoral-votes proxy correlates with census population
  cross-sectionally (log-log r = 0.93–0.98) but weakly in growth
  (r ≈ 0.18, 2016→2022 votes vs 2015→2020 population): turnout noise dominates
  at 5-year municipal horizons. Reported as a limitation.
- BARMM: residual "in-migration" (Basilan +53/1,000/yr) is not credible as
  migration. PSA's 2020 CPH found 77% of BARMM's household population had a
  registered birth against 96.6% nationally [cite PSA 2020 CPH birth-
  registration release / UNICEF 2023], so the residual absorbs the
  registration gap as spurious in-migration; the region's 2024 census growth
  (3.43%/yr vs 0.80% national, per PSA's own highlights) cannot be decomposed
  with registered vital events of this quality. Flagged in the data.

## 5. Usage Notes

**Supported uses.** Cross-sectional comparison of municipal net migration
(2020–2024); two-period provincial comparison (2015–2020 vs 2020–2024);
shock analysis on the 1960–2020 census panel (worked examples in
Applications); benchmarking modeled global products against census-based
estimates; barangay-level 2010–2020 change within verified municipalities;
joining to any PSGC-coded administrative dataset (spending, projects,
elections) for policy evaluation.

**Cautions.** Compare places, not levels: the national closure error absorbs
international migration, registration incompleteness, and census coverage
differences. Do not read BARMM residuals as migration (registration
artifact; flagged in-data). Combined units (Makati+Taguig, Cotabato+SGA)
supersede their flagged component rows — drop the flagged rows before
aggregating, or regions containing them are double-counted. Registered
vital events are unadjusted for completeness; small-area extremes
(|rate| > 50/1,000/yr) are flagged.

**Not supported.** Origin–destination flows (net only), age/sex-specific
migration, sub-census-window frequency.

## 6. Figures

- Fig 1: choropleths 2015–2020 / 2020–2024 (figures/net_migration_province_maps.png) ✓
- Fig 2: municipal choropleth 2020–2024 (figures/net_migration_municipal_2020_2024.png) ✓
- Fig 3: validation scatter vs NMS 2018 (figures/validation_nms_scatter.png) ✓
- Table 1: top in/out units per period ✓ (from net_migration_province.csv).

## Applications

- **Event-study suite (delivered).** Six thin DiD designs on the 1960–2020
  panel + the 2020–2024 residual (atlas/event_studies_summary.csv; forest
  plot in figures/): Pinatubo 1991 −0.51 pp/yr [−0.98, +0.19] (suggestive
  1990s out-migration from the lahar provinces); Bohol earthquake 2013 ≈ 0
  (recovery too fast for a census-window signature); Haiyan +0.50 (n.s.) in
  the census window but **−1.14 [−1.53, −0.61] delayed** — the demographic
  cost arrives after the immediate recovery; Marawi 2017 **+1.30
  [+1.03, +1.57]**, which is hard to read as people moving toward a siege —
  we treat it as a count anomaly, not migration; Odette 2021 null with
  wide CI on the residual outcome. The suite also demonstrates that the panel
  supports shock analysis across six decades.
- **Gravity demonstration (delivered): social connectedness.** With no public
  O-D migration matrix, we fit the gravity model on Meta's Social
  Connectedness Index (81 GADM provinces, 6,006 directed pairs): distance
  elasticity −0.79, R² = 0.56 — the canonical gravity structure of
  accumulated migration/social networks. A province's SCI share toward the
  NCR+suburban core does NOT predict its residual net rate (r ≈ −0.12):
  connectivity reflects accumulated past migration, not current flow.
  True-flow gravity awaits IPUMS-International 2010 microdata (registration
  required).
- Flood-control scandal application (with D.D. Africa's DPWH panel): migration
  response to flood-control investment/failure — future work, one demo only.

## Data & Code Availability

GitHub [URL TODO] + Zenodo DOI [TODO], ODbL. Pipeline: `python3 pipeline/run_all.py`.

## Acknowledgements

OpenHalalan (R. R. Leung) for the election data plumbing model; PSA for the
underlying statistics; Internet Archive for preservation infrastructure.
