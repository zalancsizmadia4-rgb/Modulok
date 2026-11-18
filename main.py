from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel

app = FastAPI(title="Saját AI Szuper-Szerver", version="1.0")

# A te saját titkos kulcsod, amivel az APK-d kommunikálni fog
SAJAT_TITKOS_KULCS = "sk-a-sajat-bizonsagi-kulcsod-123"

def ellenoriz_kulcsot(authorization: str = Header(None)):
    if not authorization or authorization.replace("Bearer ", "") != SAJAT_TITKOS_KULCS:
        raise HTTPException(status_code=401, detail="Hibás API kulcs!")
    return True

class ChatAdat(BaseModel):
    uzenet: str

@app.get("/")
def home():
    return {"status": "A szerverfut és készen áll a feladatra!"}

@app.post("/api/chat")
def ai_chat(adat: ChatAdat, engedelyezve: bool = Depends(ellenoriz_kulcsot)):
    # Itt fog majd dolgozni a rendszer a te egyedi személyiségeddel
    valasz = f"AI válasz érkezett erre: '{adat.uzenet}'"
    return {
        "status": "siker",
        "valasz": valasz
    }
