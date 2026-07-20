"""Parse the PSGC publication datafile into a canonical municipality register,
and provide name->PSGC resolution for PSA statistical tables that identify
municipalities only by (region, province, name) hierarchy.

Outputs:
    data/interim/psgc_municipalities.csv  — one row per city/municipality (incl. NCR cities)
    data/interim/psgc_provinces.csv       — provinces + NCR districts/HUC "province-equivalents"

Name normalization handles the usual PSA quirks:
    "City of Caloocan" vs "Caloocan City", "(Capital)" suffixes, footnote
    markers ("1/", "*"), ñ/Ñ vs n, casing, extra whitespace.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"

PSGC_FILE = RAW / "psgc" / "PSGC-1Q-2025-Publication-Datafile.xlsx"


def normalize_name(name: str) -> str:
    """Normalize an LGU name for matching across PSA sources."""
    if not isinstance(name, str):
        return ""
    s = name.strip()
    # strip footnote markers: trailing "1/", "2/", "*", bare digits ("STO. TOMAS 1")
    s = re.sub(r"\s*\d+/\s*$", "", s)
    s = re.sub(r"\s*\*+\s*$", "", s)
    s = re.sub(r"\s+\d+\s*$", "", s)
    # strip parentheticals we don't want to key on, but KEEP disambiguating ones
    # like "(Capital)"? No: "(Capital)" is annotation, drop it.
    s = re.sub(r"\(\s*capital\s*\)", "", s, flags=re.I)
    # PSA writes some old names in parens e.g. "Sto. Niño (Saug)"; keep primary part
    # unify "City of X" -> "X city" word bag
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))  # ñ -> n
    s = s.lower()
    s = s.replace("ñ", "n")
    # canonical city form: "city of caloocan" -> "caloocan city"
    m = re.match(r"^city of (.+)$", s)
    if m:
        s = f"{m.group(1)} city"
    # collapse punctuation/whitespace
    s = s.replace("&", " and ")
    s = re.sub(r"[.,'’`\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # spell out common abbreviations
    s = re.sub(r"\bsto\b", "santo", s)
    s = re.sub(r"\bsta\b", "santa", s)
    s = re.sub(r"\bgen\b", "general", s)
    s = re.sub(r"\bpres\b", "president", s)
    return s


def strip_parens(s: str) -> str:
    """Remove ALL parenthetical chunks and trailing footnote digits.
    'shariff aguak (maganoy) (capital)' -> 'shariff aguak';
    'city of sto tomas 1' -> handled at normalize level via trailing-digit strip.
    Operates on normalized or raw strings alike."""
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\s+\d+$", "", s.strip())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_province(name: str) -> str:
    """Province-context normalization for statistical-table headers:
    strips footnote digits/asterisks and parentheticals like
    '(excluding City of Isabela)' or '(NORTH COTABATO)'."""
    if not isinstance(name, str):
        return ""
    s = re.sub(r"\*+", " ", name)
    s = strip_parens(s)
    return normalize_name(s)


def base_name(norm: str) -> str:
    """City-blind base: 'calaca city' -> 'calaca' (for pre/post-cityhood matching)."""
    return re.sub(r"\s+city$", "", norm).strip()


def load_psgc() -> pd.DataFrame:
    df = pd.read_excel(PSGC_FILE, sheet_name="PSGC", dtype={"10-digit PSGC": str, "Correspondence Code": str})
    df = df.rename(columns={
        "10-digit PSGC": "psgc10",
        "Correspondence Code": "psgc9",
        "Name": "name",
        "Geographic Level": "level",
        "Old names": "old_names",
        "City Class": "city_class",
        "Income\nClassification": "income_class",
        "2020 Population": "pop2020_psgc",
    })
    df["psgc10"] = df["psgc10"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    return df


def build_register() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_psgc()
    # decode hierarchy from the 10-digit code: RRPPPMMBBB (region 2, prov 3, mun 2, bgy 3)
    df["region_code"] = df["psgc10"].str[:2]
    df["prov_code"] = df["psgc10"].str[:5]
    df["mun_code"] = df["psgc10"].str[:7]

    regions = df[df.level == "Reg"][["region_code", "name"]].rename(columns={"name": "region"})
    provs = df[df.level == "Prov"][["prov_code", "name", "income_class"]].rename(columns={"name": "province"})

    munis = df[df.level.isin(["Mun", "City"])].copy()
    munis = munis[["psgc10", "psgc9", "name", "level", "city_class", "income_class",
                   "old_names", "pop2020_psgc", "region_code", "prov_code"]]
    munis = munis.merge(regions, on="region_code", how="left")
    munis = munis.merge(provs[["prov_code", "province"]], on="prov_code", how="left")
    # NCR cities/municipality have no Prov row: use region as province context
    munis["province"] = munis["province"].fillna(munis["region"])
    munis["name_norm"] = munis["name"].map(normalize_name)
    munis["province_norm"] = munis["province"].map(normalize_name)
    return munis, provs.merge(regions.assign(k=1), how="cross", suffixes=("", "_r")) if False else (munis, provs)[1]


# Names that changed spelling/status between the Table B vintage and the
# 1Q-2025 PSGC, not covered by mechanical rules or the PSGC old-names column.
ALIASES = {
    ("bulacan", "baliuag"): "baliwag",
    ("masbate", "pio v corpuz (limbuhan)"): "pio v corpus",
    ("masbate", "pio v corpuz"): "pio v corpus",
    # renamed to Dr. Jose P. Rizal by RA 11983 (2024); PSGC old_names only has "Marcos"
    ("palawan", "rizal (marcos)"): "dr jose p rizal",
    ("palawan", "rizal marcos"): "dr jose p rizal",
    ("palawan", "rizal"): "dr jose p rizal",
    ("bohol", "jetafe"): "getafe",  # COMELEC spelling
    ("masbate", "pio v corpuz limbuhan"): "pio v corpus",
    # COMELEC prints old+current reversed: "BACUNGAN LEON T POSTIGO"
    ("zamboanga del norte", "bacungan leon t postigo"): "leon t postigo",
    ("lanao del sur", "tagoloan"): "tagoloan ii",  # Tagoloan II (the LdS one)
    ("cebu", "cordoba"): "cordova",  # COMELEC spelling
    ("misamis occidental", "ozamis"): "ozamiz city",
    ("misamis occidental", "ozamis city"): "ozamiz city",
    # spacing/spelling variants used in vital statistics tables
    ("batangas", "mataas na kahoy"): "mataasnakahoy",
    ("cebu", "pinamungahan"): "pinamungajan",
    # Wikipedia short forms / renames (LGU list article)
    ("misamis occidental", "don victoriano"): "don victoriano chiongbian",
    ("negros occidental", "don salvador benedicto"): "salvador benedicto",
    ("nueva ecija", "munoz"): "science city of munoz",
    ("rizal", "jalajala"): "jala jala",
    ("sultan kudarat", "senator ninoy aquino"): "sen ninoy aquino",
    ("sulu", "banguingui"): "tongkil",
    ("sulu", "panamao"): "old panamao",
    ("zamboanga del norte", "leon b postigo"): "leon t postigo",
    ("zamboanga del norte", "roxas"): "president manuel a roxas",
    ("zamboanga del norte", "sergio osmena"): "sergio osmena sr",
    ("davao del norte", "samal"): "island garden city of samal",
    ("cotabato", "pigcawayan"): "pigkawayan",
    ("davao del norte", "sawata"): "san isidro",
    ("lanao del norte", "balo i"): "baloi",
    ("maguindanao del sur", "datu montawal"): "pagagawan",
    ("maguindanao del sur", "general salipada k pendatun"): "general s k pendatun",
    ("antique", "san jose de buenavista"): "san jose",
    ("bukidnon", "impasugong"): "impasug ong",
    ("bulacan", "bulakan"): "bulacan",
    ("capiz", "sapian"): "sapi an",
    # BARMM Special Geographic Area: 2020 CPH Report 2A lists the eight SGA
    # municipalities by their barangay-cluster designations; correspondence to
    # the chartered names follows the BARMM MMA Acts creating them.
    ("special geographic area", "carmen cluster"): "kapalawan",
    ("special geographic area", "kabacan cluster"): "old kaabakan",
    ("special geographic area", "midsayap cluster i"): "kadayangan",
    ("special geographic area", "midsayap cluster ii"): "nabalawag",
    ("special geographic area", "pigkawayan cluster"): "pahamuddin",
    ("special geographic area", "pikit cluster i"): "malidegao",
    ("special geographic area", "pikit cluster ii"): "ligawasan",
    ("special geographic area", "pikit cluster iii"): "tugunan",
}

# Provinces that split/renamed after the source table's vintage: try each
# successor's context. Maguindanao split into Del Norte/Del Sur (RA 11550, 2022).
PROVINCE_ALIASES = {
    "maguindanao": ["maguindanao del norte", "maguindanao del sur"],
    # renamed Davao de Oro by RA 11297 (2019)
    "compostela valley": ["davao de oro"],
}

# HUCs/ICCs are statistically outside provinces (their PSGC province context is
# the region), but sources like COMELEC print them under the geographic host
# province. Index them under both. Keys are the city's normalized name.
CITY_HOST_PROVINCE = {
    "baguio city": "benguet", "angeles city": "pampanga", "olongapo city": "zambales",
    "lucena city": "quezon", "puerto princesa city": "palawan", "iloilo city": "iloilo",
    "bacolod city": "negros occidental", "cebu city": "cebu", "lapu lapu city": "cebu",
    "mandaue city": "cebu", "tacloban city": "leyte", "zamboanga city": "zamboanga del sur",
    "cagayan de oro city": "misamis oriental", "iligan city": "lanao del norte",
    "davao city": "davao del sur", "general santos city": "south cotabato",
    "butuan city": "agusan del norte", "isabela city": "basilan",
    "cotabato city": "maguindanao del norte", "ozamiz city": "misamis occidental",
}


def build_indexes(munis: pd.DataFrame):
    """Layered lookup tables keyed by (province_norm, name-variant).
    Current-name indexes are separate from old-name indexes so a current name
    always beats another LGU's former name (e.g. municipality Maguing vs
    Lumba-Bayabao's old name 'Maguing')."""
    cur = {"exact": {}, "stripped": {}, "based": {}}
    old = {"exact": {}, "stripped": {}, "based": {}}
    national = {}

    def add(ix, pv, v, m):
        sv = strip_parens(v)
        fv = re.sub(r"\s+", " ", v.replace("(", " ").replace(")", " ")).strip()
        ix["exact"].setdefault((pv, v), []).append(m)
        ix["stripped"].setdefault((pv, sv), []).append(m)
        if fv != v:
            # paren-flattened variant: "el nido (bacuit)" -> "el nido bacuit"
            # (COMELEC/OpenHalalan print old names inline without parentheses)
            ix["stripped"].setdefault((pv, fv), []).append(m)
        ix["based"].setdefault((pv, base_name(sv)), []).append(m)

    for _, m in munis.iterrows():
        pv = m.province_norm
        add(cur, pv, m.name_norm, m)
        host = CITY_HOST_PROVINCE.get(m.name_norm)
        if host:
            add(cur, host, m.name_norm, m)
        national.setdefault(m.name_norm, []).append(m)
        national.setdefault(strip_parens(m.name_norm), []).append(m)
        national.setdefault(base_name(strip_parens(m.name_norm)), []).append(m)
        if isinstance(m.old_names, str):
            for alt in re.split(r"[;,/]", m.old_names):
                if alt.strip():
                    an = normalize_name(alt)
                    add(old, pv, an, m)
                    # COMELEC-style concatenation: "JAVIER BUGHO" = name + old name
                    combo = f"{m.name_norm} {an}"
                    old["stripped"].setdefault((pv, combo), []).append(m)
                    national.setdefault(combo, []).append(m)
    return cur, old, national


