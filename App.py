import streamlit as st
import pandas as pd

# Configuração da Página
st.set_page_config(page_title="Nutre Compare Pro", layout="wide", page_icon="🌾")

# ==========================================
# LINKS DA SUA PLANILHA (COLE AQUI)
# ==========================================
URL_ABA_GERAL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTUFXCmvEtY4bwfoaz3ux21qc41BAfNT1K2QRysfW6qZ2xaAJOsmXEFmzw2ZWH1KeBy1yfsqtpETrtt/pub?output=csv"
URL_ABA_AMINOACIDOS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTUFXCmvEtY4bwfoaz3ux21qc41BAfNT1K2QRysfW6qZ2xaAJOsmXEFmzw2ZWH1KeBy1yfsqtpETrtt/pub?output=csv"

@st.cache_data(ttl=60)
def load_data():
    df_geral = pd.read_csv(URL_ABA_GERAL)
    # Tenta carregar aminoácidos, se falhar cria um dataframe vazio para não quebrar
    try:
        df_amino = pd.read_csv(URL_ABA_AMINOACIDOS)
    except:
        df_amino = pd.DataFrame()
    return df_geral, df_amino

def clean_number(val):
    if pd.isna(val): return 0.0
    val_str = str(val).replace('Mcal/kg', '').replace(',', '.').strip()
    try: return float(val_str)
    except: return 0.0

# FUNÇÃO CORRIGIDA: SEM ESPAÇOS NO INÍCIO PARA NÃO VIRAR BLOCO DE CÓDIGO
def render_bar(val_soja, val_ddgs, max_val):
    pct_soja = min((val_soja / max_val) * 100, 100) if max_val > 0 else 0
    pct_ddgs = min((val_ddgs / max_val) * 100, 100) if max_val > 0 else 0
    
    html = f"""<div style="margin-bottom: 15px;">
<div style="display:flex; align-items:center; margin-bottom:4px;">
<div style="width:50px; font-size:14px; color:#4ade80; font-weight:bold;">Soja</div>
<div style="flex:1; background:#334155; border-radius:10px; height:18px; overflow:hidden; margin-right: 10px;">
<div style="width:{pct_soja}%; background:#10b981; height:100%;"></div>
</div>
<div style="width:40px; font-size:14px; text-align:right;">{val_soja}</div>
</div>
<div style="display:flex; align-items:center;">
<div style="width:50px; font-size:14px; color:#fbbf24; font-weight:bold;">DDGS</div>
<div style="flex:1; background:#334155; border-radius:10px; height:18px; overflow:hidden; margin-right: 10px;">
<div style="width:{pct_ddgs}%; background:#f59e0b; height:100%;"></div>
</div>
<div style="width:40px; font-size:14px; text-align:right;">{val_ddgs}</div>
</div>
</div>"""
    return html

st.title("🌾 Nutre Compare Pro")
st.markdown("Plataforma de análise e soluções econômicas: **Farelo de Soja vs. DDGS**")

