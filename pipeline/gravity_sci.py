"""Demonstration: gravity structure of inter-province social connectedness,
and its link to residual migration.

Public province-to-province migration O-D matrices do not exist for the
Philippines (see inventory). Meta's Social Connectedness Index (SCI) — the
relative probability of a Facebook friendship tie between two provinces — is
a standard proxy for accumulated migration networks. Two thin results:

  1. Gravity fit: log SCI_ij ~ log distance_ij + log pop_i + log pop_j
     (81 GADM provinces; NCR is one unit).
  2. Bridge to migration: a province's SCI-weighted connection to the
     in-migration core (NCR + Cavite/Laguna/Rizal/Bulacan) vs its residual
     net migration rate 2015-2020.

Output: data/clean/atlas/gravity_sci_province.csv + printed estimates.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from psgc import normalize_name, CITY_HOST_PROVINCE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"


def haversine(lon1, lat1, lon2, lat2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    dp = p2 - p1
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def norm_gadm(s: str) -> str:
    # GADM concatenates: "AgusandelNorte" -> "agusan del norte"-ish key:
    # strip spaces from both sides instead
    return re.sub(r"[^a-z]", "", str(s).lower())


def main() -> None:
    sci = pd.read_csv(RAW / "sci" / "sci_phl_gadm1.csv")
    cent = pd.read_csv(RAW / "sci" / "gadm41_phl_admin1_centroids.csv")
    cent["key"] = cent.NAME_1.map(norm_gadm)

    # geographic-province 2020 populations (HUCs folded into hosts; NCR one unit)
    cp = pd.read_csv(CLEAN / "population_census_municipal.csv", dtype={"psgc10": str})
    host = {}
    for _, r in cp.iterrows():
        nm = normalize_name(str(r["name"]))
        prov = CITY_HOST_PROVINCE.get(nm)
        if prov is None:
            prov = normalize_name(str(r.province))
            if "national capital region" in prov:
                prov = "metropolitan manila"
        host[r.psgc10] = prov
    cp["geo_prov"] = cp.psgc10.map(host)
    pops = cp.groupby("geo_prov")["pop2020"].sum()
    pops.index = [re.sub(r"[^a-z]", "", i) for i in pops.index]

    cent["pop2020"] = cent.key.map(pops)
    matched = cent.pop2020.notna().sum()
    print(f"GADM provinces matched to census pops: {matched}/81")
    if matched < 75:
        print(cent[cent.pop2020.isna()][["NAME_1", "key"]].to_string())

    meta = cent.set_index("GID_1")
    df = sci[sci.user_region != sci.friend_region].copy()
    for side, pre in (("user_region", "u"), ("friend_region", "f")):
        df[f"{pre}_lon"] = df[side].map(meta.lon)
        df[f"{pre}_lat"] = df[side].map(meta.lat)
        df[f"{pre}_pop"] = df[side].map(meta.pop2020)
        df[f"{pre}_name"] = df[side].map(meta.NAME_1)
    df = df.dropna(subset=["u_pop", "f_pop"])
    df["dist_km"] = haversine(df.u_lon, df.u_lat, df.f_lon, df.f_lat)
    df = df[(df.scaled_sci > 0) & (df.dist_km > 0)]

    y = np.log(df.scaled_sci.values)
    X = np.column_stack([np.ones(len(df)), np.log(df.dist_km.values),
                         np.log(df.u_pop.values), np.log(df.f_pop.values)])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    r2 = 1 - resid.var() / y.var()
    print(f"gravity fit on SCI: n={len(df)} directed pairs; "
          f"distance elasticity {beta[1]:+.3f}; pop elasticities {beta[2]:+.3f}/{beta[3]:+.3f}; "
          f"R^2={r2:.3f}")

    # bridge: SCI share toward the in-migration core vs residual net rate
    core_keys = {"metropolitanmanila", "cavite", "laguna", "rizal", "bulacan"}
    df["to_core"] = df.f_name.map(lambda s: norm_gadm(s) in core_keys)
    share = df.groupby("u_name").apply(
        lambda g: g.loc[g.to_core, "scaled_sci"].sum() / g.scaled_sci.sum(),
        include_groups=False).rename("sci_share_to_core")

    prov = pd.read_csv(CLEAN / "net_migration_province.csv", dtype={"unit_id": str})
    prov = prov[(prov.period == "2015-2020") & prov.net_migration.notna()].copy()
    # fold units to geographic provinces to match GADM
    munis = pd.read_csv(CLEAN / "municipalities.csv", dtype=str)
    name_by_id = dict(zip(munis.psgc10, munis.name))
    def geo_key(r):
        uid = r.unit_id
        if len(uid) == 5 and uid.isdigit():
            return norm_gadm(r.unit_name)
        nm = normalize_name(name_by_id.get(uid, ""))
        h = CITY_HOST_PROVINCE.get(nm)
        if h:
            return re.sub(r"[^a-z]", "", h)
        if uid.startswith("13"):
            return "metropolitanmanila"
        if uid == "19087+19088":
            return None  # split below
        return None
    prov["gkey"] = prov.apply(geo_key, axis=1)
    rows = prov[prov.gkey.notna()].groupby("gkey").agg(
        net=("net_migration", "sum"), p0=("pop_start", "sum"), p1=("pop_end", "sum"))
    rows["rate"] = rows.net / ((rows.p0 + rows.p1) / 2) / 4.75 * 1000
    share.index = [norm_gadm(s) for s in share.index]
    j = rows.join(share, how="inner").dropna()
    r_core = np.corrcoef(j.sci_share_to_core, j.rate)[0, 1]
    rho = j.sci_share_to_core.rank().corr(j.rate.rank())
    print(f"SCI share to NCR+core vs residual net rate 2015-2020: "
          f"r={r_core:+.3f}, Spearman={rho:+.3f} (n={len(j)})")
    (CLEAN / "atlas").mkdir(exist_ok=True)
    j.round(4).to_csv(CLEAN / "atlas" / "gravity_sci_province.csv")
    print("wrote", CLEAN / "atlas" / "gravity_sci_province.csv")


if __name__ == "__main__":
    main()
