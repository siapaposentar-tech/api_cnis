import re

# ==============================
# PARSER CNIS — BASE INCREMENTAL
# CNIS CIDADÃO | SEGURADO EMPREGADO
# ==============================

COMP_REGEX = re.compile(r"(0[1-9]|1[0-2])/\d{4}")

HEADER_MARKERS = [
    "competência",
    "remuneração",
    "agentes nocivos",
    "indicadores"
]

def is_header_line(linha: str) -> bool:
    texto = linha.lower()
    return any(m in texto for m in HEADER_MARKERS)

def extrair_competencias_horizontal(linhas):
    """
    Leitura HORIZONTAL das competências:
    - esquerda → direita
    - até 3 por linha
    - continua linha a linha e página a página
    - ignora cabeçalhos repetidos
    - NÃO cria lacuna por branco visual
    """
    competencias = []

    for linha in linhas:
        if not linha.strip():
            continue

        if is_header_line(linha):
            continue

        encontrados = [m.group(0) for m in re.finditer(COMP_REGEX, linha)]

        for comp in encontrados:
            competencias.append(comp)

    return competencias

def parse_cnis(texto):
    """
    Parser CNIS Cidadão.
    Extração literal e incremental.
    """

    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    linhas = texto.split("\n")

    # ------------------------------
    # IDENTIFICAÇÃO DO SEGURADO
    # ------------------------------

    nome = re.search(r"Nome:\s*(.*)", texto)
    if nome:
        resultado["identificacao"]["nome"] = nome.group(1).strip()

    cpf = re.search(r"CPF:\s*([\d\.\-]+)", texto)
    if cpf:
        resultado["identificacao"]["cpf"] = cpf.group(1).strip()

    nit = re.search(r"NIT:\s*([\d\.\-]+)", texto)
    if nit:
        resultado["identificacao"]["nit"] = nit.group(1).strip()

    # ------------------------------
    # VÍNCULOS E REMUNERAÇÕES
    # ------------------------------

    bloco_atual = None
    linhas_remuneracao = []

    for linha in linhas:
        # Detecta início de vínculo
        if re.search(r"Origem do Vínculo|Código Emp\.", linha, re.IGNORECASE):
            if bloco_atual:
                bloco_atual["competencias"] = extrair_competencias_horizontal(linhas_remuneracao)
                resultado["vinculos"].append(bloco_atual)

            bloco_atual = {
                "linha_inicio": linha.strip(),
                "competencias": []
            }
            linhas_remuneracao = []
            continue

        if bloco_atual is not None:
            linhas_remuneracao.append(linha)

    if bloco_atual:
        bloco_atual["competencias"] = extrair_competencias_horizontal(linhas_remuneracao)
        resultado["vinculos"].append(bloco_atual)

    return resultado