try:
    df_raw, df_amino = load_data()
    
    # --- BARRA LATERAL (CONFIGURAÇÕES GERAIS) ---
    st.sidebar.header("⚙️ Configurações da Análise")
    
    especie = st.sidebar.selectbox("Filtro Zootécnico (Espécie)", ["Bovino", "Suínos", "Aves"])
    praca = st.sidebar.text_input("Praça de Cotação", value="Campinas/SP")
    embalagem = st.sidebar.selectbox("Formato de Comercialização", ["A Granel", "Ensacado"])
    
    st.sidebar.markdown("---")
    st.sidebar.header("💰 Cotações do Dia (R$/ton)")
    preco_soja = st.sidebar.number_input(f"Farelo de Soja ({embalagem})", min_value=0.0, value=2200.0, step=50.0)
    preco_ddgs = st.sidebar.number_input(f"DDGS ({embalagem})", min_value=0.0, value=1400.0, step=50.0)

    # --- PROCESSAMENTO DOS DADOS ---
    pb_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Proteína Bruta (PB) %', 'Farelo de Soja (46-48%)'].values[0])
    pb_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Proteína Bruta (PB) %', 'DDGS de Milho(inpasa)'].values[0])
    
    ee_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Extrato Etéreo (EE) %', 'Farelo de Soja (46-48%)'].values[0])
    ee_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Extrato Etéreo (EE) %', 'DDGS de Milho(inpasa)'].values[0])

    ms_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Matéria Seca (MS) %', 'Farelo de Soja (46-48%)'].values[0])
    ms_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Matéria Seca (MS) %', 'DDGS de Milho(inpasa)'].values[0])

    fdn_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'FDN %', 'Farelo de Soja (46-48%)'].values[0])
    fdn_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'FDN %', 'DDGS de Milho(inpasa)'].values[0])
    
    linha_energia = f"Energia Metabolizável - {especie}" if especie != "Bovino" else "Energia Metabolizável - Bovino"
    try:
        energia_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'].str.contains(linha_energia, na=False), 'Farelo de Soja (46-48%)'].values[0])
        energia_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'].str.contains(linha_energia, na=False), 'DDGS de Milho(inpasa)'].values[0])
    except:
        energia_soja, energia_ddgs = 0.0, 0.0

    # --- ABA 1: VIABILIDADE E CUSTO ---
    tab1, tab2, tab3 = st.tabs(["📊 Custo-Benefício & Nutrição", "⚖️ Simulador de Substituição", "📋 Base de Dados"])
    
    with tab1:
        st.subheader(f"Análise Econômica - Praça: {praca} | Formato: {embalagem}")
        
        col1, col2, col3 = st.columns(3)
        
        custo_pb_soja = preco_soja / (pb_soja * 10) if pb_soja > 0 else 0
        custo_pb_ddgs = preco_ddgs / (pb_ddgs * 10) if pb_ddgs > 0 else 0
        
        col1.metric("Custo por kg de PB (Soja)", f"R$ {custo_pb_soja:.2f}")
        with col1.expander("ℹ️ Como essa conta é feita?"):
            st.write(f"Preço (R$ {preco_soja}) dividido pelos kg de Proteína em 1 tonelada ({pb_soja} * 10 = {pb_soja*10} kg).")

        col2.metric("Custo por kg de PB (DDGS)", f"R$ {custo_pb_ddgs:.2f}", 
                    delta=f"{((custo_pb_ddgs/custo_pb_soja)-1)*100:.1f}% vs Soja", delta_color="inverse")
        with col2.expander("ℹ️ Como essa conta é feita?"):
            st.write(f"Preço (R$ {preco_ddgs}) dividido pelos kg de Proteína em 1 tonelada ({pb_ddgs} * 10 = {pb_ddgs*10} kg).")

        viabilidade = preco_ddgs / preco_soja
        status_viabilidade = "🟢 Favorável para DDGS" if viabilidade < 0.75 else ("🟡 Atenção (Equilíbrio)" if viabilidade < 0.82 else "🔴 Desfavorável para DDGS")
        col3.metric("Relação de Preço (DDGS/Soja)", f"{viabilidade*100:.1f}%", status_viabilidade)
        with col3.expander("ℹ️ Regra de Ouro"):
            st.write("Se o preço do DDGS for até 75%-80% do preço da Soja, ele é financeiramente vantajoso na dieta.")

        st.markdown("---")
        st.subheader("Comparativo Nutricional Direto")
        
        col_bar1, col_bar2 = st.columns(2)
        
        with col_bar1:
            st.markdown("**Proteína Bruta (%)**")
            st.markdown(render_bar(pb_soja, pb_ddgs, 60), unsafe_allow_html=True)
            
            st.markdown("**Matéria Seca (%)**")
            st.markdown(render_bar(ms_soja, ms_ddgs, 100), unsafe_allow_html=True)
            
        with col_bar2:
            st.markdown("**Extrato Etéreo (Energia/Óleo) (%)**")
            st.markdown(render_bar(ee_soja, ee_ddgs, 15), unsafe_allow_html=True)
            
            st.markdown("**FDN (Fibra) (%)**")
            st.markdown(render_bar(fdn_soja, fdn_ddgs, 50), unsafe_allow_html=True)

    # --- ABA 2: SIMULADOR DE BLENDING ---
    with tab2:
        st.subheader(f"Simulador de Mistura para {especie}")
        
        perc_ddgs = st.slider("Porcentagem de DDGS na mistura (O restante será Farelo de Soja)", 0, 100, 30, step=5)
        perc_soja = 100 - perc_ddgs
        
        pb_mistura = (pb_soja * (perc_soja/100)) + (pb_ddgs * (perc_ddgs/100))
        energia_mistura = (energia_soja * (perc_soja/100)) + (energia_ddgs * (perc_ddgs/100))
        preco_mistura = (preco_soja * (perc_soja/100)) + (preco_ddgs * (perc_ddgs/100))
        economia_ton = preco_soja - preco_mistura
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Proteína Bruta (Mistura)", f"{pb_mistura:.1f}%")
        col_m2.metric(f"Energia ({especie})", f"{energia_mistura:.2f} Mcal")
        col_m3.metric("Custo (R$/ton)", f"R$ {preco_mistura:.2f}")
        col_m4.metric("Economia vs 100% Soja", f"R$ {economia_ton:.2f} / ton")

        if 'historico' not in st.session_state:
            st.session_state.historico = []

        if st.button("💾 Salvar Simulação no Histórico"):
            st.session_state.historico.append({
                "Mistura": f"{perc_soja}% Soja / {perc_ddgs}% DDGS",
                "Espécie": especie,
                "PB (%)": round(pb_mistura, 1),
                "Custo (R$/t)": round(preco_mistura, 2),
                "Economia vs Soja (R$/t)": round(economia_ton, 2)
            })
            st.success("Simulação salva!")

        if st.session_state.historico:
            st.markdown("### 📋 Histórico")
            st.dataframe(pd.DataFrame(st.session_state.historico), use_container_width=True)
            if st.button("Limpar Histórico"):
                st.session_state.historico = []
                st.rerun()

    # --- ABA 3: DADOS ---
    with tab3:
        st.subheader("Base de Dados (Google Sheets)")
        st.dataframe(df_raw, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar os dados. Detalhes: {e}")
