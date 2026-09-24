"""
===============================================================================
 NUTRE COMPARE PRO  v2.0
 Comparacao nutricional, analise economica, preco limite e simulacao de
 formulacao para commodities de racao animal.

 Arquivo unico, de proposito: da para criar direto pela interface web do
 GitHub, sem clonar nada, e o Streamlit Cloud sobe sem configuracao extra.

 Deploy:  share.streamlit.io  ->  New app  ->  aponte para este arquivo
 Local:   pip install -r requirements.txt  &&  streamlit run streamlit_app.py
===============================================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st

# =============================================================================
#  >>> COLE AQUI O LINK DA SUA PLANILHA <<<
#  A planilha precisa estar compartilhada como
#  "Qualquer pessoa com o link  ->  Leitor".
#  Este valor e so o padrao: da para trocar pela barra lateral sem mexer
#  no codigo, ou definir SHEET_URL nos secrets do Streamlit Cloud.
# =============================================================================
SHEET_URL_PADRAO = (
    "https://docs.google.com/spreadsheets/d/"
    "1nxpwRl24aPK5NL2uvCmSUPbI1aLqn86ZmqrQIdKtngI/edit?usp=sharing"
)

ABA_NUTRICIONAL = "NUTRICIONAL"
ABA_FONTES = "FONTES"
ABA_COMMODITIES = "COMMODITIES"
ABA_FAIXAS = "FAIXAS_PRECO"

COLUNAS_META = {"PARAMETRO", "UNIDADE", "BASE", "CATEGORIA",
                "FONTE", "LINK", "OBSERVACAO"}
CORES_PADRAO = ["#10b981", "#f59e0b", "#3b82f6", "#8b5cf6", "#ec4899",
                "#14b8a6", "#ef4444", "#84cc16", "#06b6d4", "#a855f7"]
AUSENTES = {"", "N/D", "ND", "NA", "N/A", "-", "--", "NAN", "NONE", "NULL", "S/D"}
PARAM_MS, PARAM_PB = "Materia Seca", "Proteina Bruta"
COR_ORIGINAL, COR_REESTRUTURADA = "#3b82f6", "#10b981"

st.set_page_config(page_title="Nutre Compare Pro", layout="wide", page_icon="🌾")


# =============================================================================
# 1. TEXTO E NUMEROS
# =============================================================================
_ACENTOS = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ",
    "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")


def normaliza_texto(s) -> str:
    """Tira acentos e padroniza espacos: 'Proteína  Bruta' casa com
    'Proteina Bruta'. Assim a planilha pode ser escrita de forma natural."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().translate(_ACENTOS))


def chave(s) -> str:
    return normaliza_texto(s).upper()


