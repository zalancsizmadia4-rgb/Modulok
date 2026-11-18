import os
import re
import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(title="Cordwainer Saját Szerver Motor", version="9.0")

SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"
MEMORIA_FAJL = "hosszutavu_memoria.json"
HATTER_FAJL = "deep_work_feladatok.json"
PROFIL_FAJL = "felhasznalo_profil.json"


def betolt_json(fajl: str, alap: Any) -> Any:
    if os.path.exists(fajl):
        try:
            with open(fajl, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return alap
    return alap


def ment_json(fajl: str, adat: Any) -> None:
    with open(fajl, "w", encoding="utf-8") as f:
        json.dump(adat, f, ensure_ascii=False, indent=2)


def ellenoriz_kulcsot(authorization: str = Header(None)) -> bool:
    if not authorization or authorization.replace("Bearer ", "").strip() != SAJAT_TITKOS_KULCS:
        raise HTTPException(status_code=401, detail="Hibás szerver kulcs!")
    return True


def http_get_json(url: str, timeout: int = 8) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CordwainerServer/9.0 (autonomous-local-engine)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def profil_frissitese(uzenet: str, profil: Dict[str, Any]) -> Dict[str, Any]:
    # Név felismerése (pl. "Zalán a nevem", "a nevem Zalán", "Zalán vagyok")
    m_nev = re.search(
        r"(?:a nevem|nevem|én vagyok|en vagyok)\s+([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+)",
        uzenet,
    )
    if m_nev:
        profil["nev"] = m_nev.group(1).strip()

    # Stíluspreferenciák
    kis = uzenet.lower()
    if any(k in kis for k in ["röviden", "tömören", "ne beszélj ennyit", "csak a lényeg"]):
        profil["stilus"] = "tömör"
    elif any(k in kis for k in ["részletesen", "minden infó", "mindent nézz át", "alaposan"]):
        profil["stilus"] = "részletes"

    return profil


def tisztit_keresokifejezest(uzenet: str) -> str:
    s = uzenet.strip()
    s = re.sub(
        r"^(jó|jo|na|figyelj|mondd|szólj|nézd meg|keress rá|keress meg|elemezd|vizsgáld meg)[,\s]+",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(ki volt|ki az|mi volt|mi az|mit tudsz erről|mit tudsz róla|miért van|hogyan működik|mi az oka)\b",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"[?!.]+$", "", s).strip()
    return s if len(s) >= 2 else uzenet.strip()


def keres_wikipedia_reszletes(kifejezes: str, lang: str = "hu") -> Optional[Dict[str, Any]]:
    q = urllib.parse.quote(kifejezes)
    search_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&list=search&srsearch={q}&format=json&srlimit=3"
    )
    search_data = http_get_json(search_url)
    if not search_data:
        return None

    talalatok = search_data.get("query", {}).get("search", [])
    if not talalatok:
        return None

    fo_cim = talalatok[0]["title"]
    cim_kodolt = urllib.parse.quote(fo_cim)
    summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{cim_kodolt}"
    summary = http_get_json(summary_url)
    if not summary or not summary.get("extract"):
        return None

    # Bevezető szöveg lekérése a query API-n keresztül (gyakran több bekezdést ad)
    extract_url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=query&prop=extracts&exintro=1&explaintext=1&titles={cim_kodolt}&format=json"
    )
    extract_data = http_get_json(extract_url)
    teljes_bevezeto = summary.get("extract", "").strip()
    if extract_data:
        pages = extract_data.get("query", {}).get("pages", {})
        for _, pdata in pages.items():
            ext = (pdata.get("extract") or "").strip()
            if len(ext) > len(teljes_bevezeto):
                teljes_bevezeto = ext

    mas_cimek = [t["title"] for t in talalatok[1:] if t.get("title")]

    return {
        "forras": f"Wikipédia ({lang.upper()})",
        "cim": summary.get("title", fo_cim),
        "leiras": summary.get("description") or "",
        "szoveg": teljes_bevezeto,
        "kapcsolodo_cimek": mas_cimek,
    }


