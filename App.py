import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser a primeira linha do Streamlit)
st.set_page_config(page_title="Nutre Compare Pro", layout="wide", page_icon="🌾")

# 2. INJEÇÃO DE CSS (Para deixar o layout igual ao protótipo que aprovamos)
st.markdown("""
    <style>
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .metric-title { color: #64748b; font-size: 14px; font-weight: 600; margin-bottom: 8px; }
    .metric-value { color: #0f172a; font-size: 28px; font-weight: 800; }
    .didactic-box { background-color: #f8fafc; border-top: 1px solid #f1f5f9; padding: 15px; border-radius: 10px; margin-top: 10px; font-family: monospace; font-size: 13px; color: #475569; }
    </style>
""", unsafe_allow_html=True)

# 3. LINKS DO GOOGLE SHEETS (Substitua pelos seus links terminados em export?format=csv)
# O "gid=0" geralmente é a primeira aba. Vá na segunda aba, copie o link e coloque aqui.
URL_ABA_GERAL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTUFXCmvEtY4bwfoaz3ux21qc41BAfNT1K2QRysfW6qZ2xaAJOsmXEFmzw2ZWH1KeBy1yfsqtpETrtt/pub?output=csv"
URL_ABA_AMINOACIDOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTUFXCmvEtY4bwfoaz3ux21qc41BAfNT1K2QRysfW6qZ2xaAJOsmXEFmzw2ZWH1KeBy1yfsqtpETrtt/pub?output=csv" # <--- TROQUE O GID DESTE LINK

# 4. FUNÇÕES DE CARREGAMENTO DE DADOS
@st.cache_data(ttl=60)
def load_data(url):
    try:
        return pd.read_csv(url)
    except:
        # Retorna um DataFrame vazio se der erro, para não quebrar o app
        return pd.DataFrame()

def clean_number(val):
    if pd.isna(val) or val == "": return 0.0
    val_str = str(val).replace('Mcal/kg', '').replace('%', '').replace(',', '.').strip()
    try: return float(val_str)
    except: return 0.0

# 5. CARREGAR OS DADOS DAS DUAS ABAS
df_geral = load_data(URL_ABA_GERAL)
df_amino = load_data(URL_ABA_AMINOACIDOS)

# --- CABEÇALHO ---
st.title("🌾 Nutre Compare Pro")
st.markdown("Plataforma de análise e soluções econômicas: **Farelo de Soja vs. DDGS**")

# --- BARRA LATERAL (CONFIGURAÇÕES GERAIS) ---
st.sidebar.header("⚙️ Configurações da Análise")
especie = st.sidebar.selectbox("Filtro Zootécnico (Espécie)", ["Bovino", "Suínos", "Aves"])
praca = st.sidebar.text_input("Praça de Cotação", value="Campinas/SP")
embalagem = st.sidebar.selectbox("Formato de Comercialização", ["A Granel", "Ensacado"])

st.sidebar.markdown("---")
st.sidebar.header("💰 Cotações do Dia (R$/ton)")
preco_soja = st.sidebar.number_input(f"Farelo de Soja ({embalagem})", min_value=0.0, value=2200.0, step=50.0)
preco_ddgs = st.sidebar.number_input(f"DDGS ({embalagem})", min_value=0.0, value=1400.0, step=50.0)

