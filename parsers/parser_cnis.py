# ============================================================
# PARSER CNIS — PROVISÓRIO (EVOLUÇÃO INCREMENTAL)
# ESCOPO: CNIS CIDADÃO | SEGURADO EMPREGADO
# REGRA-CHAVE: cria vínculo APENAS quando Tipo Vínculo = Empregado
# GOVERNANÇA: SUBORDINADO AO P&R CNIS — EMPREGADO
#
# ATUALIZAÇÃO (2026-02-01):
# - Extrair também: Sequencial, Nome da Empresa, Código Emp./NB (CNPJ/CEI/raiz), Origem do Vínculo
# - Correção no momento da detecção: deslocamento de coluna (ex.: matrícula no lugar de Data Fim)
# - Bloqueio de vínculo fantasma (não salva vínculo sem data_inicio e sem identificadores mínimos)
# ============================================================

import re
from typing import List, Dict, Optional, Tuple

# ------------------------------------------------------------
# REGEX BÁSICOS (tolerantes)
# ------------------------------------------------------------

RE_CPF = re.compile(r"\bCPF\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)
RE_NIT = re.compile(r"\bNIT\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)

# NIT dentro de colunas tabulares (ex.: 1.112.798.857-8)
RE_NIT_TOKEN = re.compile(r"\b\d{1,3}\.\d{3}\.\d{3}\.\d{3}\-\d\b")

# datas
RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_MES_ANO = re.compile(r"\b\d{2}/\d{4}\b")

# remuneração: "MM/AAAA 1.234,56" (valor pode ser negativo)
RE_REMUN = re.compile(r"\b(\d{2}/\d{4})\s+(-?[\d\.\,]+)\b")

# palavra Empregado isolada (valor da coluna Tipo Vínculo)
RE_EMPREGADO = re.compile(r"\bEmpregado\b", re.IGNORECASE)

# possíveis separadores de coluna (CNIS texto bruto)
SEP_COLS = re.compile(r"\s{2,}|\t|\|")

# CNPJ / CEI / NB (extração literal)
RE_CNPJ_FORMATADO = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CNPJ_SEM_MASCARA = re.compile(r"\b\d{14}\b")
RE_CEI_FORMATADO = re.compile(r"\b\d{2}\.\d{3}\.\d{5}/\d{2}\b")
RE_CEI_SEM_MASCARA = re.compile(r"\b\d{12}\b")

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
    # verdadeiro se ALGUMA coluna contiver "Empregado"
    for c in cols:
        if RE_EMPREGADO.search(c):
            return True
    return False

def _extract_datas_from_cols(cols: List[str]) -> Tuple[Optional[str], Optional[str]]:
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
        token = c.strip()
        if len(token) <= 10 and token.isupper():
            out.append(token)
    return out

def _extract_codigo_emp(cols: List[str]) -> Optional[str]:
    # Extrai literalmente o primeiro token que pareça CNPJ/CEI (com ou sem máscara)
    for c in cols:
        m = RE_CNPJ_FORMATADO.search(c)
        if m:
            return m.group(0)
        m = RE_CNPJ_SEM_MASCARA.search(c)
        if m:
            return m.group(0)
        m = RE_CEI_FORMATADO.search(c)
        if m:
            return m.group(0)
        m = RE_CEI_SEM_MASCARA.search(c)
        if m:
            return m.group(0)

    # fallback literal: token com bastante dígito e não sendo data/mes-ano
    for c in cols:
        if RE_DATA.search(c) or RE_MES_ANO.search(c):
            continue
        digits = re.sub(r"\D", "", c)
        if len(digits) >= 8 and ("/" in c or "." in c or "-" in c or c.isdigit()):
            return c.strip()

    return None

def _find_nit_index(cols: List[str]) -> Optional[int]:
    for i, c in enumerate(cols):
        if RE_NIT_TOKEN.search(c):
            return i
    return None

def _is_numeric_token(tok: str) -> bool:
    return bool(tok) and tok.strip().isdigit()

def _safe_get(cols: List[str], idx: int) -> Optional[str]:
    if idx < 0 or idx >= len(cols):
        return None
    val = cols[idx].strip()
    return val if val else None

def _extract_nome_empresa(linha_acima: Optional[str], cols_acima: List[str]) -> Optional[str]:
    if not linha_acima:
        return None
    upper = linha_acima.upper()
    # evitar cabeçalhos
    if "SEQUENCIAL" in upper or "CÓD" in upper or "COD" in upper or "ORIGEM" in upper or "TIPO" in upper:
        return None
    if cols_acima and _find_empregado_col(cols_acima):
        return None
    # Opção A: literal
    return linha_acima.strip()

def _should_append_vinculo(v: Dict) -> bool:
    # Bloqueio de vínculo fantasma: precisa ter algo mínimo além do tipo
    if not v:
        return False
    if v.get("tipo_vinculo") != "EMPREGADO":
        return False
    has_min = any([
        v.get("data_inicio"),
        v.get("sequencial"),
        v.get("codigo_emp"),
        v.get("nome_empresa"),
        v.get("nit_vinculo"),
    ])
    return bool(has_min)

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

    prev_line_nonempty: Optional[str] = None
    prev_cols_nonempty: List[str] = []

    for linha in linhas:
        ln = linha.rstrip()
        if not ln.strip():
            continue

        cols = _split_cols(ln)

        # --- GATILHO: linha tabular com "Empregado" ---
        if cols and _find_empregado_col(cols):
            # fecha vínculo anterior
            if vinculo_atual:
                vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
                if _should_append_vinculo(vinculo_atual):
                    resultado["vinculos"].append(vinculo_atual)

            # Campos podem estar visualmente na linha acima (CNIS CIDADÃO)
            merged_cols = prev_cols_nonempty + cols if prev_cols_nonempty else cols

            data_inicio, data_fim = _extract_datas_from_cols(merged_cols)

            nit_idx = _find_nit_index(merged_cols)
            nit_vinculo = _safe_get(merged_cols, nit_idx) if nit_idx is not None else None

            # Sequencial (índice do vínculo) costuma estar imediatamente antes do NIT
            sequencial = None
            if nit_idx is not None and nit_idx - 1 >= 0:
                cand = _safe_get(merged_cols, nit_idx - 1)
                if cand and cand.isdigit():
                    sequencial = cand

            codigo_emp = None
            origem_vinculo = None

            # Se achou NIT, tenta capturar por posição (layout tabular)
            if nit_idx is not None:
                codigo_emp = _safe_get(merged_cols, nit_idx + 1)
                origem_vinculo = _safe_get(merged_cols, nit_idx + 2)

            # Se não encontrou ou veio vazio, tenta por regex (literal)
            if not codigo_emp:
                codigo_emp = _extract_codigo_emp(merged_cols)

            nome_empresa = _extract_nome_empresa(prev_line_nonempty, prev_cols_nonempty)

            # Correção no momento da detecção: matrícula ocupando posição de Data Fim
            matricula = None
            if nit_idx is not None:
                # Ordem esperada após NIT: codigo_emp, origem, data_inicio, data_fim, ult_remun, tipo...
                cand_data_fim = _safe_get(merged_cols, nit_idx + 5)
                if cand_data_fim and (not RE_DATA.search(cand_data_fim)) and _is_numeric_token(cand_data_fim):
                    if not data_fim:
                        matricula = cand_data_fim

            vinculo_atual = {
                "sequencial": sequencial,
                "nit_vinculo": nit_vinculo,
                "nome_empresa": nome_empresa,
                "codigo_emp": codigo_emp,
                "origem_vinculo": origem_vinculo,
                "tipo_vinculo": "EMPREGADO",
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "ultima_remuneracao": None,
                "matricula": matricula,
                "indicadores": _extract_indicadores(cols),
                "remuneracoes": []
            }

            bloco_linhas = []
            prev_line_nonempty = ln
            prev_cols_nonempty = cols
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

        # atualiza anterior
        prev_line_nonempty = ln
        prev_cols_nonempty = cols

    # fecha último vínculo
    if vinculo_atual:
        vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
        if _should_append_vinculo(vinculo_atual):
            resultado["vinculos"].append(vinculo_atual)

    return resultado

# ============================================================
# FIM DO ARQUIVO — parsers/parser_cnis.py
# ============================================================
