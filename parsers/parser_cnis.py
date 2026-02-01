import re
from datetime import datetime

# =====================================================
# PARSER CNIS — CNIS CIDADÃO | SEGURADO EMPREGADO
# =====================================================

REGEX_DATA_COMPLETA = re.compile(r"\d{2}/\d{2}/\d{4}")
REGEX_COMPETENCIA = re.compile(r"(0[1-9]|1[0-2])/\d{4}")
REGEX_NUMERO = re.compile(r"^\d+$")

HEADER_MARKERS = [
    "competência",
    "remuneração",
    "agentes nocivos",
    "indicadores"
]

def is_header_line(linha: str) -> bool:
    return any(h in linha.lower() for h in HEADER_MARKERS)

def extrair_competencias_horizontal(linhas):
    """
    CNIS CIDADÃO | SEGURADO EMPREGADO
    Leitura horizontal das competências:
    esquerda → direita, linha a linha, página a página.
    """
    competencias = []

    for linha in linhas:
        if not linha.strip():
            continue
        if is_header_line(linha):
            continue

        encontrados = [m.group(0) for m in re.finditer(REGEX_COMPETENCIA, linha)]
        for comp in encontrados:
            competencias.append(comp)

    return competencias

def gerar_competencias_esperadas(inicio, fim):
    """
    Gera todas as competências entre duas datas (mm/aaaa).
    """
    competencias = []
    data_inicio = datetime.strptime(inicio, "%m/%Y")
    data_fim = datetime.strptime(fim, "%m/%Y")

    atual = data_inicio
    while atual <= data_fim:
        competencias.append(atual.strftime("%m/%Y"))
        if atual.month == 12:
            atual = atual.replace(year=atual.year + 1, month=1)
        else:
            atual = atual.replace(month=atual.month + 1)

    return competencias

def parse_cnis(texto):
    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    linhas = texto.split("\n")

    # ------------------------------
    # IDENTIFICAÇÃO
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
    # VÍNCULOS
    # ------------------------------
    bloco_atual = None
    linhas_remuneracao = []

    for linha in linhas:
        if re.search(r"Origem do Vínculo|Código Emp", linha, re.IGNORECASE):
            if bloco_atual:
                bloco_atual["competencias_encontradas"] = extrair_competencias_horizontal(linhas_remuneracao)
                resultado["vinculos"].append(bloco_atual)

            bloco_atual = {
                "linha_inicio": linha.strip(),
                "data_inicio": None,
                "data_fim": None,
                "ultima_remuneracao": None,
                "matricula": None,
                "competencias_encontradas": [],
                "competencias_esperadas": [],
                "competencias_sem_remuneracao": []
            }
            linhas_remuneracao = []
            continue

        if bloco_atual:
            # Detecta datas completas
            datas = REGEX_DATA_COMPLETA.findall(linha)
            for d in datas:
                if not bloco_atual["data_inicio"]:
                    bloco_atual["data_inicio"] = d
                elif not bloco_atual["data_fim"]:
                    bloco_atual["data_fim"] = d

            # Detecta última remuneração (mm/aaaa)
            comps = REGEX_COMPETENCIA.findall(linha)
            if comps:
                bloco_atual["ultima_remuneracao"] = comps[-1]

            # Detecta matrícula (número isolado)
            tokens = linha.split()
            for t in tokens:
                if REGEX_NUMERO.match(t):
                    bloco_atual["matricula"] = t

            linhas_remuneracao.append(linha)

    if bloco_atual:
        bloco_atual["competencias_encontradas"] = extrair_competencias_horizontal(linhas_remuneracao)
        resultado["vinculos"].append(bloco_atual)

    # ------------------------------
    # CÁLCULO DE LACUNAS
    # ------------------------------
    for v in resultado["vinculos"]:
        if not v["data_inicio"]:
            continue

        inicio = datetime.strptime(v["data_inicio"], "%d/%m/%Y").strftime("%m/%Y")

        if v["data_fim"]:
            fim = datetime.strptime(v["data_fim"], "%d/%m/%Y").strftime("%m/%Y")
        else:
            fim = v["ultima_remuneracao"]

        if not fim:
            continue

        v["competencias_esperadas"] = gerar_competencias_esperadas(inicio, fim)

        encontradas = set(v["competencias_encontradas"])
        v["competencias_sem_remuneracao"] = [
            c for c in v["competencias_esperadas"] if c not in encontradas
        ]

    return resultado