def parse_number(val):
    """Texto da planilha -> float, ou None quando nao e numero.

    Trata o formato brasileiro corretamente. A versao 1.0 da ferramenta
    devolvia 0.0 para '1.200,50', porque replace(',', '.') produzia
    '1.200.50' e o except engolia o erro. Aqui o que nao e numero vira
    None, e None nunca vira zero em lugar nenhum do sistema.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if chave(s) in AUSENTES:
        return None
    s = re.sub(r"[^\d,.\-]", "", s)          # descarta unidades e texto
    if s in ("", "-", ".", ","):
        return None

    tem_v, tem_p = "," in s, "." in s
    if tem_v and tem_p:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")     # 1.200,50 -> 1200.50
        else:
            s = s.replace(",", "")                       # 1,200.50 -> 1200.50
    elif tem_v:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif tem_p:
        partes = s.split(".")
        if len(partes) > 2 or (len(partes) == 2 and len(partes[1]) == 3
                               and 0 < len(partes[0]) <= 3):
            s = s.replace(".", "")                       # 1.200 -> 1200
    try:
        return float(s)
    except ValueError:
        return None


def fmt(x, casas: int = 2) -> str:
    """Padrao brasileiro, sempre duas casas."""
    if x is None:
        return "N/D"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(x, casas: int = 2) -> str:
    return "N/D" if x is None else f"R$ {fmt(x, casas)}"


# =============================================================================
# 2. ENDERECO DA PLANILHA
# =============================================================================
@dataclass
class Fonte:
    """modo 'id'        -> compartilhada por link. Le as abas pelo NOME.
       modo 'publicada' -> publicada na web (/d/e/2PACX-...). O Google so
                           entrega uma aba por vez, por gid numerico."""
    modo: str
    identificador: str
    gids: dict = field(default_factory=dict)

    def url(self, aba: str | None = None) -> str:
        if self.modo == "id":
            base = f"https://docs.google.com/spreadsheets/d/{self.identificador}/gviz/tq?tqx=out:csv"
            return f"{base}&sheet={quote(aba)}" if aba else base
        gid = self.gids.get(aba, "0" if aba is None else None)
        if gid is None:
            raise ValueError(
                f"A aba '{aba}' precisa de um gid. Links de publicacao na web "
                "entregam uma aba por vez. Use o compartilhamento por link, "
                "que dispensa gids.")
        return (f"https://docs.google.com/spreadsheets/d/e/{self.identificador}"
                f"/pub?gid={gid}&single=true&output=csv")


def resolver_fonte(entrada: str, gids: dict | None = None) -> Fonte:
    """Aceita link completo, link de publicacao, ou o ID sozinho."""
    s = (entrada or "").strip()
    if not s:
        raise ValueError("Informe o link ou o ID da planilha.")
    m = re.search(r"/spreadsheets/d/e/([A-Za-z0-9_-]+)", s)
    if m:
        return Fonte("publicada", m.group(1), gids or {})
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", s)
    if m:
        return Fonte("id", m.group(1))
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", s):
        return Fonte("id", s)
    raise ValueError("Nao reconheci esse endereco. Cole o link que aparece na "
                     "barra do navegador ao abrir a planilha.")


# =============================================================================
# 3. VALOR
# =============================================================================
class Valor:
    """Dado nutricional com unidade, base e disponibilidade.

    Um float nao sabe dizer se representa 'zero' ou 'nao sei'. Este objeto
    sabe, e e por isso que existe.
    """
    __slots__ = ("valor", "unidade", "base", "disponivel", "provisorio",
                 "parametro", "commodity")

    def __init__(self, valor, unidade="", base="MS", parametro="",
                 commodity="", provisorio=False):
        self.valor = valor
        self.unidade = unidade or ""
        b = (base or "MS").upper()
        self.base = b if b in ("MS", "MN") else "MS"
        self.parametro, self.commodity = parametro, commodity
        self.provisorio = provisorio
        self.disponivel = valor is not None

    def fmt(self, casas: int = 2) -> str:
        return "N/D" if not self.disponivel else fmt(self.valor, casas)


# =============================================================================
# 4. LEITURA DA PLANILHA
# =============================================================================
@st.cache_data(ttl=300, show_spinner="Lendo a planilha...")
def carregar_abas(entrada: str, gids: tuple) -> dict:
    fonte = resolver_fonte(entrada, dict(gids))
    erros, avisos = [], []

    def _le(nome, obrigatoria=False):
        try:
            df = pd.read_csv(fonte.url(nome), dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception as e:                                # noqa: BLE001
            if obrigatoria:
                # a aba pode ter outro nome: tenta a primeira da planilha
                try:
                    df = pd.read_csv(fonte.url(None), dtype=str)
                    df.columns = [str(c).strip() for c in df.columns]
                    avisos.append(
                        f"Nao achei uma aba chamada '{nome}'. Usei a primeira aba "
                        f"da planilha. Renomeie a aba para '{nome}' para evitar "
                        f"surpresas quando voce reordenar as abas.")
                    return df
                except Exception as e2:                       # noqa: BLE001
                    raise RuntimeError(
                        f"Nao consegui ler a planilha. Verifique se o "
                        f"compartilhamento esta como 'qualquer pessoa com o link'. "
                        f"({type(e2).__name__})") from e
            erros.append(nome)
            return pd.DataFrame()

    return {"nutricional": _le(ABA_NUTRICIONAL, True),
            "fontes": _le(ABA_FONTES),
            "commodities": _le(ABA_COMMODITIES),
            "faixas": _le(ABA_FAIXAS),
            "lido_em": datetime.now(), "erros": erros, "avisos": avisos}


class BancoNutricional:
    """Ponto unico de acesso aos dados. Nenhum calculo le a planilha direto."""

    def __init__(self, pacote: dict):
        self.df = pacote["nutricional"]
        self.df_fontes = pacote.get("fontes", pd.DataFrame())
        self.df_com = pacote.get("commodities", pd.DataFrame())
        self.df_faixas = pacote.get("faixas", pd.DataFrame())
        self.lido_em = pacote.get("lido_em", datetime.now())
        self.erros = pacote.get("erros", [])
        self.avisos = list(pacote.get("avisos", []))
        self.cores, self.info_fonte = {}, {}

        cols = {chave(c): c for c in self.df.columns}
        self.col_param = cols.get("PARAMETRO")
        self.col_unidade = cols.get("UNIDADE")
        self.col_base = cols.get("BASE")
        self.col_categoria = cols.get("CATEGORIA")
        if self.col_param is None:
            raise ValueError(
                "A aba NUTRICIONAL precisa de uma coluna chamada 'Parametro'. "
                f"Encontrei estas colunas: {', '.join(map(str, self.df.columns))}")
        if self.col_unidade is None:
            self.avisos.append("Sem coluna 'Unidade': o custo por unidade de "
                               "nutriente nao vai conseguir calcular.")
        if self.col_base is None:
            self.avisos.append("Sem coluna 'Base': assumi materia seca (MS) para "
                               "todos os parametros. Se algum estiver em materia "
                               "natural, os totais da formulacao sairao errados.")

        # tudo que nao for metadado e commodity
        self.commodities = [c for c in self.df.columns
                            if chave(c) not in COLUNAS_META
                            and not chave(c).startswith("UNNAMED")]
        self._aplica_ativos()
        self._indexa()
        self._marca_provisorios()

    def _aplica_ativos(self):
        if self.df_com.empty:
            return
        cols = {chave(c): c for c in self.df_com.columns}
        c_nome = cols.get("COMMODITY")
        if not c_nome:
            return
        inativas = set()
        for _, lin in self.df_com.iterrows():
            nome = chave(lin.get(c_nome))
            if cols.get("ATIVO") and chave(lin.get(cols["ATIVO"])) in ("NAO", "N", "FALSE", "0"):
                inativas.add(nome)
            cor = str(lin.get(cols.get("COR", ""), "")).strip()
            if cor.startswith("#"):
                self.cores[nome] = cor
        if inativas:
            self.commodities = [c for c in self.commodities if chave(c) not in inativas]

    def _indexa(self):
        self._idx, self.meta_param = {}, {}
        for _, lin in self.df.iterrows():
            nome = normaliza_texto(lin[self.col_param])
            if not nome:
                continue
            k = chave(nome)
            un = str(lin[self.col_unidade]).strip() if self.col_unidade else ""
            if chave(un) in AUSENTES:
                un = ""
            base = str(lin[self.col_base]).strip().upper() if self.col_base else "MS"
            cat = str(lin[self.col_categoria]).strip() if self.col_categoria else "Outros"
            self.meta_param[k] = {"nome": nome, "unidade": un,
                                  "base": base if base in ("MS", "MN") else "MS",
                                  "categoria": cat}
            for com in self.commodities:
                self._idx[(k, chave(com))] = Valor(parse_number(lin[com]), un,
                                                   base, nome, com)

    def _marca_provisorios(self):
        """Status != VERIFICADO na aba FONTES = dado provisorio.
        A cor vermelha da planilha se perde no export CSV, entao quem avisa
        o aplicativo e a coluna Status, nao a cor."""
        if self.df_fontes.empty:
            return
        cols = {chave(c): c for c in self.df_fontes.columns}
        cp, cc, cs = cols.get("PARAMETRO"), cols.get("COMMODITY"), cols.get("STATUS")
        if not (cp and cc and cs):
            return
        for _, lin in self.df_fontes.iterrows():
            k = (chave(lin[cp]), chave(lin[cc]))
            status = chave(lin[cs])
            self.info_fonte[k] = {"status": status,
                                  "fonte": str(lin.get(cols.get("FONTE", ""), "")).strip()}
            if k in self._idx and status != "VERIFICADO":
                self._idx[k].provisorio = True

    # ---------------- acesso ----------------
    def get(self, commodity: str, parametro: str) -> Valor:
        v = self._idx.get((chave(parametro), chave(commodity)))
        if v is None:
            m = self.meta_param.get(chave(parametro), {})
            return Valor(None, m.get("unidade", ""), m.get("base", "MS"),
                         parametro, commodity)
        return v

    def unidade(self, p): return self.meta_param.get(chave(p), {}).get("unidade", "")
    def base(self, p): return self.meta_param.get(chave(p), {}).get("base", "MS")
    def nomes_parametros(self): return [m["nome"] for m in self.meta_param.values()]

    def cor(self, commodity, i=0):
        return self.cores.get(chave(commodity), CORES_PADRAO[i % len(CORES_PADRAO)])

    def buscar_parametro(self, fragmento):
        """Acha o nome real a partir de um pedaco: tolera a planilha escrever
        'Energia Metabolizavel - Aves' ou so 'EM Aves'."""
        f = chave(fragmento)
        if f in self.meta_param:
            return self.meta_param[f]["nome"]
        for k, m in self.meta_param.items():
            if f in k or k in f:
                return m["nome"]
        return None

    def faixa_preco(self, ref, aval):
        """None quando o par nao esta cadastrado: sem regra registrada, o app
        nao inventa um semaforo."""
        if self.df_faixas.empty:
            return None
        cols = {chave(c): c for c in self.df_faixas.columns}
        cr, ca = cols.get("COMMODITY REFERENCIA"), cols.get("COMMODITY AVALIADA")
        cv, cam = cols.get("FAIXA VERDE ATE (%)"), cols.get("FAIXA AMARELA ATE (%)")
        if not (cr and ca and cv and cam):
            return None
        for _, lin in self.df_faixas.iterrows():
            if chave(lin[cr]) == chave(ref) and chave(lin[ca]) == chave(aval):
                verde, amarelo = parse_number(lin[cv]), parse_number(lin[cam])
                if verde is not None and amarelo is not None:
                    return {"verde": verde, "amarelo": amarelo,
                            "fonte": str(lin.get(cols.get("FONTE DA REGRA", ""), "")).strip()}
        return None

    def contagem_provisorios(self):
        prov = sum(1 for v in self._idx.values() if v.provisorio and v.disponivel)
        tot = sum(1 for v in self._idx.values() if v.disponivel)
        return prov, tot


# =============================================================================
# 5. MEMORIAL DE CALCULO
# =============================================================================
class Memorial:
    """Registro auditavel: entradas, formula, conversoes, resultado.
    Alimenta o expander 'Como essa conta e feita?' automaticamente."""

    def __init__(self, titulo):
        self.titulo = titulo
        self.entradas, self.passos, self.avisos = [], [], []
        self.formula, self.resultado, self.impedimento = "", None, None

    def entrada(self, r, v, u=""): self.entradas.append((r, v, u)); return self
    def passo(self, t): self.passos.append(t); return self
    def aviso(self, t): self.avisos.append(t); return self
    def bloqueia(self, m): self.impedimento = m; return self

    def render(self):
        if self.impedimento:
            st.warning(f"Cálculo não realizado: {self.impedimento}")
        if self.entradas:
            st.markdown("**Valores utilizados**")
            for r, v, u in self.entradas:
                st.markdown(f"- {r}: **{v}** {u}".rstrip())
        if self.formula:
            st.markdown("**Fórmula**")
            st.code(self.formula, language="text")
        if self.passos:
            st.markdown("**Desenvolvimento**")
            for p in self.passos:
                st.markdown(f"- {p}")
        if self.resultado is not None:
            st.markdown(f"**Resultado:** {self.resultado}")
        for a in self.avisos:
            st.caption(f"⚠ {a}")


def mostrar_memorial(m, rotulo="Como essa conta é feita?"):
    with st.expander(rotulo):
        m.render()


# =============================================================================
# 6. CONVERSAO DE BASE
# =============================================================================
def pct_materia_seca(banco, commodity) -> Valor:
    nome = banco.buscar_parametro(PARAM_MS)
    return banco.get(commodity, nome) if nome else Valor(None, "%", "MN", PARAM_MS, commodity)


def para_materia_natural(banco, commodity, valor: Valor):
    """valor_MN = valor_MS x (MS% / 100).

    Necessario porque a inclusao na formulacao e informada em materia
    natural, enquanto quase todo dado de tabela esta em materia seca.
    Somar os dois sem converter e erro matematico.
    """
    if not valor.disponivel:
        return valor, None
    if valor.base == "MN":
        return valor, "já estava em matéria natural"
    ms = pct_materia_seca(banco, commodity)
    if not ms.disponivel or ms.valor <= 0:
        return (Valor(None, valor.unidade, "MN", valor.parametro, commodity),
                "conversão impossível: Matéria Seca ausente")
    novo = Valor(valor.valor * ms.valor / 100.0, valor.unidade, "MN",
                 valor.parametro, commodity, valor.provisorio)
    return novo, f"{fmt(valor.valor)} × {fmt(ms.valor)}% / 100 = {fmt(novo.valor)}"


# =============================================================================
# 7. CALCULOS
# =============================================================================
def custo_por_nutriente(banco, commodity, parametro, preco_ton):
    v = banco.get(commodity, parametro)
    m = Memorial("")
    m.entrada("Preço da tonelada", brl(preco_ton))
    m.entrada(f"{parametro} ({v.base})", v.fmt(), v.unidade)

    if not preco_ton or preco_ton <= 0:
        return None, None, m.bloqueia("preço não informado ou inválido.")
    if not v.disponivel:
        return None, None, m.bloqueia(
            f"o valor de {parametro} para {commodity} não existe na planilha (N/D). "
            "O sistema não substitui dado ausente por zero.")
    if v.valor <= 0:
        return None, None, m.bloqueia(f"{parametro} é zero ou negativo; divisão inválida.")

    un = v.unidade.lower()
    if "%" in un and "da pb" not in un:
        qtd, uc = v.valor * 10.0, "R$/kg"
        m.formula = "Custo = Preço da tonelada / (valor % × 10)"
        m.passo(f"Uma tonelada tem 1.000 kg, então {fmt(v.valor)}% equivale a "
                f"{fmt(v.valor)} × 10 = {fmt(qtd)} kg por tonelada.")
    elif "mcal/kg" in un:
        qtd, uc = v.valor * 1000.0, "R$/Mcal"
        m.formula = "Custo = Preço da tonelada / (Mcal/kg × 1.000)"
        m.passo(f"Uma tonelada tem 1.000 kg, então {fmt(v.valor)} Mcal/kg equivale a "
                f"{fmt(v.valor)} × 1.000 = {fmt(qtd)} Mcal por tonelada.")
    elif "kcal/kg" in un:
        qtd, uc = v.valor, "R$/Mcal"
        m.formula = "Custo = Preço da tonelada / (kcal/kg × 1.000 kg / 1.000)"
        m.passo(f"{fmt(v.valor)} kcal/kg × 1.000 kg = {fmt(qtd)} Mcal/t.")
    else:
        return None, None, m.bloqueia(
            f"a unidade '{v.unidade}' não permite determinar a quantidade contida "
            "em uma tonelada. Custo por unidade não calculado.")

    if v.base == "MS":
        m.aviso("Valor em base de matéria seca: o custo é por unidade de "
                "nutriente na matéria seca do ingrediente.")
    r = preco_ton / qtd
    m.passo(f"{brl(preco_ton)} / {fmt(qtd)} = {brl(r)}")
    m.resultado = f"{brl(r)} por unidade ({uc})"
    if v.provisorio:
        m.aviso("Dado marcado como PROVISÓRIO na aba FONTES.")
    return r, uc, m


def preco_limite(banco, ref, aval, parametro, preco_ref):
    """Preco limite = Preco_ref × (nutriente_aval / nutriente_ref).

    NAO e 'o preco justo': e o preco equivalente NAQUELE nutriente.
    """
    a, b = banco.get(ref, parametro), banco.get(aval, parametro)
    m = Memorial("")
    m.entrada(f"Preço de {ref}", brl(preco_ref), "por tonelada")
    m.entrada(f"{parametro} em {ref}", a.fmt(), a.unidade)
    m.entrada(f"{parametro} em {aval}", b.fmt(), b.unidade)

    if not preco_ref or preco_ref <= 0:
        return None, m.bloqueia(f"preço de {ref} não informado.")
    if not a.disponivel or not b.disponivel:
        return None, m.bloqueia(
            f"{parametro} de {ref if not a.disponivel else aval} está N/D na planilha.")
    if a.valor <= 0:
        return None, m.bloqueia(f"{parametro} de {ref} é zero; razão indefinida.")
    if chave(a.unidade) != chave(b.unidade):
        return None, m.bloqueia(
            f"unidades incompatíveis: {ref} em '{a.unidade}' e {aval} em "
            f"'{b.unidade}'. A razão entre unidades diferentes não tem significado.")
    if a.base != b.base:
        m.aviso(f"Bases diferentes ({ref} em {a.base}, {aval} em {b.base}). "
                "Confira a coluna Base da planilha.")

    razao = b.valor / a.valor
    r = preco_ref * razao
    m.formula = ("Preço limite = Preço da referência × "
                 "(nutriente do avaliado / nutriente da referência)")
    m.passo(f"Razão do nutriente: {fmt(b.valor)} / {fmt(a.valor)} = {fmt(razao)}")
    m.passo(f"{brl(preco_ref)} × {fmt(razao)} = {brl(r)}")
    m.resultado = f"{brl(r)} por tonelada"
    m.aviso(f"Este é o preço equivalente EM {parametro.upper()}, não um preço justo "
            "global. Outro nutriente daria outro limite.")
    if a.provisorio or b.provisorio:
        m.aviso("Há dado PROVISÓRIO neste cálculo.")
    return r, m


def custo_formulacao(banco, formulacao, precos):
    m = Memorial("")
    m.formula = "Custo = soma de (preço do ingrediente × % de inclusão / 100)"
    total, incompleto = 0.0, False
    for com, pct in formulacao.items():
        if pct <= 0:
            continue
        p = precos.get(com)
        if not p or p <= 0:
            m.aviso(f"Preço de {com} não informado; ingrediente fora do custo.")
            incompleto = True
            continue
        parcela = p * pct / 100.0
        total += parcela
        m.passo(f"{com}: {brl(p)} × {fmt(pct)}% = {brl(parcela)}")
    m.resultado = f"{brl(total)} por tonelada"
    if incompleto:
        m.aviso("Custo incompleto: há ingrediente sem preço.")
    return (None if incompleto else total), m


def nutricao_formulacao(banco, formulacao, parametro):
    """Dado ausente nunca vira zero: se falta o dado de um ingrediente com
    inclusao > 0, o resultado e N/D com o motivo explicito."""
    unidade = banco.unidade(parametro)
    m = Memorial("")
    if "da pb" in unidade.lower():
        return _fracao_pb(banco, formulacao, parametro, unidade, m)

    m.formula = ("Valor = soma de (valor do ingrediente em matéria natural "
                 "× % de inclusão / 100)")
    total = 0.0
    for com, pct in formulacao.items():
        if pct <= 0:
            continue
        v = banco.get(com, parametro)
        if not v.disponivel:
            m.bloqueia(f"{parametro} de {com} está N/D. Com inclusão de {fmt(pct)}%, "
                       "somar sem esse dado produziria um total subestimado.")
            return None, unidade, m
        v_mn, nota = para_materia_natural(banco, com, v)
        if not v_mn.disponivel:
            m.bloqueia(f"não foi possível converter {parametro} de {com} para "
                       "matéria natural: Matéria Seca ausente.")
            return None, unidade, m
        parcela = v_mn.valor * pct / 100.0
        total += parcela
        extra = f" [conversão MS→MN: {nota}]" if v.base == "MS" else ""
        m.passo(f"{com}: {fmt(v_mn.valor)} × {fmt(pct)}% = {fmt(parcela)}{extra}")
        if v.provisorio:
            m.aviso(f"{com}: dado PROVISÓRIO.")
    m.resultado = f"{fmt(total)} {unidade} (matéria natural)"
    return total, unidade, m


def _fracao_pb(banco, formulacao, parametro, unidade, m):
    """PDR e PNDR estao em '% da PB', nao em % do alimento. Media ponderada
    pela massa daria numero inflado por ingredientes de baixa proteina."""
    nome_pb = banco.buscar_parametro(PARAM_PB)
    m.formula = ("Valor = soma de (fração do ingrediente × proteína que ele aporta) "
                 "/ proteína total da ração")
    m.aviso("Parâmetro expresso em % da PB. A média é ponderada pela proteína "
            "aportada por cada ingrediente, não pela massa.")
    if not nome_pb:
        m.bloqueia("parâmetro 'Proteína Bruta' não encontrado na planilha.")
        return None, unidade, m
    soma_pond, soma_pb = 0.0, 0.0
    for com, pct in formulacao.items():
        if pct <= 0:
            continue
        v, pb = banco.get(com, parametro), banco.get(com, nome_pb)
        if not v.disponivel or not pb.disponivel:
            m.bloqueia(f"{parametro if not v.disponivel else PARAM_PB} de {com} está N/D.")
            return None, unidade, m
        pb_mn, _ = para_materia_natural(banco, com, pb)
        if not pb_mn.disponivel:
            m.bloqueia(f"Matéria Seca de {com} ausente; conversão impossível.")
            return None, unidade, m
        aporte = pb_mn.valor * pct / 100.0
        soma_pb += aporte
        soma_pond += v.valor * aporte
        m.passo(f"{com}: aporta {fmt(aporte)}% de PB na ração, com "
                f"{parametro} = {fmt(v.valor)}% da PB")
    if soma_pb <= 0:
        m.bloqueia("proteína total da ração é zero; média ponderada indefinida.")
        return None, unidade, m
    total = soma_pond / soma_pb
    m.passo(f"{fmt(soma_pond)} / {fmt(soma_pb)} = {fmt(total)}")
    m.resultado = f"{fmt(total)} {unidade}"
    return total, unidade, m


def normalizar_formulacao(f: dict) -> dict:
    total = sum(v for v in f.values() if v > 0)
    return dict(f) if total <= 0 else {c: v * 100.0 / total for c, v in f.items()}


# =============================================================================
# 8. VINCULOS DE SUBSTITUICAO
# =============================================================================
def vinculos_de(relacoes, commodity, ingredientes):
    """Parceiros ativos e o fator de cada um. O fator e 'quantos pontos de
    para se movem para cada 1 ponto de de'. No inverso vale o reciproco."""
    saida = {}
    for r in relacoes:
        if not r.get("ativa"):
            continue
        de, para, fator = r["de"], r["para"], float(r.get("fator", 1.0))
        if de not in ingredientes or para not in ingredientes or fator <= 0:
            continue
        if de == commodity and para not in saida:
            saida[para] = fator
        elif para == commodity and de not in saida:
            saida[de] = 1.0 / fator
    return list(saida.items())