def keres_duckduckgo_reszletes(kifejezes: str) -> Dict[str, Any]:
    q = urllib.parse.quote(kifejezes)
    url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
    data = http_get_json(url)
    if not data:
        return {"osszefoglalo": None, "kapcsolodo": []}

    kapcsolodo: List[str] = []
    for topic in data.get("RelatedTopics", [])[:5]:
        if isinstance(topic, dict) and topic.get("Text"):
            kapcsolodo.append(topic["Text"].strip())

    return {
        "osszefoglalo": (data.get("AbstractText") or "").strip() or None,
        "kapcsolodo": kapcsolodo,
    }


def keres_a_memoriaban(kulcsszo: str, memoria: List[Dict[str, Any]]) -> List[str]:
    talalatok: List[str] = []
    k_kis = kulcsszo.lower()
    if len(k_kis) < 3:
        return talalatok
    for elem in reversed(memoria[-60:]):
        szoveg = elem.get("user") or elem.get("bot") or ""
        if k_kis in szoveg.lower() and not szoveg.startswith("### "):
            talalatok.append(szoveg[:140])
        if len(talalatok) >= 3:
            break
    return talalatok


def keres_a_deep_workban(kulcsszo: str, feladatok: List[Dict[str, Any]]) -> List[str]:
    talalatok: List[str] = []
    k_kis = kulcsszo.lower()
    for f in reversed(feladatok[-30:]):
        leiras = f.get("leiras", "")
        eredmeny = f.get("eredmeny") or ""
        if k_kis in leiras.lower() or k_kis in eredmeny.lower():
            talalatok.append(f"[{f.get('statusz')}] {leiras}")
    return talalatok


def epits_ok_okozati_vazat(kerdes: str, forras_szovegek: List[str]) -> str:
    egybeszurt = " ".join(forras_szovegek)
    mondatok = [m.strip() for m in re.split(r"(?<=[.!?])\s+", egybeszurt) if len(m.strip()) > 25]

    ok_mondatok = [
        m for m in mondatok
        if re.search(r"\b(mert|miatt|következtében|eredményeként|hatására|okozta|alapján|vezetett)\b", m, re.IGNORECASE)
    ]
    teny_mondatok = mondatok[:3]

    sorok = [f"**Vizsgált kérdés / fókusz:** {kerdes}"]
    if teny_mondatok:
        sorok.append("**Azonosított alap-tények (forrásból):** " + " ".join(teny_mondatok[:2]))
    if ok_mondatok:
        sorok.append("**Kifejezett ok-okozati utalások a forrásokban:** " + ok_mondatok[0])
    else:
        sorok.append(
            "**Ok-okozati megjegyzés:** A fellelt összefoglalók tényeket és összefüggéseket mutatnak, "
            "de önálló, bizonyított ok-okozati láncot nem támasztanak alá kellő részletességgel – nem egészítem ki kitalációval."
        )
    return "\n".join(sorok)


