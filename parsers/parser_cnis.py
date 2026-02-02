# ============================================================
# PARSER CNIS — parsers/parser_cnis.py
# ESCOPO: CNIS CIDADÃO | SEGURADO EMPREGADO
# REGRA-CHAVE: cria vínculo APENAS quando a linha do vínculo
#              contém "Empregado" + data DD/MM/AAAA e inicia
#              com SEQUENCIAL numérico.
# EXTRAÇÃO: literal, sem inferência fora do escopo.
# ============================================================

import re
from typing import List, Dict, Optional, Tuple

# ------------------------------------------------------------
# REGEX BÁSICOS
# ------------------------------------------------------------

RE_CPF = re.compile(r"\bCPF\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)
RE_NIT_ID = re.compile(r"\bNIT\b\s*[:\-]?\s*([\d\.\-]+)", re.IGNORECASE)

# NIT em formato usual do CNIS (ex.: 1.112.798.857-8)
RE_NIT_VAL = re.compile(r"\b\d\.\d{3}\.\d{3}\.\d{3}-\d\b")

# datas
RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_MES_ANO = re.compile(r"\b\d{2}/\d{4}\b")

# remuneração: "MM/AAAA 1.234,56" (valor pode ser negativo)
RE_REMUN = re.compile(r"\b(\d{2}/\d{4})\s+(-?[\d\.\,]+)\b")

# palavra Empregado (token)
RE_EMPREGADO_TOKEN = re.compile(r"\bEmpregado\b", re.IGNORECASE)

# CNPJ (padrão clássico)
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")

# CEI / outros códigos possíveis (heurística conservadora)
# (mantemos simples: sequências com muitos dígitos e separadores comuns)
RE_CODIGO_EMP_ALT = re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d{2}-\d\b|\b\d{11,14}\b")

# sequencial no início da linha
RE_SEQ_INICIO = re.compile(r"^\s*(\d{1,4})\s+")

# indicadores (tokens em maiúsculo, com números/underscore)
RE_IND_TOKENS = re.compile(r"\b[A-Z][A-Z0-9_]{1,15}\b")

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
    cols = [c.strip() for c in SEP_COLS.split(linha) if c.strip()]
    return cols

def _is_likely_vinculo_line(raw_line: str) -> bool:
    """
    Linha de vínculo válida (para CRIAR vínculo):
    - começa com sequencial numérico
    - contém token Empregado
    - contém pelo menos 1 data DD/MM/AAAA (início)
    """
    if not RE_SEQ_INICIO.search(raw_line):
        return False
    if not RE_EMPREGADO_TOKEN.search(raw_line):
        return False
    if not RE_DATA.search(raw_line):
        return False
    # proteção: evita cabeçalhos tipo "Indicador Descrição" etc
    if "Indicador" in raw_line and "Descrição" in raw_line:
        return False
    return True

def _extract_datas_from_line(line: str) -> Tuple[Optional[str], Optional[str], int, int]:
    """
    Retorna:
    data_inicio, data_fim, idx_inicio_data1, idx_fim_ultima_data
    """
    datas = list(RE_DATA.finditer(line))
    if not datas:
        return None, None, -1, -1
    data_inicio = datas[0].group(0)
    data_fim = datas[1].group(0) if len(datas) >= 2 else None
    idx_inicio_data1 = datas[0].start()
    idx_fim_ultima_data = datas[-1].end()
    return data_inicio, data_fim, idx_inicio_data1, idx_fim_ultima_data

def _extract_nit_and_codigo_and_empresa(line: str, idx_inicio_data: int) -> Tuple[Optional[int], Optional[str], Optional[str], Optional[str]]:
    """
    Regra fixada pelo Ronaldo:
    - Nome da empresa está SEMPRE entre o CNPJ/CEI e a Data de Início.
    Extraímos:
    - sequencial (int)
    - nit_vinculo (str) = NIT limpo encontrado na linha
    - codigo_emp (str) = CNPJ/CEI
    - nome_empresa (str) = trecho restante antes da data
    """
    raw = line.strip()

    # sequencial
    mseq = RE_SEQ_INICIO.search(raw)
    sequencial = int(mseq.group(1)) if mseq else None

    # pega somente a parte antes da primeira data (onde ficam seq/nit/codigo/nome)
    pre = raw[:idx_inicio_data].strip()

    # remove sequencial do começo
    if mseq:
        pre = pre[mseq.end():].strip()

    # NIT do vínculo (primeiro NIT que aparecer)
    nit_vinculo = None
    mnit = RE_NIT_VAL.search(pre)
    if mnit:
        nit_vinculo = mnit.group(0)
        pre = (pre[:mnit.start()] + " " + pre[mnit.end():]).strip()

    # código do empregador (prioriza CNPJ)
    codigo_emp = None
    mc = RE_CNPJ.search(pre)
    if mc:
        codigo_emp = mc.group(0)
        pre = (pre[:mc.start()] + " " + pre[mc.end():]).strip()
    else:
        # tenta CEI/alternativos, mas só se houver algo com cara de código
        mc2 = RE_CODIGO_EMP_ALT.search(pre)
        if mc2:
            codigo_emp = mc2.group(0)
            pre = (pre[:mc2.start()] + " " + pre[mc2.end():]).strip()

    # o que sobra é o nome da empresa (regra: fica entre codigo e data)
    nome_empresa = pre.strip() if pre.strip() else None

    return sequencial, nit_vinculo, codigo_emp, nome_empresa

def _extract_matricula_and_indicadores(line: str, idx_fim_ultima_data: int) -> Tuple[Optional[str], List[str], Optional[str]]:
    """
    Após a(s) data(s), antes/apos "Empregado" podem existir:
    - matrícula / código interno (ex.: 3062691, KRTC006S016336)
    - última remuneração (MM/AAAA) às vezes aparece na linha do vínculo
    - indicadores (AVRC, PEXT, PRPPS, IEAN...)
    """
    matricula = None
    ultima_remun_linha = None

    # encontra posição de "Empregado"
    memp = RE_EMPREGADO_TOKEN.search(line)
    if not memp:
        return None, [], None

    # trecho entre o fim da última data e a palavra Empregado
    mid = line[idx_fim_ultima_data:memp.start()].strip()

    # se existir MM/AAAA aqui, pode ser última remuneração
    meses = RE_MES_ANO.findall(mid)
    if meses:
        ultima_remun_linha = meses[-1]

    # tenta extrair matrícula: primeiro token "forte" que não seja MM/AAAA
    # (aceita alfanumérico com tamanho >= 4)
    tokens = [t for t in re.split(r"\s+", mid) if t.strip()]
    for t in tokens:
        if RE_MES_ANO.fullmatch(t):
            continue
        if re.fullmatch(r"[A-Za-z0-9\-_/]{4,40}", t):
            matricula = t
            break

    # indicadores: tudo depois de "Empregado"
    after = line[memp.end():]
    inds = []
    for tok in RE_IND_TOKENS.findall(after):
        # evita incluir palavras comuns que não são indicadores
        if tok.upper() in ("CPF", "NIT"):
            continue
        inds.append(tok)

    # remove duplicados preservando ordem
    seen = set()
    indicadores = []
    for i in inds:
        if i not in seen:
            seen.add(i)
            indicadores.append(i)

    return matricula, indicadores, ultima_remun_linha

def _extract_ultima_remun_from_block(block_lines: List[str]) -> Optional[str]:
    meses = []
    for ln in block_lines:
        meses.extend(RE_MES_ANO.findall(ln))
    return meses[-1] if meses else None

def _is_noise_line_for_remun(line: str) -> bool:
    """
    Filtro mínimo para reduzir lixo (ex.: rodapé, cabeçalhos).
    Mantemos conservador, pois o ajuste fino será feito depois.
    """
    low = line.lower()
    if "emitido" in low or "página" in low or "pagina" in low:
        return True
    if "indicador" in line and "descrição" in line.lower():
        return True
    return False

# ------------------------------------------------------------
# PARSER PRINCIPAL
# ------------------------------------------------------------

def parse_cnis(texto: str) -> Dict:
    """
    CNIS CIDADÃO | SEGURADO EMPREGADO
    Regra: cria vínculo APENAS quando a linha do vínculo contém:
    - sequencial no início
    - token "Empregado"
    - data DD/MM/AAAA
    Extração literal.
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

    m = RE_NIT_ID.search(texto)
    if m:
        resultado["identificacao"]["nit"] = m.group(1).strip()

    # --------------------------
    # PROCESSAMENTO
    # --------------------------
    linhas = texto.split("\n")

    vinculo_atual = None
    bloco_linhas: List[str] = []

    for linha in linhas:
        raw = linha.rstrip("\n")
        ln = raw.strip()
        if not ln:
            continue

        # --------------------------
        # GATILHO: linha de vínculo "Empregado" válida
        # --------------------------
        if _is_likely_vinculo_line(ln):
            # fecha vínculo anterior
            if vinculo_atual:
                # última remuneração pelo bloco acumulado (se não houver, mantém o que já tiver)
                if not vinculo_atual.get("ultima_remuneracao"):
                    vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
                resultado["vinculos"].append(vinculo_atual)

            data_inicio, data_fim, idx_ini_data, idx_fim_ult_data = _extract_datas_from_line(ln)
            sequencial, nit_vinculo, codigo_emp, nome_empresa = _extract_nit_and_codigo_and_empresa(ln, idx_ini_data)
            matricula, indicadores, ultima_remun_linha = _extract_matricula_and_indicadores(ln, idx_fim_ult_data)

            vinculo_atual = {
                "sequencial": sequencial,
                "nit_vinculo": nit_vinculo,
                "nome_empresa": nome_empresa,
                "codigo_emp": codigo_emp,
                "origem_vinculo": None,

                "tipo_vinculo": "EMPREGADO",
                "data_inicio": data_inicio,
                "data_fim": data_fim,

                # pode vir na linha do vínculo; se não, pode vir do bloco
                "ultima_remuneracao": ultima_remun_linha,

                "matricula": matricula,
                "indicadores": indicadores,
                "remuneracoes": []
            }

            bloco_linhas = []
            continue

        # --------------------------
        # COLETA DE REMUNERAÇÕES (somente se já houver vínculo aberto)
        # --------------------------
        if vinculo_atual and vinculo_atual.get("tipo_vinculo") == "EMPREGADO":
            bloco_linhas.append(ln)

            # filtro mínimo para reduzir ruído
            if _is_noise_line_for_remun(ln):
                continue

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
        if not vinculo_atual.get("ultima_remuneracao"):
            vinculo_atual["ultima_remuneracao"] = _extract_ultima_remun_from_block(bloco_linhas)
        resultado["vinculos"].append(vinculo_atual)

    return resultado

# ============================================================
# FIM DO ARQUIVO — parsers/parser_cnis.py
# ============================================================