def mover_vinculado(valores, relacoes, ingredientes, commodity, novo) -> dict:
    """Move um ingrediente respeitando os vinculos. Devolve um NOVO dicionario.

    Com fator diferente de 1 a soma muda de proposito: entra 1 ponto e saem
    1,6, entao o total cai 0,6. O deslocamento e limitado pelo que o parceiro
    pode ceder ou receber, e pelo teto de 100% no total.
    """
    f = dict(valores)
    novo = max(0.0, min(100.0, novo))
    ant = f.get(commodity, 0.0)
    d = novo - ant
    v = vinculos_de(relacoes, commodity, ingredientes)
    if not v or abs(d) < 1e-9:
        f[commodity] = round(novo, 2)
        return f

    for p, fator in v:                       # limite de cada parceiro
        if abs(fator) < 1e-9:
            continue
        cur = f.get(p, 0.0)
        d = min(d, cur / fator) if d > 0 else max(d, (cur - 100.0) / fator)

    k = 1.0 - sum(fator for _, fator in v)   # limite do total
    if abs(k) > 1e-9:
        total = sum(f.get(c, 0.0) for c in ingredientes)
        if d * k > 0:
            maximo = (100.0 - total) / k
            if k > 0 and d > maximo:
                d = max(0.0, maximo)
            elif k < 0 and d < maximo:
                d = min(0.0, maximo)

    for p, fator in v:
        f[p] = round(max(0.0, min(100.0, f.get(p, 0.0) - d * fator)), 2)
    f[commodity] = round(max(0.0, min(100.0, ant + d)), 2)
    return f


