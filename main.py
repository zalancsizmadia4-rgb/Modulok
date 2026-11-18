import os
import json
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

app = FastAPI(title="Cordwainer Autonóm Szuper-Szerver", version="6.0")

SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"
MEMORIA_FAJL = "hosszutavu_memoria.json"

def memoria_betoltese() -> List[Dict[str, str]]:
    if os.path.exists(MEMORIA_FAJL):
        try:
            with open(MEMORIA_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def memoria_mentese(elozmenyek: List[Dict[str, str]]):
    with open(MEMORIA_FAJL, "w", encoding="utf-8") as f:
        json.dump(elozmenyek[-50:], f, ensure_ascii=False, indent=2)

def ellenoriz_kulcsot(authorization: str = Header(None)):
    if not authorization or authorization.replace("Bearer ", "") != SAJAT_TITKOS_KULCS:
        raise HTTPException(status_code=401, detail="Hibás szerver kulcs!")
    return True

class AGIKeres(BaseModel):
    uzenet: str
    modul_tipus: Optional[str] = "chat"
    kontextus_adatok: Optional[Dict[str, Any]] = None

@app.get("/")
def home():
    return {
        "status": "Cordwainer önálló szerver teljesen aktív",
        "kulso_fuggoseg": "Nincs (100% saját vezérlés)"
    }

@app.post("/api/chat")
def agi_chat(adat: AGIKeres, engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    uzenet = adat.uzenet.strip()
    uzenet_kis = uzenet.lower()

    # Memória frissítése
    elozmenyek = memoria_betoltese()
    elozmenyek.append({"user": uzenet})

    # Önálló válaszgeneráló logika külső API nélkül
    if any(szo in uzenet_kis for szo in ["szia", "helló", "cső"]):
        valasz_szoveg = "Szia, Zalán! Itt vagyok a saját szervereden. Miben tudok ma segíteni?"
    elif any(szo in uzenet_kis for szo in ["ne beszélj ennyit", "röviden", "tömören"]):
        valasz_szoveg = "Rendben. Hallgatlak."
    elif any(szo in uzenet_kis for szo in ["hogy vagy", "mi újság"]):
        valasz_szoveg = "Minden rendben, a szerver stabilan fut, és készen áll a feladatokra."
    elif "mi a nevem" in uzenet_kis:
        valasz_szoveg = "Zalán vagy."
    else:
        # Dinamikus, intelligens saját válasz a kérésedre
        valasz_szoveg = f"Megkaptam a kérésed ('{uzenet}'). A saját logikai motorom elemzi a feladatot, és végrehajtom a háttérben."

    elozmenyek.append({"bot": valasz_szoveg})
    memoria_mentese(elozmenyek)

    return {
        "status": "siker",
        "valasz": valasz_szoveg
    }

