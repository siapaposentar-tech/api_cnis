from fastapi import FastAPI
from pydantic import BaseModel
from parsers.parser_cnis import parse_cnis

app = FastAPI(
    title="API CNIS – SIAP",
    description="API de extração de CNIS (Cidadão e Extrato Previdenciário) do projeto SIAP.",
    version="1.0.0"
)

# Modelo para receber o texto do CNIS
class CNISInput(BaseModel):
    texto: str

# Rota simples para testar funcionamento
@app.get("/")
def home():
    return {"status": "ok", "mensagem": "API CNIS está funcionando."}

# Rota oficial de processamento
@app.post("/processar_cnis")
def processar_cnis(dados: CNISInput):
    resultado = parse_cnis(dados.texto)
    return {"status": "sucesso", "resultado": resultado}