# =============================================================================
# 9. BARRAS COMPARATIVAS
# =============================================================================
def barra(nome, valor, maximo, cor, marca=""):
    """HTML sem indentacao inicial: com espacos, o Streamlit trata como
    bloco de codigo e mostra o markup cru."""
    if valor is not None and maximo and maximo > 0:
        pct, texto = min(max(valor / maximo * 100, 0), 100), fmt(valor)
    else:
        pct, texto = 0, "N/D"
    return (f"""<div style="display:flex;align-items:center;margin-bottom:6px;">
<div style="width:135px;font-size:13px;color:{cor};font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{nome}{marca}</div>
<div style="flex:1;background:#334155;border-radius:10px;height:18px;overflow:hidden;margin-right:10px;">
<div style="width:{pct}%;background:{cor};height:100%;"></div>
</div>
<div style="width:66px;font-size:13px;text-align:right;">{texto}</div>
</div>""")


def bloco_barras(itens):
    vals = [i[1] for i in itens]
    disp = [v for v in vals if v is not None]
    mx = max(disp) * 1.15 if disp and max(disp) > 0 else 1.0
    return ('<div style="margin-bottom:14px;">'
            + "".join(barra(n, v, mx, c, mk) for n, v, c, mk in itens) + "</div>")


# =============================================================================
# 10. INTERFACE
# =============================================================================
st.sidebar.header("📄 Planilha de dados")

