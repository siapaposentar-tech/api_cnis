# ============================================================
# PARSER CNIS — PROVISÓRIO
# ESCOPO: CNIS CIDADÃO | SEGURADO EMPREGADO
# REGRA-CHAVE: cria vínculo APENAS quando Tipo Vínculo = Empregado
# STATUS: PASSO 1 FINAL — linha tabular como gatilho
# GOVERNANÇA: SUBORDINADO AO P&R CNIS — EMPREGADO
# ============================================================

import re
from typing import List, Dict, Optional

# ------------------------------------------------------------
# REGEX BÁSICOS (tolerantes)
# ------------------------------------------------------------

RE_CPF = re.compile(r"\bCPF\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)
RE_NIT = re.compile(r"\bNIT\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)

# datas
RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_MES_ANO = re.compile(r"\b\d{2}/\d{4}\b")

# remuneração: "MM/AAAA 1.234,56" (valor pode ser negativo)
RE_REMUN = re.compile(r"\b(\d{2}/\d{4})\s+(-?[\d\.\,]+)\b")

# palavra Empregado isolada (valor da coluna Tipo Vínculo)
RE_EMPREGADO = re.compile(r"\bEmpregado\b", re.IGNORECASE)

# possíveis separadores de coluna (CNIS texto bruto)
SEP_COLS = re.compile(r"\s{2,}|\t|\|")

# ------------------------------------------------------------
# UTILITÁRIOS
# ------------------------------------------------------------

def _to_float_ptbr(txt: str) -> Optional[float]:
    try:
        return float(txt.replace(".", "").replace(",", "."))
    except Exception:
        return None

def _split_cols(linha: str) -> List[str]:
    # divide por múltiplos espaços / tabs / pipes
    cols = [c.strip() for c in SEP_COLS.split(linha) if c.strip()]
    return cols

def _find_empregado_col(cols: List[str]) -> bool:
    # verdadeiro se ALGUMA coluna for exatamente/contiver "Empregado"
    for c in cols:
        if RE_EMPREGADO.search(c):
            return True
    return False

def _extract_datas_from_cols(cols: List[str]):
    datas = []
    for c in cols:
        datas.extend(RE_DATA.findall(c))
    data_inicio = datas[0] if len(datas) >= 1 else None
    data_fim = datas[1] if len(datas) >= 2 else None
    return data_inicio, data_fim

def _extract_ultima_remun_from_block(block_lines: List[str]) -> Optional[str]:
    meses = []
    for ln in block_lines:
        meses.extend(RE_MES_ANO.findall(ln))
    return meses[-1] if meses else None

def _extract_indicadores(cols: List[str]) -> List[str]:
    # indicadores costumam aparecer em coluna própria; extrai tokens literais
    out = []
    for c in cols:
        if len(c) <= 6 and c.isupper():
            out.append(c)
    return out

# ------------------------------------------------------------
# PARSER PRINCIPAL
# ------------------------------------------------------------

def parse_cnis(texto: str) -> Dict:
    """
    CNIS CIDADÃO | SEGURADO EMPREGADO
    Regra: cria vínculo APENAS quando linha tabular tiver Tipo Vínculo = Empregado.
    Extração literal, sem inferência.
    """

    resultado = {
        "identificacao": {},
        "vinculos": []
    }

    # --------------------------
    # IDENTIFICAÇÃO
    # --------------------------
    m = RE_CPF.search(texto)
    if m:
        resultado["identificacao"]["cpf"] = m.group(1).strip()

    m = RE_NIT.search(texto)
    if m:
        resultado["identificacao"]["nit"] = m.group(1).strip()

    # --------------------------
    # PROCESSAMENTO TABULAR
    # --------------------------
    linhas = texto.split("\n")

    vinculo_atual = None
    bloco_linhas: List[str] = []

    for linha in linhas:
        ln = linha.rstrip()
        if not ln.strip():
            continue

        cols = _split_cols(ln)

        # --- GATILHO: linha tabular com "Empregado" ---
        if cols and _find_empregado_col(cols):
            # fecha vínculo anterior
            if vinculo_atual:
                # fecha última remuneração pelo bloco acumulado
                vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
                resultado["vinculos"].append(vinculo_atual)

            data_inicio, data_fim = _extract_datas_from_cols(cols)

            vinculo_atual = {
                "tipo_vinculo": "EMPREGADO",
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "ultima_remuneracao": None,
                "matricula": None,
                "indicadores": _extract_indicadores(cols),
                "remuneracoes": []
            }
            bloco_linhas = []
            continue

        # --- COLETA DE REMUNERAÇÕES (somente se já houver vínculo EMPREGADO) ---
        if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
            bloco_linhas.append(ln)
            mrem = RE_REMUN.search(ln)
            if mrem:
                competencia = mrem.group(1)
                valor = _to_float_ptbr(mrem.group(2))
                vinculo_atual["remuneracoes"].append({
                    "competencia": competencia,
                    "valor": valor
                })

    # fecha último vínculo
    if vinculo_atual:
        vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
        resultado["vinculos"].append(vinculo_atual)

    return resultado

# ============================================================
# FIM DO ARQUIVO — parsers/parser_cnis.py
# ============================================================
