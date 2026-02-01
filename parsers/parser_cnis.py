import re
from datetime import datetime

# =========================================================
# FUNÇÃO AUXILIAR
# =========================================================

def gerar_competencias_esperadas(inicio, fim):
    """
    Gera competências esperadas (MM/YYYY) somente
    quando as datas são completas e válidas.

    Regras CNIS CIDADÃO – SEGURADO EMPREGADO:
    - inicio: dd/mm/aaaa
    - fim: mm/aaaa
    - qualquer inconsistência → lista vazia
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
# ESCOPO ATUAL: SEGURADO EMPREGADO
# =========================================================

def parse_cnis(texto):
    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    linhas = [l.strip() for l in texto.split("\n") if l.strip()]

    # -----------------------------------------------------
    # IDENTIFICAÇÃO
    # -----------------------------------------------------

    for linha in linhas:
        if linha.startswith("Nome:"):
            resultado["identificacao"]["nome"] = linha.replace("Nome:", "").strip()

        if "CPF:" in linha:
            m = re.search(r"CPF:\s*([\d\.\-]+)", linha)
            if m:
                resultado["identificacao"]["cpf"] = m.group(1)

        if "NIT:" in linha or "Nit:" in linha:
            m = re.search(r"(NIT|Nit):\s*([\d\.\-]+)", linha)
            if m:
                resultado["identificacao"]["nit"] = m.group(2)

    # -----------------------------------------------------
    # VÍNCULOS — SOMENTE EMPREGADO
    # -----------------------------------------------------

    vinculo_atual = None
    dentro_relacoes = False
    aguardando_tipo = False

    for linha in linhas:

        # Entrada no bloco de relações previdenciárias
        if "Relações Previdenciárias" in linha:
            dentro_relacoes = True
            continue

        if not dentro_relacoes:
            continue

        # Detecta campo Tipo Vínculo
        if "Tipo Vínculo" in linha:
            aguardando_tipo = True
            continue

        # Valor do Tipo Vínculo
        if aguardando_tipo:
            aguardando_tipo = False

            if "Empregado" in linha:
                # Fecha vínculo anterior
                if vinculo_atual:
                    resultado["vinculos"].append(vinculo_atual)

                # Abre novo vínculo EMPREGADO
                vinculo_atual = {
                    "tipo_vinculo": "EMPREGADO",
                    "data_inicio": None,
                    "data_fim": None,
                    "ultima_remuneracao": None,
                    "matricula": None,
                    "competencias_encontradas": [],
                    "competencias_esperadas": [],
                    "competencias_sem_remuneracao": []
                }
            else:
                # Outros vínculos ignorados por enquanto
                vinculo_atual = None

            continue

        if not vinculo_atual:
            continue

        # Data Início
        if "Data Início:" in linha:
            m = re.search(r"(\d{2}/\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["data_inicio"] = m.group(1)

        # Data Fim
        if "Data Fim:" in linha:
            m = re.search(r"(\d{2}/\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["data_fim"] = m.group(1)

        # Última Remuneração
        if "Últ. Remun." in linha:
            m = re.search(r"(\d{2}/\d{4})", linha)
            if m:
                vinculo_atual["ultima_remuneracao"] = m.group(1)

        # Matrícula do Trabalhador
        if "Matrícula do Trabalhador" in linha:
            m = re.search(r":\s*(\S+)", linha)
            if m:
                valor = m.group(1)
                if not re.match(r"\d{2}/\d{4}", valor):
                    vinculo_atual["matricula"] = valor

        # Competências (MM/YYYY)
        m = re.search(r"(\d{2}/\d{4})\s+([\d\.,]+)", linha)
        if m:
            vinculo_atual["competencias_encontradas"].append(m.group(1))

    # Fecha último vínculo
    if vinculo_atual:
        resultado["vinculos"].append(vinculo_atual)

    # -----------------------------------------------------
    # PÓS-PROCESSAMENTO
    # -----------------------------------------------------

    for v in resultado["vinculos"]:
        inicio = v["data_inicio"]
        fim = None

        if v["data_fim"]:
            fim = v["data_fim"][3:]
        elif v["ultima_remuneracao"]:
            fim = v["ultima_remuneracao"]

        v["competencias_esperadas"] = gerar_competencias_esperadas(inicio, fim)
        v["competencias_sem_remuneracao"] = [
            c for c in v["competencias_esperadas"]
            if c not in v["competencias_encontradas"]
        ]

    return resultado
