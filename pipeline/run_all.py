"""One-command build: raw sources -> clean dataset.

Assumes data/raw/ is already populated (download scripts: openstat.py,
wayback.py; every file logged in data/provenance.jsonl). Re-running is
idempotent.

    python3 pipeline/run_all.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

STEPS = [
    "psgc.py",           # PSGC register (municipality/province lookup tables)
    "parse_census.py",   # 2020 CPH Table B -> municipal census panel
    "parse_census_historical.py",  # Report 2A T1 -> 1960-1990 municipal counts
    "parse_vitals.py",   # VSD/OpenSTAT tables -> municipal births/deaths panel
    "parse_changes.py",  # PSGC summary of changes -> boundary event log
    "parse_pop2024_wiki.py",  # 2024 POPCEN municipal counts (verified transcription)
    "build_dataset.py",  # clean files + provincial (and municipal) residuals
    "make_master.py",    # one-file join: municipal_master.csv
    "parse_votes_proxy.py",  # OpenHalalan mayoral-votes proxy panel
    "make_maps.py",      # choropleth figures
    "make_map_municipal.py",  # municipal choropleth
    "validate_nms.py",   # validation suite + scatter
    "make_atlas.py",     # ranked rate tables + event tables
    "event_studies.py",  # event-study suite (incl. Haiyan)
    "make_centroid_drift.py",  # center-of-gravity figure
    "make_growth_gif.py",     # animated growth-share GIF (README)
    "parse_psy_prov.py",      # province windows (1995/2007 censuses) figure
    "make_birthreg_strip.py", # birth-registration visibility strip
    "gravity_sci.py",    # gravity demo on social connectedness
    "make_site_data.py", # single geojson behind both site maps + window thumbnails
    "make_region_bars.py",  # region bar chart + NCR dumbbell for the site
    "make_hero_map.py",  # static sideways hero map with metro cutaways
    "make_capital_shares.py",  # NCR vs suburban-ring population shares 1960-2020
    "build_prov_vs_panel.py",  # provincial VS panel 2006-2024
    "parse_barangay2020.py",   # barangay-level 2020 populations
    "parse_barangay2010.py",   # barangay-level 2010 from archived PDFs (QA-flagged)
]


def main() -> None:
    for step in STEPS:
        print(f"\n=== {step} ===")
        r = subprocess.run([sys.executable, str(HERE / step)])
        if r.returncode != 0:
            sys.exit(f"FAILED at {step}")
    print("\nBuild complete. Outputs in data/clean/")


if __name__ == "__main__":
    main()