def teljes_atvizsgalas(
    kerdes: str,
    memoria: List[Dict[str, Any]],
    feladatok: List[Dict[str, Any]],
    profil: Dict[str, Any],
) -> Dict[str, Any]:
    kulcsszo = tisztit_keresokifejezest(kerdes)
    ok_okozati_kerdes = bool(
        re.search(r"\b(miért|hogyan|mi az oka|okoz|következmény|hatás|összefüggés)\b", kerdes.lower())
    )

    lepesek: List[str] = [
        f"1. Szándék és fókusz meghatározása: '{kulcsszo}' (ok-okozati fókusz: {'igen' if ok_okozati_kerdes else 'általános'})",
        "2. Hosszú távú memória és Deep-Work háttérfeladatok átvizsgálása",
        "3. Többforrásos lekérdezés: Wikipédia (HU), Wikipédia (EN), DuckDuckGo",
        "4. Tényellenőrzés, ok-okozati váz építése és stílus-illesztés",
    ]

    mem_talalatok = keres_a_memoriaban(kulcsszo, memoria)
    dw_talalatok = keres_a_deep_workban(kulcsszo, feladatok)

    wiki_hu = keres_wikipedia_reszletes(kulcsszo, "hu")
    wiki_en = keres_wikipedia_reszletes(kulcsszo, "en")
    ddg = keres_duckduckgo_reszletes(kulcsszo)

    blokkok: List[str] = []
    nyers_szovegek: List[str] = []

    if wiki_hu:
        nyers_szovegek.append(wiki_hu["szoveg"])
        alcim = f" — *{wiki_hu['leiras']}*" if wiki_hu.get("leiras") else ""
        blokk = f"### {wiki_hu['cim']}{alcim} (Wikipédia HU)\n{wiki_hu['szoveg']}"
        if wiki_hu.get("kapcsolodo_cimek"):
            blokk += "\n\n**Kapcsolódó szócikkek:** " + ", ".join(wiki_hu["kapcsolodo_cimek"])
        blokkok.append(blokk)

    if wiki_en:
        nyers_szovegek.append(wiki_en["szoveg"])
        if not wiki_hu or len(wiki_hu["szoveg"]) < 260:
            alcim_en = f" — *{wiki_en['leiras']}*" if wiki_en.get("leiras") else ""
            blokkok.append(f"### {wiki_en['cim']}{alcim_en} (Wikipédia EN)\n{wiki_en['szoveg']}")

    if ddg.get("osszefoglalo"):
        nyers_szovegek.append(ddg["osszefoglalo"])
        blokkok.append(f"### Gyors összefoglaló (DuckDuckGo)\n{ddg['osszefoglalo']}")

    if ddg.get("kapcsolodo"):
        blokkok.append("### Kapcsolódó témák\n" + "\n".join(f"- {p}" for p in ddg["kapcsolodo"]))

    if ok_okozati_kerdes and nyers_szovegek:
        blokkok.append("### Ok-okozati (Causal) elemzés\n" + epits_ok_okozati_vazat(kerdes, nyers_szovegek))

    if mem_talalatok:
        blokkok.append("### Találatok a memóriában\n" + "\n".join(f"- {m}" for m in mem_talalatok))

    if dw_talalatok:
        blokkok.append("### Kapcsolódó Deep-Work feladatok\n" + "\n".join(f"- {d}" for d in dw_talalatok))

    if not blokkok:
        nev = profil.get("nev") or "Zalán"
        valasz = (
            f"{nev}, átnéztem a memóriát, a Deep-Work feladatokat és a nyílt internetes forrásokat a(z) "
            f"**'{kulcsszo}'** témában, de nem találtam elég megbízható egyezést. "
            "Pontosítsd a nevet, a kifejezést vagy a kérdést, és újra végigmegyek rajta."
        )
        lepesek.append("5. Nem volt elegendő forrás -> őszinte bizonytalanság jelezve.")
    else:
        if profil.get("stilus") == "tömör":
            # Tömör mód: az első érdemi blokk kivonata
            valasz = blokkok[0]
        else:
            valasz = "\n\n".join(blokkok)
        lepesek.append(f"5. Válasz összeállítva {len(blokkok)} átvizsgált blokkból.")

    return {"valasz": valasz, "logikai_lanc": lepesek}


def futtass_deep_work_feladatot(feladat_id: str, leiras: str) -> None:
    # 1. fázis: indítás
    feladatok = betolt_json(HATTER_FAJL, [])
    for item in feladatok:
        if item["id"] == feladat_id:
            item["statusz"] = "1_fazis_tervezes"
            item["lepesek"].append("Feladat lebontása és kulcsszavak azonosítása")
    ment_json(HATTER_FAJL, feladatok)

    # 2. fázis: többfordulós átvizsgálás
    memoria = betolt_json(MEMORIA_FAJL, [])
    profil = betolt_json(PROFIL_FAJL, {"nev": "Zalán", "stilus": "alap"})
    eredmeny = teljes_atvizsgalas(leiras, memoria, feladatok, profil)

    # 3. fázis: lezárás és eredmény mentése
    feladatok = betolt_json(HATTER_FAJL, [])
    for item in feladatok:
        if item["id"] == feladat_id:
            item["statusz"] = "kesz"
            item["befejezve"] = datetime.utcnow().isoformat()
            item["lepesek"].extend(eredmeny["logikai_lanc"])
            item["eredmeny"] = eredmeny["valasz"]
    ment_json(HATTER_FAJL, feladatok)


