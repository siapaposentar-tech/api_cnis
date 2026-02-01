# ============================================================
# PARSER CNIS — PROVISÓRIO
# ESCOPO: CNIS CIDADÃO | SEGURADO EMPREGADO
# STATUS: FUNCIONAL — PASSO 1 APLICADO
# GOVERNANÇA: SUBORDINADO AO P&R CNIS — EMPREGADO
# ============================================================

import re

# ------------------------------------------------------------
# PADRÕES REGEX
# ------------------------------------------------------------

PADRAO_DATA_COMPLETA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
PADRAO_MES_ANO = re.compile(r"\b\d{2}/\d{4}\b")
PADRAO_REMUNERACAO = re.compile(r"(\d{2}/\d{4})\s+([\d\.\,]+)")

# ------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------------------------------------

def _to_float_ptbr(valor_txt: str) -> float:
    return float(valor_txt.replace(".", "").replace(",", "."))

def _eh_inicio_vinculo(linha: str) -> bool:
    return bool(
        re.search(r"Origem do Vínculo", linha, re.IGNORECASE)
        or re.search(r"C[oó]digo\s+Emp", linha, re.IGNORECASE)
    )

def _extrair_tipo_vinculo(linha: str):
    if re.search(r"\bEmpregado\b", linha, re.IGNORECASE):
        return "EMPREGADO"
    return None

def _extrair_indicadores(linha: str) -> list:
    m = re.search(r"Indicadores\s*:\s*(.*)", linha, re.IGNORECASE)
    if not m:
        return []
    bruto = m.group(1).strip()
    if not bruto:
        return []
    return [i for i in re.split(r"[\s,;]+", bruto) if i]

def _extrair_datas_e_ultima_remun(linha: str):
    datas = PADRAO_DATA_COMPLETA.findall(linha)
    data_inicio = datas[0] if len(datas) >= 1 else None
    data_fim = datas[1] if len(datas) >= 2 else None

    meses_anos = PADRAO_MES_ANO.findall(linha)
    ultima_remun = meses_anos[-1] if meses_anos else None

    return data_inicio, data_fim, ultima_remun

# ------------------------------------------------------------
# FUNÇÃO PRINCIPAL
# ------------------------------------------------------------

def parse_cnis(texto: str) -> dict:
    """
    Parser CNIS — CNIS CIDADÃO | SEGURADO EMPREGADO
    Extração literal, sem inferência.
    """

    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    # --------------------------------------------------------
    # IDENTIFICAÇÃO BÁSICA
    # --------------------------------------------------------

    nit = re.search(r"NIT:\s*([\d\.\-]+)", texto)
    if nit:
        resultado["identificacao"]["nit"] = nit.group(1).strip()

    cpf = re.search(r"CPF:\s*([\d\.\-]+)", texto)
    if cpf:
        resultado["identificacao"]["cpf"] = cpf.group(1).strip()

    # --------------------------------------------------------
    # PROCESSAMENTO DE VÍNCULOS
    # --------------------------------------------------------

    linhas = texto.split("\n")
    vinculo_atual = None

    for linha in linhas:

        # ---------------- INÍCIO DE VÍNCULO -----------------
        if _eh_inicio_vinculo(linha):

            if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
                resultado["vinculos"].append(vinculo_atual)

            data_inicio, data_fim, ultima_remun = _extrair_datas_e_ultima_remun(linha)

            vinculo_atual = {
                "tipo_vinculo": _extrair_tipo_vinculo(linha),
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "ultima_remuneracao": ultima_remun,
                "matricula": None,
                "indicadores": _extrair_indicadores(linha),
                "remuneracoes": []
            }
            continue

        # ---------------- REMUNERAÇÕES -----------------
        if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
            match = PADRAO_REMUNERACAO.search(linha)
            if match:
                vinculo_atual["remuneracoes"].append({
                    "competencia": match.group(1),
                    "valor": _to_float_ptbr(match.group(2))
                })

    # --------------------------------------------------------
    # FECHAMENTO DO ÚLTIMO VÍNCULO
    # --------------------------------------------------------

    if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
        resultado["vinculos"].append(vinculo_atual)

    return resultado

# ============================================================
# FIM DO ARQUIVO — parsers/parser_cnis.py
# ============================================================
