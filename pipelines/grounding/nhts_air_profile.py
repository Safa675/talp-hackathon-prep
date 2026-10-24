"""Profile of US air travellers from the 2022 NHTS long-distance trip file (public, no key).
Source: FHWA National Household Travel Survey 2022 (nhts.ornl.gov). Weighted with WTPERFIN.
Usage: python3 -I nhts_air_profile.py <ldtv2pub.csv> <codebook.xlsx>  -> prints tables and writes nhts_air_profile.json
"""
import csv, json, re, sys, zipfile, collections, xml.etree.ElementTree as ET
M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

def codebook(path):
    z = zipfile.ZipFile(path)
    ss = ["".join(t.text or "" for t in si.iter(M + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(M + "si")]
    labels, cur = collections.defaultdict(dict), None
    for n in sorted(x for x in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", x)):
        for row in ET.fromstring(z.read(n)).iter(M + "row"):
            vals = []
            for c in row.findall(M + "c"):
                v = c.find(M + "v")
                vals.append("" if v is None else (ss[int(v.text)] if c.get("t") == "s" else v.text))
            if vals and re.fullmatch(r"[A-Z0-9_]+", vals[0] or ""): cur = vals[0]
            for x in vals:
                m = re.match(r"^(-?\d+)=(.+)$", x or "")
                if cur and m: labels[cur].setdefault(m.group(1), m.group(2).strip())
    return labels

def main(ldt, cb):
    lab = codebook(cb)
    rows = [r for r in csv.DictReader(open(ldt, encoding="utf-8")) if r["MAINMODE"] == "14"]  # 14 = airplane (AIRSIZE filled only here)
    W = lambda r: float(r["WTPERFIN"] or 0)
    tot = sum(W(r) for r in rows)
    out = {"source": "NHTS 2022 long-distance trips (FHWA), MAINMODE=14 air, weighted by WTPERFIN",
           "n_air_trips": len(rows), "tables": {}}
    def dist(name, key, order=None):
        c = collections.Counter()
        for r in rows:
            k = key(r)
            if k is not None: c[k] += W(r)
        s = sum(c.values())
        items = sorted(c.items(), key=(lambda kv: order.index(kv[0]) if order and kv[0] in order else 99) if order else (lambda kv: -kv[1]))
        out["tables"][name] = {k: round(100 * v / s, 1) for k, v in items}
        print(f"\n{name}  (n={len(rows)})"); [print(f"   {k:55s} {100*v/s:5.1f}%") for k, v in items]
    L = lambda var: (lambda r: None if r[var].startswith("-") else lab[var].get(r[var], r[var]))
    dist("trip purpose (FARREAS)", L("FARREAS"))
    dist("household income (HHFAMINC)", L("HHFAMINC"), order=[lab["HHFAMINC"].get(f"{i:02d}") for i in range(1, 12)])
    dist("household life cycle (LIF_CYC)", L("LIF_CYC"), order=[lab["LIF_CYC"].get(f"{i:02d}") for i in range(1, 11)])
    def age(r):
        a = int(r["R_AGE"]) if r["R_AGE"].lstrip("-").isdigit() else -1
        if a < 0: return None
        return next(b for lo, hi, b in [(0,17,"0-17"),(18,24,"18-24"),(25,34,"25-34"),(35,44,"35-44"),(45,54,"45-54"),(55,64,"55-64"),(65,200,"65+")] if lo <= a <= hi)
    dist("age of traveller", age, order=["0-17","18-24","25-34","35-44","45-54","55-64","65+"])
    def party(r):
        n = int(r["LD_NUMONTRP"]) if r["LD_NUMONTRP"].lstrip("-").isdigit() else -1
        return None if n < 0 else ("alone" if n <= 1 else "2" if n == 2 else "3-4" if n <= 4 else "5+")
    dist("people on the trip incl. respondent (LD_NUMONTRP)", party, order=["alone","2","3-4","5+"])
    def nights(r):
        n = int(r["NTSAWAY"]) if r["NTSAWAY"].lstrip("-").isdigit() else -1
        return None if n < 0 else ("0" if n == 0 else "1-3" if n <= 3 else "4-7" if n <= 7 else "8+")
    dist("nights away (NTSAWAY)", nights, order=["0","1-3","4-7","8+"])
    dist("destination inside/outside US (INT_FLAG)", L("INT_FLAG"))
    dist("home census division (CENSUS_D)", L("CENSUS_D"))
    # purpose x life cycle (children?) for persona mixing
    kids = lambda r: "with children" if r["LIF_CYC"] in ("03","04","05","06") else "no children" if not r["LIF_CYC"].startswith("-") else None
    for p in ("01","02","03","04"):
        sub = [r for r in rows if r["FARREAS"] == p]; s = sum(W(r) for r in sub)
        c = collections.Counter(); [c.__setitem__(kids(r), c[kids(r)] + W(r)) for r in sub if kids(r)]
        out["tables"].setdefault("children in household by purpose", {})[lab["FARREAS"].get(p, p)] = {k: round(100*v/s,1) for k, v in c.items()}
    print("\nchildren in household by purpose:", json.dumps(out["tables"]["children in household by purpose"], ensure_ascii=False))
    json.dump(out, open(sys.argv[3] if len(sys.argv) > 3 else "nhts_air_profile.json", "w"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
