import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Nutre Compare Pro", layout="wide", page_icon="🌾")

# Função para carregar os dados da sua planilha
@st.cache_data(ttl=60)
def load_data():
    # URL de exportação CSV da sua aba "Comparativo Geral"
    url_geral = "https://docs.google.com/spreadsheets/d/17Aa0wv-LxqQwx9gicdBM8ygbrBOBIF-cQny8eRkYKVE/export?format=csv&gid=0"
    df = pd.read_csv(url_geral)
    return df

# Função para limpar e converter números (trata vírgulas e textos como Mcal/kg)
def clean_number(val):
    if pd.isna(val): return 0.0
    val_str = str(val).replace('Mcal/kg', '').replace(',', '.').strip()
    try:
        return float(val_str)
    except:
        return 0.0

st.title("🌾 Nutre Compare Pro")
st.markdown("Plataforma de análise e viabilidade econômica: **Farelo de Soja vs. DDGS**")

try:
    df_raw = load_data()
    
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
    # Extrair os valores nutricionais essenciais da tabela
    pb_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Proteína Bruta (PB) %', 'Farelo de Soja (46-48%)'].values[0])
    pb_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'] == 'Proteína Bruta (PB) %', 'DDGS de Milho(inpasa)'].values[0])
    
    # Filtrar a energia dependendo da espécie selecionada
    linha_energia = f"Energia Metabolizável - {especie}" if especie != "Bovino" else "Energia Metabolizável - Bovino"
    try:
        energia_soja = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'].str.contains(linha_energia, na=False), 'Farelo de Soja (46-48%)'].values[0])
        energia_ddgs = clean_number(df_raw.loc[df_raw['Parâmetro Nutricional'].str.contains(linha_energia, na=False), 'DDGS de Milho(inpasa)'].values[0])
    except:
        energia_soja, energia_ddgs = 0.0, 0.0

    # --- ABA 1: VIABILIDADE E CUSTO ---
    tab1, tab2, tab3 = st.tabs(["📊 Custo-Benefício", "⚖️ Simulador de Substituição", "📋 Tabela Nutricional (Raw)"])
    
    with tab1:
        st.subheader(f"Análise Econômica - Praça: {praca} | Formato: {embalagem}")
        
        col1, col2, col3 = st.columns(3)
        
        # Cálculos de Custo por Ponto de Proteína
        custo_pb_soja = preco_soja / (pb_soja * 10) if pb_soja > 0 else 0
        custo_pb_ddgs = preco_ddgs / (pb_ddgs * 10) if pb_ddgs > 0 else 0
        
        col1.metric("Custo por Ponto de PB (Soja)", f"R$ {custo_pb_soja:.2f}")
        col2.metric("Custo por Ponto de PB (DDGS)", f"R$ {custo_pb_ddgs:.2f}", 
                    delta=f"{((custo_pb_ddgs/custo_pb_soja)-1)*100:.1f}% vs Soja", delta_color="inverse")
        
        # Regra de Bolso para DDGS
        viabilidade = preco_ddgs / preco_soja
        status_viabilidade = "🟢 Favorável para DDGS" if viabilidade < 0.75 else ("🟡 Atenção (Equilíbrio)" if viabilidade < 0.82 else "🔴 Desfavorável para DDGS")
        col3.metric("Relação de Preço (DDGS/Soja)", f"{viabilidade*100:.1f}%", status_viabilidade)
        st.info("💡 **Dica Prática:** Historicamente, o DDGS é considerado excelente substituto econômico quando seu preço por tonelada representa menos de 75% a 80% do valor do Farelo de Soja.")

    # --- ABA 2: SIMULADOR DE BLENDING (MISTURA) ---
    with tab2:
        st.subheader(f"Simulador de Mistura Protéica para {especie}")
        
        # Controle Deslizante (Slider)
        perc_ddgs = st.slider("Porcentagem de DDGS na mistura (O restante será Farelo de Soja)", 0, 100, 30, step=5)
        perc_soja = 100 - perc_ddgs
        
        # Cálculos da Mistura
        pb_mistura = (pb_soja * (perc_soja/100)) + (pb_ddgs * (perc_ddgs/100))
        energia_mistura = (energia_soja * (perc_soja/100)) + (energia_ddgs * (perc_ddgs/100))
        preco_mistura = (preco_soja * (perc_soja/100)) + (preco_ddgs * (perc_ddgs/100))
        economia_ton = preco_soja - preco_mistura
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Proteína Bruta da Mistura", f"{pb_mistura:.1f}%")
        col_m2.metric(f"Energia ({especie})", f"{energia_mistura:.2f} Mcal")
        col_m3.metric("Custo da Mistura (R$/ton)", f"R$ {preco_mistura:.2f}")
        col_m4.metric("Economia vs 100% Soja", f"R$ {economia_ton:.2f} / ton", "Ganho Financeiro")

        # Gerenciamento de Histórico usando Session State
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
            st.markdown("### 📋 Histórico de Simulações Salvas")
            df_hist = pd.DataFrame(st.session_state.historico)
            st.dataframe(df_hist, use_container_width=True)
            
            if st.button("Limpar Histórico"):
                st.session_state.historico = []
                st.rerun()

    # --- ABA 3: TABELA NUTRICIONAL DA PLANILHA ---
    with tab3:
        st.subheader("Base de Dados (Google Sheets)")
        st.dataframe(df_raw, use_container_width=True)

except Exception as e:
    st.error(f"Erro ao carregar os dados. Detalhes: {e}")
