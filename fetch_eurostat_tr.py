"""Pull Turkey (TR) tables from the Eurostat dissemination API into tidy CSVs.
Eurostat republishes TÜİK survey data (ICT usage, LFS, SILC, HBS) for Türkiye; reuse is free with attribution.
Run:  python3 fetch_eurostat_tr.py            (writes data/eurostat/<code>.csv)
"""
import csv, json, os, sys, urllib.request

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "eurostat")
DATASETS = [
    "isoc_ec_ib20",      # online purchases 2020+: age, sex, education, activity, ... x product category
    "isoc_ci_ifp_iu",    # internet use by individuals
    "isoc_ci_ac_i",      # internet activities (e-banking, social networks, ...)
    "isoc_ci_dev_i",     # devices used
    "demo_pjan",         # population on 1 Jan, single age x sex
    "lfsa_pgaed",        # population by education attainment x age x sex (LFS)
    "ilc_di01",          # income distribution / quintile thresholds (SILC)
    "ilc_di03",          # mean/median income by age x sex (SILC)
    "ilc_mdes04",        # can afford unexpected expense (SILC)
    "ilc_mdes09",        # deprivation items (SILC)
    "hbs_str_t211",      # household budget: expenditure shares by income quintile (to 2020)
]

def fetch(code, geo="TR"):
    url = f"{BASE}{code}?format=JSON&lang=en&geo={geo}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)

def to_rows(d):
    ids, sizes = d["id"], d["size"]
    cats = []
    for dim in ids:
        c = d["dimension"][dim]["category"]
        idx = c["index"]
        codes = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx)
        cats.append((codes, c.get("label", {})))
    values, status = d.get("value", {}), d.get("status", {})
    strides, s = [], 1
    for n in reversed(sizes):
        strides.append(s); s *= n
    strides.reverse()
    header = []
    for dim in ids:
        header += [dim, dim + "_label"]
    header += ["value", "flag"]
    rows = []
    for k, v in values.items():
        i = int(k); rec = []
        for pos, (codes, labels) in enumerate(cats):
            j = (i // strides[pos]) % sizes[pos]
            rec += [codes[j], labels.get(codes[j], "")]
        rec += [v, status.get(k, "")]
        rows.append(rec)
    return header, rows

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for code in DATASETS:
        try:
            d = fetch(code)
            header, rows = to_rows(d)
        except Exception as e:
            print(f"{code}: FAILED {e}", file=sys.stderr); continue
        with open(os.path.join(OUT, f"{code}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(header); w.writerows(rows)
        print(f"{code}: {len(rows)} rows, updated {d.get('updated','')[:10]}")
