import re
from datetime import datetime

# =========================================================
# FUNÇÃO AUXILIAR — GERAR COMPETÊNCIAS ESPERADAS
# =========================================================

def gerar_competencias_esperadas(inicio, fim):
    """
    Gera lista de competências esperadas (MM/YYYY)
    SOMENTE quando as datas estão completas e válidas.

    Regras CNIS CIDADÃO:
    - inicio: dd/mm/aaaa
    - fim: mm/aaaa
    - qualquer inconsistência → retorna lista vazia
    - é proibido inferir ou corrigir datas
    """

    if not inicio or not fim:
        return []

    try:
        data_inicio = datetime.strptime(inicio, "%d/%m/%Y")
    except ValueError:
        return []

    try:
        data_fim = datetime.strptime(fim, "%m/%Y")
    except ValueError:
        # CNIS Cidadão: fim incompleto → não calcular
        return []

    competencias = []
    ano = data_inicio.year
    mes = data_inicio.month

    while (ano < data_fim.year) or (ano == data_fim.year and mes <= data_fim.month):
        competencias.append(f"{mes:02d}/{ano}")
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    return competencias


# =========================================================
# PARSER PRINCIPAL — CNIS CIDADÃO
# =========================================================

def parse_cnis(texto):
    """
    Parser do CNIS Cidadão.
    Extração 100% literal.
    Foco atual: Segurado Empregado.
    """

    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    linhas = texto.split("\n")

    # -----------------------------------------------------
    # IDENTIFICAÇÃO DO FILIADO
    # -----------------------------------------------------

    for linha in linhas:
        if "Nome:" in linha and "Nome da Mãe" not in linha:
            resultado["identificacao"]["nome"] = linha.replace("Nome:", "").strip()

        if "CPF:" in linha:
            cpf = re.search(r"CPF:\s*([\d\.\-]+)", linha)
            if cpf:
                resultado["identificacao"]["cpf"] = cpf.group(1)

        if "NIT:" in linha:
            nit = re.search(r"NIT:\s*([\d\.\-]+)", linha)
            if nit:
                resultado["identificacao"]["nit"] = nit.group(1)

    # -----------------------------------------------------
    # VÍNCULOS — SEGURADO EMPREGADO
    # -----------------------------------------------------

    vinculo_atual = None

    for linha in linhas:

        # Início de vínculo
        if "Origem do Vínculo" in linha and "EMPREGADO" in linha:
            if vinculo_atual:
                resultado["vinculos"].append(vinculo_atual)

            vinculo_atual = {
                "tipo": "EMPREGADO",
                "data_inicio": None,
                "data_fim": None,
                "ultima_remuneracao": None,
                "matricula": None,
                "competencias_encontradas": [],
                "competencias_esperadas": [],
                "competencias_sem_remuneracao": []
            }

        if not vinculo_atual:
            continue

        # Data Início
        if "Data Início:" in linha:
            m = re.search(r"Data Início:\s*(\d{2}/\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["data_inicio"] = m.group(1)

        # Data Fim
        if "Data Fim:" in linha:
            m = re.search(r"Data Fim:\s*(\d{2}/\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["data_fim"] = m.group(1)

        # Última Remuneração
        if "Últ. Remun." in linha:
            m = re.search(r"Últ\. Remun\.\:\s*(\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["ultima_remuneracao"] = m.group(1)

        # Matrícula do Trabalhador
        if "Matrícula do Trabalhador" in linha:
            m = re.search(r"Matrícula do Trabalhador:\s*(\S+)", linha)
            if m:
                valor = m.group(1).strip()
                if valor and not re.match(r"\d{2}/\d{4}", valor):
                    vinculo_atual["matricula"] = valor

        # Competências + Remuneração
        match_comp = re.search(r"(\d{2}/\d{4})\s+([\d\.,]+)", linha)
        if match_comp:
            vinculo_atual["competencias_encontradas"].append(match_comp.group(1))

    # Fecha último vínculo
    if vinculo_atual:
        resultado["vinculos"].append(vinculo_atual)

    # -----------------------------------------------------
    # PROCESSAMENTO FINAL DE COMPETÊNCIAS
    # -----------------------------------------------------

    for v in resultado["vinculos"]:

        inicio = v["data_inicio"]
        fim = None

        # Regra CNIS Cidadão:
        # Data Fim → prioridade
        # Senão → Últ. Remun.
        if v["data_fim"]:
            fim = v["data_fim"][3:]  # dd/mm/aaaa → mm/aaaa
        elif v["ultima_remuneracao"]:
            fim = v["ultima_remuneracao"]

        v["competencias_esperadas"] = gerar_competencias_esperadas(inicio, fim)

        v["competencias_sem_remuneracao"] = [
            c for c in v["competencias_esperadas"]
            if c not in v["competencias_encontradas"]
        ]

    return resultado