class AGIKeres(BaseModel):
    uzenet: str
    modul_tipus: Optional[str] = "chat"
    kontextus_adatok: Optional[Dict[str, Any]] = None


class DeepWorkKeres(BaseModel):
    feladat_leiras: str


@app.get("/")
def home():
    memoria = betolt_json(MEMORIA_FAJL, [])
    feladatok = betolt_json(HATTER_FAJL, [])
    profil = betolt_json(PROFIL_FAJL, {"nev": "Zalán", "stilus": "alap"})
    return {
        "status": "Cordwainer Saját Szerver v9.0 aktív",
        "profil": profil,
        "atvizsgalas": "Memória + Deep-Work + Wikipédia HU/EN + DuckDuckGo + Ok-okozati váz",
        "memoria_bejegyzesek": len(memoria),
        "deep_work_feladatok": len(feladatok),
    }


@app.post("/api/chat")
def agi_chat(adat: AGIKeres, engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    uzenet = adat.uzenet.strip()
    kis = uzenet.lower()

    memoria = betolt_json(MEMORIA_FAJL, [])
    feladatok = betolt_json(HATTER_FAJL, [])
    profil = profil_frissitese(uzenet, betolt_json(PROFIL_FAJL, {"nev": "Zalán", "stilus": "alap"}))
    ment_json(PROFIL_FAJL, profil)

    nev = profil.get("nev") or "Zalán"
    memoria.append({"ido": datetime.utcnow().isoformat(), "user": uzenet})

    if any(k in kis for k in ["szia", "helló", "cső", "sziasztok"]):
        valasz_szoveg = f"Szia, {nev}! Átnézem a forrásokat, a memóriát és a háttérfeladatokat is. Miben segíthetek?"
        logikai_lanc = ["1. Üdvözlés felismerve", f"2. Felhasználói profil alkalmazva ({nev})"]
    elif "mi a nevem" in kis:
        valasz_szoveg = f"{nev}."
        logikai_lanc = ["1. Identitás-lekérdezés", "2. Profilból kiolvasva"]
    elif "mit tudsz" in kis and len(kis) < 40:
        valasz_szoveg = (
            f"Szia, {nev}! Saját motorral futok külső AI-kulcs nélkül: átnézem a memóriát és a "
            "Deep-Work feladatokat, keresek a magyar/angol Wikipédián és a DuckDuckGón, ok-okozati "
            "vázat rakok össze a talált tényekből, és háttérfeladatokat is indítok (`/api/deep-work`)."
        )
        logikai_lanc = ["1. Képesség-lekérdezés", "2. Aktív modulok felsorolása"]
    else:
        eredmeny = teljes_atvizsgalas(uzenet, memoria, feladatok, profil)
        valasz_szoveg = eredmeny["valasz"]
        logikai_lanc = eredmeny["logikai_lanc"]

    memoria.append({"ido": datetime.utcnow().isoformat(), "bot": valasz_szoveg})
    ment_json(MEMORIA_FAJL, memoria[-150:])

    return {
        "status": "siker",
        "valasz": valasz_szoveg,
        "logikai_lanc": logikai_lanc,
    }


@app.post("/api/deep-work")
def indit_deep_work(
    adat: DeepWorkKeres,
    background_tasks: BackgroundTasks,
    engedelyezve: bool = Depends(ellenoriz_kulcsot),
):
    feladat_id = f"dw_{int(datetime.utcnow().timestamp())}"
    feladatok = betolt_json(HATTER_FAJL, [])
    uj_feladat = {
        "id": feladat_id,
        "leiras": adat.feladat_leiras,
        "statusz": "ütemezve",
        "letrehozva": datetime.utcnow().isoformat(),
        "lepesek": ["Feladat regisztrálva"],
        "eredmeny": None,
    }
    feladatok.append(uj_feladat)
    ment_json(HATTER_FAJL, feladatok[-60:])

    background_tasks.add_task(futtass_deep_work_feladatot, feladat_id, adat.feladat_leiras)
    return {"status": "deep_work_elinditva", "feladat_id": feladat_id}


@app.get("/api/deep-work")
def listaz_deep_work(engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    return {"feladatok": betolt_json(HATTER_FAJL, [])}


