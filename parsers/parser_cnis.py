import re

def parse_cnis(texto):
    """
    Parser inicial do CNIS.
    Este parser identifica campos básicos e separa blocos de vínculos.
    Ele será evoluído com Ronaldo conforme forem enviados novos modelos.
    """

    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    linhas = texto.split("\n")

    # ------------------------------
    # CAPTURA DE CAMPOS BÁSICOS
    # ------------------------------

    # Nome
    nome = re.search(r"Nome:\s*(.*)", texto)
    if nome:
        resultado["identificacao"]["nome"] = nome.group(1).strip()

    # CPF
    cpf = re.search(r"CPF:\s*([\d\.\-]+)", texto)
    if cpf:
        resultado["identificacao"]["cpf"] = cpf.group(1).strip()

    # NIT
    nit = re.search(r"NIT:\s*([\d\.\-]+)", texto)
    if nit:
        resultado["identificacao"]["nit"] = nit.group(1).strip()

    # ------------------------------
    # SEPARAÇÃO DE VÍNCULOS
    # ------------------------------

    bloco_atual = None

    for linha in linhas:
        # Detecta início de um vínculo
        if re.search(r"Origem do Vínculo|Código Emp\.", linha, re.IGNORECASE):
            if bloco_atual:
                resultado["vinculos"].append(bloco_atual)
            bloco_atual = {"linha_inicio": linha, "remuneracoes": []}

        # Captura remunerações simples
        if bloco_atual:
            match_rem = re.search(r"(\d{2}/\d{4})\s+([\d\.\,]+)", linha)
            if match_rem:
                competencia = match_rem.group(1)
                remun = match_rem.group(2).replace(".", "").replace(",", ".")
                bloco_atual["remuneracoes"].append({
                    "competencia": competencia,
                    "valor": float(remun)
                })

    if bloco_atual:
        resultado["vinculos"].append(bloco_atual)

    return resultado

