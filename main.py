import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel

app = FastAPI(title="Cordwainer AGI Chat Gateway", version="10.0")

# Ez a titkos kulcs védi a szerveredet a Cordwainer app felől
SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"
MEMORIA_FAJL = "hosszutavu_memoria.json"

def betolt_memoria() -> List[Dict[str, str]]:
    if os.path.exists(MEMORIA_FAJL):
        try:
            with open(MEMORIA_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def ment_memoria(elozmenyek: List[Dict[str, str]]):
    # Eltároljuk az utolsó 50 üzenetet a hosszú távú memóriához
    with open(MEMORIA_FAJL, "w", encoding="utf-8") as f:
        json.dump(elozmenyek[-50:], f, ensure_ascii=False, indent=2)

def ellenoriz_kulcsot(authorization: str = Header(None)) -> bool:
    if not authorization or authorization.replace("Bearer ", "").strip() != SAJAT_TITKOS_KULCS:
        raise HTTPException(status_code=401, detail="Hibás szerver kulcs!")
    return True

class ChatKeres(BaseModel):
    uzenet: str
    modul_tipus: Optional[str] = "chat"

@app.get("/")
def home():
    return {
        "status": "Cordwainer AGI Gateway v10.0 aktív",
        "rendszer": "Független, külső API kulcsok nélküli architektúra"
    }

@app.post("/api/chat")
def agi_chat(adat: ChatKeres, engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    uzenet = adat.uzenet.strip()
    
    # Memória kezelés
    elozmenyek = betolt_memoria()
    elozmenyek.append({"role": "user", "content": uzenet})

    # Itt generáljuk le a választ a saját szerver logika alapján
    # (A jövőben itt hívhatjuk meg közvetlenül a Hugging Face modelljeinket is)
    ai_valasz = f"Cordwainer AGI válasz: Megkaptam a parancsot ('{uzenet}'). A rendszer zökkenőmentesen, külső API-k nélkül feldolgozta a kérést."

    # Válasz mentése a memóriába
    elozmenyek.append({"role": "assistant", "content": ai_valasz})
    ment_memoria(elozmenyek)

    return {
        "status": "siker",
        "valasz": ai_valasz,
        "logikai_lanc": [
            "1. Kérés sikeresen beérkezett a Render szerverre",
            "2. Hosszú távú memória frissítve",
            "3. Válasz generálva és visszaküldve a Cordwainer appnak"
        ]
    }
