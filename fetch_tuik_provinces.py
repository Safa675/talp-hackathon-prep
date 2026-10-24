"""Province-level (81 il) indicators from TÜİK's public geo portal (cip.tuik.gov.tr).
Unofficial/undocumented JSON endpoints (same ones the portal's own map uses); no login. Keep the CSV copies in case they change.
Run: python3 fetch_tuik_provinces.py   -> data/tuik_cip/provinces_long.csv, provinces_latest.csv
"""
import csv, json, os, urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tuik_cip")
UA = {"User-Agent": "Mozilla/5.0"}
PLATES = ("Adana Adıyaman Afyonkarahisar Ağrı Amasya Ankara Antalya Artvin Aydın Balıkesir Bilecik Bingöl Bitlis Bolu Burdur Bursa "
 "Çanakkale Çankırı Çorum Denizli Diyarbakır Edirne Elazığ Erzincan Erzurum Eskişehir Gaziantep Giresun Gümüşhane Hakkâri Hatay Isparta "
 "Mersin İstanbul İzmir Kars Kastamonu Kayseri Kırklareli Kırşehir Kocaeli Konya Kütahya Malatya Manisa Kahramanmaraş Mardin Muğla Muş "
 "Nevşehir Niğde Ordu Rize Sakarya Samsun Siirt Sinop Sivas Tekirdağ Tokat Trabzon Tunceli Şanlıurfa Uşak Van Yozgat Zonguldak Aksaray "
 "Bayburt Karaman Kırıkkale Batman Şırnak Bartın Ardahan Iğdır Yalova Karabük Kilis Osmaniye Düzce").split()
NAME = {str(i + 1): n for i, n in enumerate(PLATES)}
IND = {  # short name -> TÜİK indicator code
 "pop_total": "ADNKS-GK137473-O29001", "pop_male": "ADNKS-GK1003-O29001", "pop_female": "ADNKS-GK1004-O29001",
 "mean_years_schooling": "ULE-GK378667484-O29503", "labour_force_participation": "ISGD-GK18575-O18502",
 "employment_rate": "ISGD-GK18575-O18506", "unemployment_rate": "ISGD-GK18575-O18504",
 "age_dependency_ratio": "NFS-GK064-O005", "avg_household_size": "NFS-GK069-O005",
 "cars_per_1000": "ULS-GK093-O009", "gdp_per_capita_tl": "UHS-GK096-O0011", "gdp_per_capita_usd": "UHS-GK095-O0011",
 "ses_score": "ses123", "house_sales_total": "INS-GK055-O006",
}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def num(s):
    s = str(s).strip().replace(" ", "")
    if s in ("", "-", "...", "x"): return None
    try: return float(s.replace(",", "."))
    except ValueError: return None

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    menu = get("https://cip.tuik.gov.tr/assets/sideMenu.json?v=2.000")
    meta = {s["gostergeNo"]: s for g in menu["menu"] for s in g["subMenu"]}
    long_rows, latest = [], {}
    for short, code in IND.items():
        s = meta[code]
        for level in (3, 4):  # 3 = province; ses123 is also offered at 4
            if level not in s["duzeyler"]: continue
            url = (f"https://cip.tuik.gov.tr/Home/GetMapData?kaynak={s['kaynak']}&duzey={level}"
                   f"&gostergeNo={code}&kayitSayisi={s['kayitSayisi']}&period={s['period']}")
            try: d = get(url)
            except Exception as e:
                print(short, level, "FAILED", e); continue
            rows = d.get("veriler", [])
            if not rows or len(rows) not in (81,): 
                print(short, level, "rows:", len(rows), "(skipped: not 81 provinces)"); continue
            for r in rows:
                plate = str(r["duzeyKodu"])
                for date, v in zip(d["tarihler"], r["veri"]):
                    x = num(v)
                    long_rows.append([plate, NAME.get(plate, plate), short, date, x])
                    if x is not None and (plate, short) not in latest:
                        latest[(plate, short)] = (date, x)
            print(f"{short:28s} level {level}: {len(rows)} provinces, years {d['tarihler'][-1]}..{d['tarihler'][0]}")
            break
    with open(os.path.join(OUT, "provinces_long.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["plate", "province", "indicator", "year", "value"]); w.writerows(long_rows)
    inds = list(IND)
    with open(os.path.join(OUT, "provinces_latest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["plate", "province"] + inds + [i + "_year" for i in inds])
        for plate in sorted(NAME, key=int):
            vals = [latest.get((plate, i), (None, None)) for i in inds]
            w.writerow([plate, NAME[plate]] + [v[1] for v in vals] + [v[0] for v in vals])
    print("wrote", OUT)