def resolve(df: pd.DataFrame, munis: pd.DataFrame) -> pd.DataFrame:
    """Resolve rows with columns (name_src, province_src) to PSGC codes.
    Returns the frame plus psgc10 and match_method columns; unresolved rows are
    kept with psgc10 = "" — never dropped."""
    cur, old, national = build_indexes(munis)

    def uniq(d, k):
        c = d.get(k, [])
        codes = {m.psgc10 for m in c}
        return c[:1] if len(codes) == 1 and c else []

    out = []
    for _, row in df.iterrows():
        nn = normalize_name(row.name_src)
        pn = normalize_province(row.province_src or "")
        if re.search(r"\b(ncr|national capital|metro manila)\b", pn) or "district" in pn:
            # sources use "NCR SECOND DISTRICT" / "Metro Manila" as province context
            pn = "national capital region (ncr)"
        nn = ALIASES.get((pn, nn), nn)
        sn = strip_parens(nn)
        bn = base_name(sn)
        provs = [pn] + PROVINCE_ALIASES.get(pn, [])
        cand, method = [], "UNRESOLVED"
        for ix, tag in ((cur, "cur"), (old, "old")):
            for p in provs:
                for layer, key in (("exact", (p, nn)), ("stripped", (p, sn)), ("based", (p, bn))):
                    cand = uniq(ix[layer], key)
                    if len(cand) == 1:
                        method = f"{tag}:{layer}"
                        break
                if cand:
                    break
            if cand:
                break
        if len(cand) != 1:
            c = national.get(nn, []) or national.get(sn, []) or national.get(bn, [])
            codes = {m.psgc10 for m in c}
            if len(codes) == 1 and c:
                cand, method = c[:1], "name_unique_national"
        if len(cand) == 1:
            out.append({**row.to_dict(), "psgc10": cand[0].psgc10, "match_method": method})
        else:
            out.append({**row.to_dict(), "psgc10": "", "match_method": "UNRESOLVED"})
    return pd.DataFrame(out)


def main() -> None:
    munis, provs = build_register()
    INTERIM.mkdir(parents=True, exist_ok=True)
    munis.to_csv(INTERIM / "psgc_municipalities.csv", index=False)
    provs.to_csv(INTERIM / "psgc_provinces.csv", index=False)
    print(f"municipalities+cities: {len(munis)}")
    print(munis.level.value_counts().to_string())
    dupes = munis[munis.duplicated(["province_norm", "name_norm"], keep=False)]
    print("name collisions within province:", len(dupes))
    if len(dupes):
        print(dupes[["psgc10", "name", "province"]].to_string())


if __name__ == "__main__":
    main()
