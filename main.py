import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel

app = FastAPI(title="Cordwainer AGI Chat Gateway", version="10.0")

SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"
MEMORIA_FAJL = "hosszutavu_memoria.json"

# Ezt a Render Environment Variables alatt add meg: HF_SPACE_URL
# Pl: https://a-sajat-neved-cordwainer-ai.hf.space/api/generate
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "")

def betolt_memoria() -> List[Dict[str, str]]:
    if os.path.exists(MEMORIA_FAJL):
        try:
            with open(MEMORIA_FAJL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def ment_memoria(elozmenyek: List[Dict[str, str]]):
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
        "status": "Cordwainer Chat Gateway v10.0 aktív",
        "hf_space_kapcsolat": bool(HF_SPACE_URL)
    }

@app.post("/api/chat")
def agi_chat(adat: ChatKeres, engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    uzenet = adat.uzenet.strip()
    
    if not HF_SPACE_URL:
        return {
            "status": "hiba",
            "valasz": "A Render szerveren még nincs beállítva a HF_SPACE_URL környezeti változó!"
        }

    # Memória betöltése és frissítése
    elozmenyek = betolt_memoria()
    elozmenyek.append({"role": "user", "content": uzenet})

    # Küldés a saját Hugging Face Space AI motorunknak
    payload = {
        "uzenet": uzenet,
        "elozmenyek": elozmenyek[-10:] # Az utolsó 10 üzenet kontextusként
    }

    req = urllib.request.Request(
        HF_SPACE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            valasz_adat = json.loads(resp.read().decode("utf-8"))
            ai_valasz = valasz_adat.get("valasz", "Nincs válasz az AI motortól.")
            
            # Válasz mentése a memóriába
            elozmenyek.append({"role": "assistant", "content": ai_valasz})
            ment_memoria(elozmenyek)
            
            return {
                "status": "siker",
                "valasz": ai_valasz,
                "logikai_lanc": ["1. Üzenet fogadva Renderen", "2. Továbbítva a Hugging Face Space AI motornak", "3. Válasz integrálva és mentve"]
            }
    except Exception as e:
        return {
            "status": "hiba",
            "valasz": f"Hiba a saját AI motor elérésében: {str(e)}"
        }



