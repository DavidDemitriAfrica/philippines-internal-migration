# Phase 0 — Novelty & literature check (2026-07-19)

**Question:** Does a public, municipality-level internal migration dataset for the
Philippines already exist? **Answer: no evidence of one.** The gap claimed in the
project goal is confirmed, with the caveats in §3 (modeled global grids exist and
must be cited and distinguished).

## 1. What PSA actually publishes

- **Census migration tables ("residence 5 years ago", lifetime migration):**
  published at **region/province level** in census-year releases.
  - 2020 CPH: "Migration and Overseas Workers" release
    (https://psa.gov.ph/content/migration-and-overseas-workers-2020-census-population-and-housing-2020-cph).
    Region-level highlights; movers classified as short-distance (within-province) /
    long-distance (cross-province). Regional PSA offices released per-region
    highlight tables (e.g. CAR: https://rssocar.psa.gov.ph/population-statistics/node/56699).
  - 2010 CPH: report "Domestic and International Migrants in the Philippines" and
    Table 12 (Household Population 5+ by Place of Present Residence × Place of
    Residence 5 Years Ago, by City/Municipality) — *destination* municipality by
    *origin province* at best; the public O-D matrices are province-level.
- **2018 National Migration Survey (PSA + UPPI):** ~45,000 households, first
  dedicated migration survey; representative at national/regional level, NOT
  municipal. (https://www.uppi.upd.edu.ph/research/the-national-migration-survey:-towards-scientific-knowledge-on-migration)
- **No published net migration rates, even provincial.** FOI request "Net
  Migration Per Province" (Oct 2023, foi.gov.ph): PSA replied its data are limited
  to CPH tables + the 2020 CPH Migration and Overseas Workers release. A Jan 2022
  FOI on migration data got the same pointer set. A further FOI asking for
  city/municipality-level migration data 2010–2025
  (https://www.foi.gov.ph/agencies/psa/migration-ofws-employment-bpos-hospitals-atmsbanks-building-permits-data-by-citymunicipality-2010-to-2025/)
  exists — page is Cloudflare-blocked (403) from this machine; content unverified
  [TODO-verify manually in browser], but search snippets indicate PSA again pointed
  to CPH tables and the Survey on Overseas Filipinos.
- **UPPI 2020 census-based population projections** documentation: net migration is
  an *optional* projection component, handled at national level only.
  (https://www.uppi.upd.edu.ph/sites/default/files/pdf/2020-Census-based-National-Population-Projection-Documentation-Report.pdf)

## 2. Domestic academic near-neighbors (cite, none municipal residual)

- **PIDS COVID-19 internal migration report (MPRA 111917, ~2021):** compared 2020
  CPH *actual vs. projected* municipal populations as a crude migration signal
  (e.g., Tacloban ~8k below projection). Closest domestic relative to our idea —
  but it is a one-off deviation-from-projection exercise, not a residual-method
  net migration dataset, and not released as data.
  (https://mpra.ub.uni-muenchen.de/111917/1/MPRA_paper_111917.pdf)
- **PIDS DP 2023-20** (Subnational infrastructure & internal migration): uses 2018
  NMS microdata for determinants modeling — no new migration measurement.
  (https://pidswebs.pids.gov.ph/CDN/document/pidsdps2320.pdf)
- Classic PH internal migration literature (Flieger; P.C. Smith; UPPI working
  papers) computed **province-level** census-survival / residual estimates for
  pre-1990 intercensal periods. [TODO-verify exact citations at PSA Library /
  library.psa.gov.ph when drafting; web search was inconclusive.]

## 3. Global modeled products that touch PH fine-grained migration (must cite & distinguish)

- **HIMD — Human Internal Migration Database** (Dyrting & Taylor 2024, PLoS One
  methods protocol; https://pmc.ncbi.nlm.nih.gov/articles/PMC11630604/):
  age-origin-destination migration probability "cubes" from IPUMS-I census
  microdata, 54 countries. **Philippines included: 2000 & 2010 samples, admin-1
  (up to 75 provinces), 5- and 10-yr intervals.** Province level only; explicitly
  notes finer levels are future work.
- **WorldPop / Sorichetta et al. 2016** (Sci Data 3:160066, "Mapping internal
  connectivity through human migration in malaria endemic countries"): modeled
  (gravity-interpolated from census microdata) 5-year admin-1 O-D flows circa
  2010 for low/middle-income countries incl. Asia. PH included at province level.
  [TODO-verify PH inclusion & vintage from the paper's supplementary tables —
  fetch was blocked from this machine.]
- **Global gridded net migration (residual, modeled):**
  - de Sherbinin et al. / CIESIN-SEDAC, "Global Estimated Net Migration Grids by
    Decade 1970–2000" — subnational census pop change minus natural increase,
    downscaled to grid. [SEDAC servers migrated to NASA Earthdata; TODO-verify
    current landing URL.]
  - Niva et al. 2023 (Nature Human Behaviour, Aalto/Kummu group), global ~1 km
    net migration 2000–2019 via residual method on gridded population and
    downscaled births/deaths. [TODO-verify exact citation.]
  These are **fine-grained but modeled/downscaled**: subnational inputs are
  interpolated, natural-increase surfaces are disaggregated from coarser admin
  data, and the products are documented as noisy at local scale. None provides
  observed municipal-level PH estimates with harmonized PSGC boundaries or
  provenance to named PSA source files.

## 4. Novelty statement (draft, for the paper)

> Published Philippine internal migration data are census-timed, based on 5-year
> recall questions, and released at province/region level; PSA publishes no net
> migration rates at any subnational level (confirmed by FOI responses, 2022–2024).
> Global harmonized or modeled products (HIMD, WorldPop flows, global net-migration
> grids) cover the Philippines only at admin-1 level or as modeled grid surfaces.
> To our knowledge this is the first public dataset of *observed* (residual-method)
> net internal migration for all ~1,600 Philippine cities and municipalities,
> harmonized across boundary changes via a documented PSGC crosswalk, with a
> higher-frequency proxy panel (voter registration, school enrollment) and full
> provenance to named PSA/COMELEC/DepEd source files.

## 5. Search-method note

Searches run 2026-07-19 via web search from this session (PSA, PIDS, UPPI, FOI
portal, HIMD, WorldPop, SEDAC targets). Several queries/fetches were blocked by
tooling filters or site 403s; those items carry explicit [TODO-verify] flags
above. None of the blocked items plausibly contains a municipal-level PH
migration dataset (they are global modeled products or FOI response pages whose
snippets we could read), so the go/no-go conclusion stands: **GO — build.**
