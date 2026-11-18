import os
import json
from typing import Optional, List, Dict
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from huggingface_hub import InferenceClient

app = FastAPI(title="Cordwainer AGI Core Gateway", version="11.0")

# Biztonsági kulcs a saját Android appod és a szerver közé
SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"
MEMORIA_FAJL = "hosszutavu_memoria.json"

# Itt állítjuk be a valódi, nyílt forráskódú Hugging Face modellt (pl. Mistral vagy Llama)
# Ehhez szükség van egy ingyenes Hugging Face Tokenre a Render Environment Variables közé (HF_TOKEN néven)
HF_TOKEN = os.getenv("HF_TOKEN", "ide_johet_a_hf_tokened_ha_nincs_kornyezeti_valtozo")
MODELL_NEV = "mistralai/Mistral-7B-Instruct-v0.2" # Vagy bármilyen más nyílt forráskódú modell

client = InferenceClient(model=MODELL_NEV, token=HF_TOKEN)

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

class ChatKeres(BaseModel):
    uzenet: str
    modul_tipus: Optional[str] = "chat"

@app.get("/")
def home():
    return {
        "status": "Cordwainer AGI Core v11.0 aktív",
        "modell": MODELL_NEV,
        "architektura": "Valódi Hugging Face nyílt forráskódú AI backend"
    }

@app.post("/api/chat")
def agi_chat(adat: ChatKeres, authorization: str = Header(None)):
    if not authorization or authorization.replace("Bearer ", "").strip() != SAJAT_TITKOS_KULCS:
        raise HTTPException(status_code=401, detail="Hibás szerver kulcs!")
        
    uzenet = adat.uzenet.strip()
    
    # Memória betöltése
    elozmenyek = betolt_memoria()
    elozmenyek.append({"role": "user", "content": uzenet})

    try:
        # Valódi nyílt forráskódú modell hívása a Hugging Face-en keresztül
        formatalt_prompt = f"[INST] {uzenet} [/INST]"
        response = client.text_generation(
            formatalt_prompt,
            max_new_tokens=500,
            temperature=0.7,
            return_full_text=False
        )
        ai_valasz = response.strip()
    except Exception as e:
        ai_valasz = f"Hiba a nyílt modell feldolgozása közben: {str(e)}"

    # Válasz mentése a memóriába
    elozmenyek.append({"role": "assistant", "content": ai_valasz})
    ment_memoria(elozmenyek)

    return {
        "status": "siker",
        "valasz": ai_valasz,
        "modell_forras": MODELL_NEV,
        "logikai_lanc": [
            "1. Kérés beérkezett a Render szerverre",
            "2. Hosszú távú memória frissítve",
            f"3. Nyílt forráskódú modell ({MODELL_NEV}) lefuttatva",
            "4. Válasz visszaküldve a Cordwainer appnak"
        ]
    }
