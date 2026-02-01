# ============================================================
# PARSER CNIS — PROVISÓRIO
# ESCOPO: CNIS CIDADÃO | SEGURADO EMPREGADO
# STATUS: CORREÇÃO PASSO 1 (v2) — vínculos não dependem de "Empregado" no cabeçalho
# GOVERNANÇA: SUBORDINADO AO P&R CNIS — EMPREGADO
# ============================================================

import re

# ------------------------------------------------------------
# PADRÕES REGEX (tolerantes a acento e variações)
# ------------------------------------------------------------

PADRAO_DATA_COMPLETA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
PADRAO_MES_ANO = re.compile(r"\b\d{2}/\d{4}\b")

# remuneração: "MM/AAAA 1.234,56" (em qualquer parte da linha)
PADRAO_REMUNERACAO = re.compile(r"(\d{2}/\d{4})\s+(-?[\d\.\,]+)")

# campos de identificação (tolerantes)
PADRAO_NIT = re.compile(r"\bNIT\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)
PADRAO_CPF = re.compile(r"\bCPF\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)

# tipo vínculo (tolerante)
PADRAO_TIPO_VINCULO_EMPREGADO = re.compile(r"\bTipo\s+V[ií]nculo\b.*\bEmpregado\b", re.IGNORECASE)

# ------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------------------------------------

def _to_float_ptbr(valor_txt: str) -> float:
    # mantém literal numérica, mas converte para float pt-br
    return float(valor_txt.replace(".", "").replace(",", "."))

def _eh_inicio_vinculo(linha: str) -> bool:
    # aceita com/sem acento e pequenas variações
    l = linha.lower()
    return ("origem do vínculo" in l) or ("origem do vinculo" in l) or ("código emp" in l) or ("codigo emp" in l)

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

    # --------------------------
    # IDENTIFICAÇÃO (literal)
    # --------------------------
    m_nit = PADRAO_NIT.search(texto)
    if m_nit:
        resultado["identificacao"]["nit"] = m_nit.group(1).strip()

    m_cpf = PADRAO_CPF.search(texto)
    if m_cpf:
        resultado["identificacao"]["cpf"] = m_cpf.group(1).strip()

    # --------------------------
    # VÍNCULOS
    # --------------------------
    linhas = texto.split("\n")
    vinculo_atual = None

    for linha in linhas:
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue

        # --- início do vínculo (cabeçalho) ---
        if _eh_inicio_vinculo(linha_limpa):
            # fecha o vínculo anterior SOMENTE se for EMPREGADO
            if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
                resultado["vinculos"].append(vinculo_atual)

            data_inicio, data_fim, ultima_remun = _extrair_datas_e_ultima_remun(linha_limpa)

            # cria vínculo "pendente": tipo ainda pode aparecer em linhas seguintes
            vinculo_atual = {
                "tipo_vinculo": None,  # será preenchido quando encontrarmos "Tipo Vínculo: Empregado"
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "ultima_remuneracao": ultima_remun,
                "matricula": None,
                "indicadores": _extrair_indicadores(linha_limpa),
                "remuneracoes": []
            }
            continue

        # se não há vínculo atual, ignora
        if not vinculo_atual:
            continue

        # --- detectar tipo vínculo em linhas seguintes ---
        if vinculo_atual.get("tipo_vinculo") is None:
            if PADRAO_TIPO_VINCULO_EMPREGADO.search(linha_limpa):
                vinculo_atual["tipo_vinculo"] = "EMPREGADO"
                continue

        # --- remunerações (só coleta se for EMPREGADO) ---
        if vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
            match = PADRAO_REMUNERACAO.search(linha_limpa)
            if match:
                competencia = match.group(1)
                valor_txt = match.group(2)

                # pelo P&R: valor negativo deve ser extraído (não bloquear)
                # aqui só armazenamos o valor numérico; marcações vêm depois
                try:
                    valor = _to_float_ptbr(valor_txt)
                except Exception:
                    # se der erro de conversão, mantém como None (literal sem inferência)
                    valor = None

                vinculo_atual["remuneracoes"].append({
                    "competencia": competencia,
                    "valor": valor
                })

    # fecha o último vínculo SOMENTE se for EMPREGADO
    if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
        resultado["vinculos"].append(vinculo_atual)

    return resultado

# ============================================================
# FIM DO ARQUIVO — parsers/parser_cnis.py
# ============================================================