try:
    padrao = st.secrets.get("SHEET_URL", SHEET_URL_PADRAO)
except Exception:                                          # noqa: BLE001
    padrao = SHEET_URL_PADRAO                              # sem secrets configurado

entrada = st.sidebar.text_input(
    "Link da planilha do Google Sheets", value=padrao,
    placeholder="https://docs.google.com/spreadsheets/d/...",
    help="A planilha precisa estar compartilhada como "
         "'qualquer pessoa com o link — Leitor'.")

if not entrada.strip():
    st.title("Nutre Compare Pro")
    st.info("Cole o link da sua planilha na barra lateral para começar.")
    st.stop()

gids = {}
try:
    fonte = resolver_fonte(entrada)
except ValueError as e:
    st.title("Nutre Compare Pro")
    st.error(str(e))
    st.stop()

if fonte.modo == "publicada":
    st.sidebar.warning("Link de publicação na web: esse formato entrega uma aba "
                       "por vez e exige o gid de cada uma. O compartilhamento "
                       "por link é mais simples.")
    with st.sidebar.expander("Informar os gids"):
        for aba in (ABA_NUTRICIONAL, ABA_FONTES, ABA_COMMODITIES, ABA_FAIXAS):
            g = st.text_input(aba, key=f"gid_{aba}")
            if g.strip():
                gids[aba] = g.strip()

if st.sidebar.button("🔄 Atualizar dados agora"):
    carregar_abas.clear()
    st.rerun()

try:
    pacote = carregar_abas(entrada, tuple(sorted(gids.items())))
    banco = BancoNutricional(pacote)
except Exception as e:                                     # noqa: BLE001
    st.title("Nutre Compare Pro")
    st.error(f"Não consegui montar o banco de dados. {e}")
    with st.expander("O que verificar", expanded=True):
        st.markdown("""
1. **Compartilhamento**: abra a planilha, clique em *Compartilhar*, e em
   *Acesso geral* escolha **Qualquer pessoa com o link → Leitor**.
2. **Nome da aba principal**: precisa se chamar `NUTRICIONAL`.
3. **Colunas obrigatórias** na primeira linha: `Parâmetro`, `Unidade`,
   `Base`, `Categoria`, e depois uma coluna por commodity.
4. **Linha de cabeçalho**: precisa ser a primeira linha da aba, sem título
   ou linhas em branco acima.
""")
    st.stop()

if not banco.commodities:
    st.error("Nenhuma commodity encontrada. Depois de `Parâmetro`, `Unidade`, "
             "`Base` e `Categoria`, cada coluna é tratada como uma commodity. "
             f"Colunas lidas: {', '.join(map(str, banco.df.columns))}")
    st.stop()

st.sidebar.caption(f"Lido em {banco.lido_em.strftime('%d/%m/%Y %H:%M:%S')} · "
                   f"{len(banco.meta_param)} parâmetros · "
                   f"{len(banco.commodities)} commodities")