# --- EXTRAÇÃO DE VARIÁVEIS (MOCK SE A TABELA FALHAR) ---
# Aqui tentamos pegar da tabela. Se a tabela não tiver os nomes exatos, usamos valores padrão.
try:
    pb_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Proteína Bruta', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
    pb_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Proteína Bruta', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
    
    linha_energia = f"Energia Metabolizável - {especie}" if especie != "Bovino" else "Energia Metabolizável - Bovino"
    energia_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains(linha_energia, case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
    energia_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains(linha_energia, case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
except:
    pb_soja, pb_ddgs = 46.0, 35.0
    energia_soja, energia_ddgs = 3.2, 3.42

# --- ABAS PRINCIPAIS ---
tab1, tab2 = st.tabs(["📊 Custo-Benefício & Nutrição", "⚖️ Simulador de Mistura"])

with tab1:
    st.subheader(f"Análise Econômica - Praça: {praca}")
    col1, col2, col3 = st.columns(3)
    
    # --- CÁLCULOS ---
    kg_pb_soja = pb_soja * 10
    kg_pb_ddgs = pb_ddgs * 10
    custo_pb_soja = preco_soja / kg_pb_soja if kg_pb_soja > 0 else 0
    custo_pb_ddgs = preco_ddgs / kg_pb_ddgs if kg_pb_ddgs > 0 else 0
    viabilidade = preco_ddgs / preco_soja if preco_soja > 0 else 0

    # --- CARD 1: CUSTO SOJA ---
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Custo por kg de PB (Soja)</div>
                <div class="metric-value">R$ {custo_pb_soja:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
        with st.expander("ℹ️ Como essa conta é feita?"):
            st.markdown(f"""
            **1. Kgs de Proteína por Tonelada:**  
            `{pb_soja}% × 10 = {kg_pb_soja} kg de PB pura`
            
            **2. Divisão do Custo:**  
            `R$ {preco_soja} ÷ {kg_pb_soja} kg = R$ {custo_pb_soja:.2f}`
            """)

    # --- CARD 2: CUSTO DDGS ---
    with col2:
        dif_custo = ((custo_pb_ddgs/custo_pb_soja)-1)*100 if custo_pb_soja > 0 else 0
        cor_dif = "green" if dif_custo < 0 else "red"
        st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid #f59e0b;">
                <div class="metric-title">Custo por kg de PB (DDGS)</div>
                <div class="metric-value">R$ {custo_pb_ddgs:.2f} <span style="font-size:14px; color:{cor_dif}">({dif_custo:.1f}% vs Soja)</span></div>
            </div>
        """, unsafe_allow_html=True)
        with st.expander("ℹ️ Como essa conta é feita?"):
            st.markdown(f"""
            **1. Kgs de Proteína por Tonelada:**  
            `{pb_ddgs}% × 10 = {kg_pb_ddgs} kg de PB pura`
            
            **2. Divisão do Custo:**  
            `R$ {preco_ddgs} ÷ {kg_pb_ddgs} kg = R$ {custo_pb_ddgs:.2f}`
            """)

    # --- CARD 3: VIABILIDADE ---
    with col3:
        status_viabilidade = "🟢 Favorável" if viabilidade < 0.75 else ("🟡 Atenção" if viabilidade < 0.82 else "🔴 Desfavorável")
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Relação de Preço (DDGS/Soja)</div>
                <div class="metric-value">{(viabilidade*100):.1f}% <span style="font-size:16px;">{status_viabilidade}</span></div>
            </div>
        """, unsafe_allow_html=True)
        with st.expander("ℹ️ Regra de Bolso"):
            st.markdown(f"""
            **Fórmula:** `(R$ {preco_ddgs} ÷ R$ {preco_soja}) × 100 = {(viabilidade*100):.1f}%`
            
            *Nutricionistas recomendam comprar o DDGS se essa porcentagem ficar abaixo de 75% a 80%, para compensar o menor volume de proteína.*
            """)

    st.markdown("---")
    
    # --- GRÁFICOS DE BARRAS COMPARATIVAS (HTML/CSS INJETADO) ---
    def render_bar(label, soja_val, ddgs_val, max_val):
        soja_pct = (soja_val / max_val) * 100
        ddgs_pct = (ddgs_val / max_val) * 100
        
        # Etiqueta de vantagem
        if soja_val > ddgs_val: badge = f"<span style='float:right; font-size:10px; background:#dcfce7; color:#166534; padding:2px 6px; border-radius:4px;'>Soja +{soja_val-ddgs_val:.1f}</span>"
        elif ddgs_val > soja_val: badge = f"<span style='float:right; font-size:10px; background:#fef3c7; color:#92400e; padding:2px 6px; border-radius:4px;'>DDGS +{ddgs_val-soja_val:.1f}</span>"
        else: badge = ""

        return f"""
        <div style="margin-bottom: 20px; font-family: sans-serif;">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <strong style="color:#334155; font-size:14px;">{label}</strong>
                {badge}
            </div>
            
            <!-- Barra Soja -->
            <div style="display:flex; align-items:center; margin-bottom:4px;">
                <div style="width:50px; font-size:12px; color:#15803d; font-weight:bold; text-align:right; margin-right:10px;">{soja_val}%</div>
                <div style="flex:1; background:#f1f5f9; border-radius:10px; height:12px;">
                    <div style="width:{soja_pct}%; background:#10b981; height:10px; border-radius:10px;"></div>
                </div>
            </div>
            
            <!-- Barra DDGS -->
            <div style="display:flex; align-items:center;">
                <div style="width:50px; font-size:12px; color:#b45309; font-weight:bold; text-align:right; margin-right:10px;">{ddgs_val}%</div>
                <div style="flex:1; background:#f1f5f9; border-radius:10px; height:12px;">
                    <div style="width:{ddgs_pct}%; background:#f59e0b; height:10px; border-radius:10px;"></div>
                </div>
            </div>
        </div>
        """

    st.subheader("Comparativo Nutricional Direto")
    # Colocando os gráficos em 2 colunas
    bcol1, bcol2 = st.columns(2)
    
    with bcol1:
        st.markdown(render_bar("Proteína Bruta (%)", pb_soja, pb_ddgs, 60), unsafe_allow_html=True)
        # Extraindo dados brutos (usando valores fallback se der erro)
        try:
            ms_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Matéria Seca', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
            ms_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Matéria Seca', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
        except: ms_soja, ms_ddgs = 89, 90
        st.markdown(render_bar("Matéria Seca (%)", ms_soja, ms_ddgs, 100), unsafe_allow_html=True)
        
        try:
            pndr_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('PNDR', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
            pndr_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('PNDR', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
        except: pndr_soja, pndr_ddgs = 35, 60
        st.markdown(render_bar("PNDR - Bypass (% da PB)", pndr_soja, pndr_ddgs, 80), unsafe_allow_html=True)

    with bcol2:
        try:
            ee_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Extrato Etéreo', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
            ee_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('Extrato Etéreo', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
        except: ee_soja, ee_ddgs = 1.5, 7
        st.markdown(render_bar("Extrato Etéreo (%)", ee_soja, ee_ddgs, 15), unsafe_allow_html=True)
        
        try:
            fdn_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('FDN', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
            fdn_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('FDN', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
        except: fdn_soja, fdn_ddgs = 11, 40
        st.markdown(render_bar("FDN - Fibra (%)", fdn_soja, fdn_ddgs, 60), unsafe_allow_html=True)
        
        try:
            ndt_soja = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('NDT', case=False, na=False), 'Farelo de Soja (46-48%)'].values[0])
            ndt_ddgs = clean_number(df_geral.loc[df_geral['Parâmetro Nutricional'].str.contains('NDT', case=False, na=False), 'DDGS de Milho(inpasa)'].values[0])
        except: ndt_soja, ndt_ddgs = 75, 89
        st.markdown(render_bar("NDT - Energia Total (%)", ndt_soja, ndt_ddgs, 100), unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Aminoácidos e Minerais")
    # Gráficos de Aminoácidos
    acol1, acol2 = st.columns(2)
    with acol1:
        st.markdown(render_bar("Lisina (%)", 2.81, 1.15, 4.0), unsafe_allow_html=True)
        st.markdown(render_bar("Metionina (%)", 0.55, 0.53, 1.0), unsafe_allow_html=True)
    with acol2:
        st.markdown(render_bar("Cálcio - Ca (%)", 0.20, 0.10, 0.5), unsafe_allow_html=True)
        st.markdown(render_bar("Fósforo Total - P (%)", 0.55, 0.89, 1.5), unsafe_allow_html=True)
        
    st.info("⚡ **Vantagem do Fósforo:** O DDGS possui um nível de Fósforo significativamente maior que a soja. Na prática, isso permite reduzir a inclusão de Fosfato Bicálcico na ração, gerando grande economia.")


# --- ABA 2: SIMULADOR ---
with tab2:
    st.subheader(f"Simulador de Mistura (Blending) - {especie}")
    
    with st.expander("ℹ️ Como a Economia é calculada?"):
        st.markdown("""
        **1.** Pegamos o preço da tonelada de 100% Soja.  
        **2.** Calculamos o custo ponderado da nova mistura: `(Preço Soja × % Soja) + (Preço DDGS × % DDGS)`  
        **3.** Subtraímos o custo da mistura do custo da Soja pura para achar a **Economia por Tonelada**.
        """)
    
    perc_ddgs = st.slider("Porcentagem de DDGS (O restante será Soja)", 0, 100, 30, step=5)
    perc_soja = 100 - perc_ddgs
    
    pb_mistura = (pb_soja * (perc_soja/100)) + (pb_ddgs * (perc_ddgs/100))
    energia_mistura = (energia_soja * (perc_soja/100)) + (energia_ddgs * (perc_ddgs/100))
    preco_mistura = (preco_soja * (perc_soja/100)) + (preco_ddgs * (perc_ddgs/100))
    economia_ton = preco_soja - preco_mistura

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1: st.metric("Mistura (Soja/DDGS)", f"{perc_soja}% / {perc_ddgs}%")
    with mcol2: st.metric("PB da Mistura", f"{pb_mistura:.1f}%")
    with mcol3: st.metric(f"Energia ({especie})", f"{energia_mistura:.2f} Mcal")
    with mcol4: st.metric("Economia vs 100% Soja", f"R$ {economia_ton:.2f} /t")
    
    # Histórico
    if 'historico' not in st.session_state:
        st.session_state.historico = []

    if st.button("💾 Salvar Simulação"):
        st.session_state.historico.append({
            "Mistura": f"{perc_soja}% Soja / {perc_ddgs}% DDGS",
            "Espécie": especie,
            "PB Final (%)": round(pb_mistura, 1),
            "Custo Final (R$/t)": round(preco_mistura, 2),
            "Economia (R$/t)": round(economia_ton, 2)
        })
        st.success("Salvo com sucesso!")

    if st.session_state.historico:
        st.markdown("### Histórico de Simulações")
        st.dataframe(pd.DataFrame(st.session_state.historico), use_container_width=True)
        if st.button("Limpar Histórico"):
            st.session_state.historico = []
            st.rerun()
