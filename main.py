from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import pdfplumber

from parsers.parser_cnis import parse_cnis

app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "ok", "mensagem": "API CNIS está funcionando."}


@app.post("/processar_cnis")
async def processar_cnis_pdf(file: UploadFile = File(...)):
    """
    Endpoint para receber PDF do CNIS Cidadão
    Extrai texto preservando quebras de linha
    e envia para o parser.
    """

    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"erro": "Envie um arquivo PDF"}
        )

    texto_extraido = ""

    with pdfplumber.open(file.file) as pdf:
        for pagina in pdf.pages:
            texto_pagina = pagina.extract_text()
            if texto_pagina:
                texto_extraido += texto_pagina + "\n"

    if not texto_extraido.strip():
        return JSONResponse(
            status_code=400,
            content={"erro": "Não foi possível extrair texto do PDF"}
        )

    resultado = parse_cnis(texto_extraido)

    return {
        "status": "sucesso",
        "resultado": resultado
    }