for a in banco.avisos:
    st.sidebar.warning(a)
if banco.erros:
    st.sidebar.info("Abas opcionais ausentes: " + ", ".join(banco.erros))

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações da Análise")
especie = st.sidebar.selectbox("Filtro Zootécnico (Espécie)", ["Bovinos", "Suínos", "Aves"])
praca = st.sidebar.text_input("Praça de Cotação", value="Campinas/SP")
embalagem = st.sidebar.selectbox("Formato de Comercialização", ["A Granel", "Ensacado"])

st.sidebar.markdown("---")
st.sidebar.header(f"💰 Cotações do Dia (R$/ton) — {embalagem}")
precos = {c: st.sidebar.number_input(c, min_value=0.0, value=0.0, step=50.0,
                                     key=f"preco_{c}") for c in banco.commodities}
st.sidebar.caption("Deixe 0 se não houver cotação. Sem preço, o custo não é calculado.")

param_energia = (banco.buscar_parametro(f"Energia Metabolizavel - {especie}")
                 or banco.buscar_parametro("Energia Metabolizavel"))


def params_visiveis():
    """Esconde as linhas de energia das outras espécies."""
    return [m["nome"] for m in banco.meta_param.values()
            if not (chave(m["nome"]).startswith("ENERGIA METABOLIZAVEL")
                    and m["nome"] != param_energia)]


st.title("Nutre Compare Pro")
st.caption("Comparação nutricional, análise econômica e simulação de formulação")

n_prov, n_tot = banco.contagem_provisorios()
if n_prov:
    st.warning(f"**{n_prov} de {n_tot} valores preenchidos estão marcados como "
               "PROVISÓRIOS** na aba FONTES. Enquanto não forem substituídos por "
               "dados com fonte registrada, nenhum resultado desta ferramenta deve "
               "embasar decisão comercial. Valores provisórios aparecem com *.")

tab1, tab2, tab3 = st.tabs(["📊 Custo-Benefício & Nutrição",
                            "⚖️ Simulador de Formulação", "📋 Base de Dados"])

# ------------------------------- ABA 1 ---------------------------------------
with tab1:
    with st.expander("Commodities selecionadas para análise", expanded=True):
        pad = [c for c in banco.commodities
               if chave(c) in ("DDGS", "FARELO DE SOJA")] or banco.commodities[:2]
        selecionadas = st.multiselect("Escolha uma ou mais commodities",
                                      banco.commodities, default=pad, key="sel_com")
    if not selecionadas:
        st.info("Selecione ao menos uma commodity.")
        st.stop()
    cores = {c: banco.cor(c, i) for i, c in enumerate(selecionadas)}

    st.subheader(f"Análise Econômica — Praça: {praca} | Formato: {embalagem}")
    criterios = [p for p in [banco.buscar_parametro("Proteina Bruta"), param_energia] if p]
    for crit in criterios:
        st.markdown(f"**Custo por unidade de {crit}**")
        cols = st.columns(min(len(selecionadas), 4))
        for i, com in enumerate(selecionadas):
            custo, uc, mem = custo_por_nutriente(banco, com, crit, precos[com])
            with cols[i % len(cols)]:
                st.metric(com, brl(custo) if custo is not None else "N/D", uc,
                          delta_color="off")
                mostrar_memorial(mem)
        st.markdown("")

    st.markdown("---")
    st.subheader("Preço Limite")
    if len(selecionadas) < 2:
        st.info("Selecione ao menos duas commodities para calcular o preço limite.")
    else:
        inv = st.session_state.get("inverteu", False)
        ref_pad, aval_pad = (selecionadas[1], selecionadas[0]) if inv else \
                            (selecionadas[0], selecionadas[1])
        c1, c2, c3 = st.columns([2, 2, 1])
        ref = c1.selectbox("Commodity de referência", selecionadas,
                           index=selecionadas.index(ref_pad))
        restantes = [c for c in selecionadas if c != ref]
        aval = c2.selectbox("Commodity avaliada", restantes,
                            index=restantes.index(aval_pad) if aval_pad in restantes else 0)
        c3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if c3.button("🔄 Inverter comparação"):
            st.session_state["inverteu"] = not inv
            st.rerun()

        compat = [p for p in params_visiveis()
                  if banco.get(ref, p).disponivel and banco.get(aval, p).disponivel]
        if not compat:
            st.warning("Não há parâmetro com dado disponível para os dois produtos.")
        else:
            pb = banco.buscar_parametro("Proteina Bruta")
            with st.expander("Critério de comparação", expanded=True):
                criterio = st.radio("Nutriente usado no cálculo", compat,
                                    index=compat.index(pb) if pb in compat else 0,
                                    horizontal=True, label_visibility="collapsed")
            limite, mem = preco_limite(banco, ref, aval, criterio, precos[ref])
            k1, k2, k3 = st.columns(3)
            k1.metric(f"Preço limite de {aval}",
                      brl(limite) if limite is not None else "N/D",
                      f"critério: {criterio}", delta_color="off")
            if limite is not None and precos[aval] > 0:
                dif = limite - precos[aval]
                k2.metric("Situação do preço atual", brl(precos[aval]),
                          f"🟢 Margem de {brl(dif)}" if dif >= 0
                          else f"🔴 Acima em {brl(abs(dif))}",
                          delta_color="normal" if dif >= 0 else "inverse")
            faixa = banco.faixa_preco(ref, aval)
            if faixa and precos[ref] > 0 and precos[aval] > 0:
                rel = precos[aval] / precos[ref] * 100
                status = ("🟢 Favorável" if rel < faixa["verde"]
                          else "🟡 Atenção" if rel < faixa["amarelo"] else "🔴 Desfavorável")
                k3.metric(f"Relação {aval}/{ref}", f"{fmt(rel)}%", status, delta_color="off")
                with k3.expander("Como essa conta é feita?"):
                    st.markdown(f"{brl(precos[aval])} / {brl(precos[ref])} = **{fmt(rel)}%**")
                    st.markdown(f"Faixa verde até {fmt(faixa['verde'])}%, "
                                f"amarela até {fmt(faixa['amarelo'])}%.")
                    st.caption(f"Origem da regra: {faixa['fonte'] or 'não informada'}")
            elif precos[ref] > 0 and precos[aval] > 0:
                k3.info(f"Sem faixa cadastrada para {ref} × {aval}. O semáforo só "
                        "aparece para pares com regra registrada na planilha.")
            mostrar_memorial(mem)

    st.markdown("---")
    lista = params_visiveis()
    sug = [p for p in lista if chave(p) in
           ("PROTEINA BRUTA", "FIBRA BRUTA", "FDN", "EXTRATO ETEREO", "NDT")]
    if param_energia:
        sug.append(param_energia)
    with st.expander("Comparativo Nutricional Direto", expanded=True):
        escolhidos = st.multiselect("Parâmetros a exibir", lista,
                                    default=sug or lista[:5], key="par_aba1")
    if escolhidos:
        cA, cB = st.columns(2)
        for i, p in enumerate(escolhidos):
            with (cA if i % 2 == 0 else cB):
                st.markdown(f"**{p}** &nbsp;<span style='color:#94a3b8;font-size:12.5px'>"
                            f"({banco.unidade(p)} — base {banco.base(p)})</span>",
                            unsafe_allow_html=True)
                itens = []
                for c in selecionadas:
                    v = banco.get(c, p)
                    itens.append((c, v.valor, cores[c], " *" if v.provisorio else ""))
                st.markdown(bloco_barras(itens), unsafe_allow_html=True)
        st.caption("\\* dado ainda marcado como PROVISÓRIO na planilha. "
                   "As barras usam o valor na base original do parâmetro.")

# ------------------------------- ABA 2 ---------------------------------------
with tab2:
    st.subheader(f"Simulador de Formulação — {especie}")
    st.caption("Percentuais de inclusão em matéria natural, como o ingrediente entra "
               "no misturador. O sistema converte os dados de matéria seca antes de somar.")

    with st.expander("Ingredientes disponíveis", expanded=True):
        ingredientes = st.multiselect("Ingredientes das formulações", banco.commodities,
                                      default=banco.commodities[:4], key="ing_sim")
    if not ingredientes:
        st.info("Selecione os ingredientes.")
        st.stop()

    st.session_state.setdefault("relacoes", [])
    for c in ingredientes:
        st.session_state.setdefault(f"o_{c}", 0.0)
        st.session_state.setdefault(f"r_{c}", 0.0)

    def _ao_mover(com):
        atual = {c: st.session_state[f"r_{c}"] for c in ingredientes}
        novo = mover_vinculado(atual, st.session_state.relacoes, ingredientes,
                               com, st.session_state[f"r_{com}"])
        for c in ingredientes:
            st.session_state[f"r_{c}"] = float(novo[c])

    def _total(pref):
        return sum(st.session_state.get(f"{pref}_{c}", 0.0) for c in ingredientes)

    def painel_total(pref, nome):
        """A soma NAO precisa dar 100%: o que falta sao outros ingredientes,
        fora desta analise. Acima de 100% e impossivel e fica bloqueado."""
        s = _total(pref)
        if s > 100.001:
            st.error(f"**Total da formulação {nome}: {fmt(s)}%** — acima de 100%. "
                     f"Nenhuma ração pode ter mais de 100% de si mesma: "
                     f"reduza {fmt(s - 100)} pontos.")
        elif abs(s - 100) < 0.001:
            st.success(f"**Total da formulação {nome}: 100%** — todos os ingredientes "
                       "estão descritos.")
        else:
            st.warning(f"**Total da formulação {nome}: {fmt(s)}%** — faltam "
                       f"{fmt(100 - s)}% para fechar a ração, tratados como "
                       "**outros ingredientes**, fora desta análise.")

    st.markdown("### Formulação Original")
    cols = st.columns(min(len(ingredientes), 3))
    for i, c in enumerate(ingredientes):
        cols[i % len(cols)].slider(c, 0.0, 100.0, step=0.5, key=f"o_{c}")
    painel_total("o", "original")

    st.markdown("### Relações de Substituição")
    st.caption("Ingredientes relacionados ficam vinculados nos sliders da formulação "
               "reestruturada: ao mover um, o outro se move na proporção do fator. "
               "A original não é afetada — ela é a referência. Substituição **física**, "
               "massa por massa, sem equivalência nutricional.")
    r1, r2, r3 = st.columns([3, 3, 1])
    de = r1.selectbox("Aumentar", ingredientes, key="rel_de")
    para = r2.selectbox("Reduzindo", [c for c in ingredientes if c != de], key="rel_para")
    r3.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if r3.button("Criar relação"):
        if any({r["de"], r["para"]} == {de, para} for r in st.session_state.relacoes):
            st.warning("Essa relação já existe.")
        else:
            st.session_state.relacoes.append({"de": de, "para": para,
                                              "fator": 1.0, "ativa": False})
            st.rerun()

    if not st.session_state.relacoes:
        st.caption("Nenhuma relação criada. Sem relação ativa, cada slider se move sozinho.")
    for i, r in enumerate(list(st.session_state.relacoes)):
        vale = r["de"] in ingredientes and r["para"] in ingredientes
        c1, c2, c3, c4 = st.columns([1.1, 2.6, 2.3, 1])
        r["ativa"] = c1.checkbox("Ativar", value=r["ativa"], key=f"at_{i}", disabled=not vale)
        c2.markdown(f"<div style='padding-top:8px'><b>{r['de']}</b> ◀————▶ "
                    f"<b>{r['para']}</b></div>", unsafe_allow_html=True)
        r["fator"] = c3.number_input(f"1 ponto de {r['de']} = X de {r['para']}",
                                     min_value=0.01, step=0.1,
                                     value=float(r["fator"]), key=f"fat_{i}")
        c4.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if c4.button("Remover", key=f"rm_{i}"):
            st.session_state.relacoes.pop(i)
            st.rerun()
        if not vale:
            st.caption("⚠ Ingrediente fora da seleção atual — relação inativa.")
        else:
            saldo = 1 - r["fator"]
            if abs(saldo) < 1e-9:
                st.caption("Total da formulação não muda.")
            else:
                verbo = "sobe" if saldo > 0 else "cai"
                st.caption(f"Total {verbo} {fmt(abs(saldo))} ponto a cada 1 ponto "
                           f"de {r['de']}.")

    h1, h2 = st.columns([3, 1])
    h1.markdown("### Formulação Reestruturada")
    h2.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if h2.button("📋 Copiar da original"):
        for c in ingredientes:
            st.session_state[f"r_{c}"] = float(st.session_state[f"o_{c}"])
        st.rerun()

    cols = st.columns(min(len(ingredientes), 3))
    for i, c in enumerate(ingredientes):
        parceiros = [p for p, _ in vinculos_de(st.session_state.relacoes, c, ingredientes)]
        rotulo = f"{c}  🔗 {', '.join(parceiros)}" if parceiros else c
        cols[i % len(cols)].slider(rotulo, 0.0, 100.0, step=0.5, key=f"r_{c}",
                                   on_change=_ao_mover, args=(c,))
    painel_total("r", "reestruturada")

    so, sr = _total("o"), _total("r")
    if so > 100.001 or sr > 100.001:
        st.error("Uma das formulações passa de 100%. Ajuste antes de comparar.")
    elif so <= 0 or sr <= 0:
        st.info("Mova os sliders das duas formulações para ver a comparação.")
    else:
        st.markdown("---")
        st.subheader("Comparação — Original × Reestruturada")
        parcial = so < 99.999 or sr < 99.999
        if parcial and abs(so - sr) > 0.001:
            st.error(f"**Atenção: as formulações somam valores diferentes "
                     f"({fmt(so)}% e {fmt(sr)}%).** Sem normalizar, você compara "
                     "quantidades diferentes de ração, e a diferença de custo vai "
                     "refletir isso em vez da troca de ingredientes.")

        normalizar = False
        if parcial:
            normalizar = st.checkbox("Normalizar as duas formulações para 100%")
            if normalizar:
                st.info("**Base do cálculo.** Totais reescalados para 100%: os números "
                        "descrevem **a mistura apenas destes ingredientes**, como se "
                        "ela fosse a ração inteira.")
            else:
                st.info(f"**Base do cálculo.** As formulações somam {fmt(so)}% e "
                        f"{fmt(sr)}%. Os números são a **contribuição destes "
                        "ingredientes para a ração completa**, não o perfil da ração. "
                        "O custo é quanto eles custam por tonelada de ração pronta; "
                        "o restante não entra na conta.")

        fo = {c: st.session_state[f"o_{c}"] for c in ingredientes}
        fr = {c: st.session_state[f"r_{c}"] for c in ingredientes}
        if normalizar:
            fo, fr = normalizar_formulacao(fo), normalizar_formulacao(fr)

        co, mem_o = custo_formulacao(banco, fo, precos)
        cr, mem_r = custo_formulacao(banco, fr, precos)
        sufixo = "parcial, por tonelada" if (parcial and not normalizar) else "por tonelada"
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Custo Original", brl(co) if co is not None else "N/D",
                      sufixo, delta_color="off")
            mostrar_memorial(mem_o)
        with k2:
            st.metric("Custo Reestruturada", brl(cr) if cr is not None else "N/D",
                      sufixo, delta_color="off")
            mostrar_memorial(mem_r)
        if co is not None and cr is not None:
            dif = co - cr                                   # positivo = economia
            pct = dif / co * 100 if co else 0
            k3.metric("Diferença", brl(dif) if dif >= 0 else f"−{brl(abs(dif))}",
                      "🟢 mais barata" if dif >= 0 else "🔴 mais cara",
                      delta_color="normal" if dif >= 0 else "inverse")
            k4.metric("Diferença %", f"{'' if dif >= 0 else '−'}{fmt(abs(pct))}%",
                      "🟢 economia" if dif >= 0 else "🔴 aumento de custo",
                      delta_color="normal" if dif >= 0 else "inverse")
            with k3.expander("Como essa conta é feita?"):
                st.markdown(f"Custo original {brl(co)} menos custo reestruturado "
                            f"{brl(cr)} = **{brl(dif)}** por tonelada.")
                st.markdown("Valor positivo = reestruturada mais barata. "
                            "Negativo = mais cara. O sinal não é invertido.")

        lista = params_visiveis()
        pad_sim = [p for p in lista if chave(p) in
                   ("PROTEINA BRUTA", "FIBRA BRUTA", "FDN", "CALCIO")]
        if param_energia:
            pad_sim.append(param_energia)
        with st.expander("Comparação Nutricional", expanded=True):
            par_sim = st.multiselect("Parâmetros a exibir", lista,
                                     default=pad_sim or lista[:5], key="par_sim")
        if parcial and not normalizar:
            st.caption("Valores = pontos que estes ingredientes aportam à ração "
                       "completa. Exceto PDR e PNDR, que são razões sobre a "
                       "proteína e não dependem da base.")
        if par_sim:
            cA, cB = st.columns(2)
            memoriais = {}
            for i, p in enumerate(par_sim):
                va, un, ma = nutricao_formulacao(banco, fo, p)
                vb, _, mb = nutricao_formulacao(banco, fr, p)
                memoriais[p] = (ma, mb)
                with (cA if i % 2 == 0 else cB):
                    st.markdown(f"**{p}** &nbsp;<span style='color:#94a3b8;font-size:12.5px'>"
                                f"({un} — base {banco.base(p)})</span>",
                                unsafe_allow_html=True)
                    st.markdown(bloco_barras([("Original", va, COR_ORIGINAL, ""),
                                              ("Reestruturada", vb, COR_REESTRUTURADA, "")]),
                                unsafe_allow_html=True)
                    if va is not None and vb is not None:
                        d = vb - va
                        dp = d / va * 100 if va else None
                        sinal = "+" if d > 0 else ""
                        txt = f"{sinal}{fmt(d)} {un}"
                        if dp is not None:
                            txt += f" ({sinal}{fmt(dp)}%)"
                        cor = "green" if d > 0 else "red" if d < 0 else "gray"
                        st.markdown(f":{cor}[{txt}]")
                    else:
                        st.caption("diferença N/D")
            alvo = st.selectbox("Auditar o cálculo de qual parâmetro?", list(memoriais))
            a1, a2 = st.columns(2)
            with a1:
                st.markdown("**Formulação Original**")
                memoriais[alvo][0].render()
            with a2:
                st.markdown("**Formulação Reestruturada**")
                memoriais[alvo][1].render()

# ------------------------------- ABA 3 ---------------------------------------
with tab3:
    st.subheader("Banco de Dados Nutricional")
    st.caption(f"Leitura em {banco.lido_em.strftime('%d/%m/%Y %H:%M:%S')} · "
               f"{len(banco.meta_param)} parâmetros · {len(banco.commodities)} commodities")
    linhas = []
    for meta in banco.meta_param.values():
        lin = {"Parâmetro": meta["nome"], "Unidade": meta["unidade"],
               "Base": meta["base"], "Categoria": meta["categoria"]}
        for com in banco.commodities:
            v = banco.get(com, meta["nome"])
            lin[com] = "N/D" if not v.disponivel else v.fmt() + (" *" if v.provisorio else "")
        linhas.append(lin)
    st.dataframe(linhas, use_container_width=True, hide_index=True)
    st.caption("\\* dado ainda marcado como PROVISÓRIO na aba FONTES.")

    if not banco.df_fontes.empty:
        st.markdown("#### Fontes e Status")
        df_f = banco.df_fontes.copy()
        cols = {chave(c): c for c in df_f.columns}
        if cols.get("STATUS") and st.checkbox("Mostrar apenas dados provisórios", value=True):
            df_f = df_f[df_f[cols["STATUS"]].apply(lambda x: chave(x) != "VERIFICADO")]
        st.dataframe(df_f, use_container_width=True, hide_index=True)
