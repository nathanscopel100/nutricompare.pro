import streamlit as st
import pandas as pd
import numpy as np

# Configuração da Página
st.set_page_config(page_title="Nutre Compare Pro v2", layout="wide", page_icon="🌾")

# ==========================================
# GESTÃO DE DADOS (SIMULANDO A NOVA GOOGLE SHEET)
# ==========================================
# Para conectar sua planilha real futuramente, basta usar pd.read_csv(URL)
# Aqui, criamos uma base "mock" auditável, com dados zootécnicos reais de literatura (Rostagno et al., NRC)
@st.cache_data(ttl=60)
def load_data():
    data = {
        'Parâmetro Nutricional': ['Proteína Bruta (PB)', 'Matéria Seca (MS)', 'Extrato Etéreo (EE)', 'FDN', 'Fibra Bruta (FB)', 'NDT (Energia)', 'Energia Metabolizável - Aves', 'Energia Metabolizável - Suínos', 'Cálcio (Ca)', 'Fósforo Total (P)'],
        'Unidade': ['%', '%', '%', '%', '%', '%', 'Mcal/kg', 'Mcal/kg', '%', '%'],
        'Farelo de Soja': [46.0, 89.0, 1.5, 14.0, 6.0, 81.0, 2.23, 3.20, 0.25, 0.60],
        'DDGS': [30.0, 89.0, 8.0, 35.0, 8.0, 84.0, 2.70, 3.30, 0.05, 0.85],
        'Milho': [8.0, 88.0, 3.5, 12.0, 2.0, 88.0, 3.38, 3.40, 0.03, 0.28],
        'Sorgo': [9.0, 88.0, 2.8, 15.0, 2.5, 83.0, 3.25, 3.30, 0.03, 0.28],
        'Farelo de Algodão': [38.0, 89.0, 1.5, 28.0, 14.0, 65.0, 1.80, 2.40, 0.20, 1.00],
        'Caroço de Algodão': [23.0, 90.0, 18.0, 44.0, 24.0, 95.0, np.nan, np.nan, 0.15, 0.60] # nan simula N/D
    }
    df = pd.DataFrame(data)
    return df

# ==========================================
# FUNÇÕES CORE & MATEMÁTICA
# ==========================================
def clean_number(val):
    if pd.isna(val) or val == '' or val == 'N/D': return np.nan
    try: return float(str(val).replace(',', '.').strip())
    except: return np.nan

def get_nutrient(df, commodity, param):
    try:
        val = df.loc[df['Parâmetro Nutricional'] == param, commodity].values[0]
        return clean_number(val)
    except:
        return np.nan

def get_unit(df, param):
    try: return df.loc[df['Parâmetro Nutricional'] == param, 'Unidade'].values[0]
    except: return ""

def calc_cost_per_nutrient(price_ton, nutrient_val, unit):
    if pd.isna(nutrient_val) or nutrient_val == 0: return np.nan, ""
    if unit == '%':
        kg_per_ton = nutrient_val * 10
        return price_ton / kg_per_ton, f"{nutrient_val} * 10 = {kg_per_ton} kg/ton"
    elif unit == 'Mcal/kg':
        mcal_per_ton = nutrient_val * 1000
        return price_ton / mcal_per_ton, f"{nutrient_val} * 1000 = {mcal_per_ton} Mcal/ton"
    return np.nan, ""

# Paleta de cores dinâmica para as barras HTML
COLORS = ['#10b981', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6', '#14b8a6', '#f43f5e', '#eab308']

def render_dynamic_bar(commodities_dict, max_val, unit):
    html = '<div style="margin-bottom: 15px;">'
    for i, (comm, val) in enumerate(commodities_dict.items()):
        color = COLORS[i % len(COLORS)]
        if pd.isna(val):
            display_val = "N/D"
            pct = 0
        else:
            display_val = f"{val}{unit}"
            pct = min((val / max_val) * 100, 100) if max_val > 0 else 0
            
        html += f"""
        <div style="display:flex; align-items:center; margin-bottom:4px;">
            <div style="width:120px; font-size:12px; font-weight:bold; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{comm}">{comm}</div>
            <div style="flex:1; background:#334155; border-radius:10px; height:18px; overflow:hidden; margin-right: 10px;">
                <div style="width:{pct}%; background:{color}; height:100%;"></div>
            </div>
            <div style="width:50px; font-size:12px; text-align:right;">{display_val}</div>
        </div>
        """
    html += '</div>'
    return html

# ==========================================
# INTERFACE PRINCIPAL
# ==========================================
st.title("🌾 Nutre Compare Pro v2.0")
st.markdown("Plataforma Dinâmica de Análise Nutricional, Econômica e Substituição de Ingredientes")

df_raw = load_data()
all_commodities = [c for c in df_raw.columns if c not in ['Parâmetro Nutricional', 'Unidade']]
all_parameters = df_raw['Parâmetro Nutricional'].tolist()

# --- BARRA LATERAL ---
st.sidebar.header("⚙️ Configurações e Cotações")
praca = st.sidebar.text_input("Praça de Cotação", value="Campinas/SP")
embalagem = st.sidebar.selectbox("Formato", ["A Granel", "Ensacado"])

st.sidebar.markdown("---")
st.sidebar.header("💰 Cotações do Dia (R$/ton)")
prices = {}
for comm in all_commodities:
    # Valores default para facilitar o teste da ferramenta
    default_price = 1200.0 if comm == 'Milho' else (2200.0 if comm == 'Farelo de Soja' else (1400.0 if comm == 'DDGS' else 1000.0))
    prices[comm] = st.sidebar.number_input(f"{comm}", min_value=0.0, value=default_price, step=50.0)

tab1, tab2, tab3 = st.tabs(["📊 Custo-Benefício & Nutrição", "⚖️ Simulador de Substituição", "📋 Base de Dados"])

# ==========================================
# ABA 1: CUSTO-BENEFÍCIO & NUTRIÇÃO
# ==========================================
with tab1:
    st.subheader("1. Seleção de Commodities para Análise")
    selected_comms = st.multiselect(
        "Selecione os ingredientes que deseja comparar lado a lado:",
        options=all_commodities,
        default=['Farelo de Soja', 'DDGS', 'Milho']
    )
    
    if not selected_comms:
        st.warning("Selecione pelo menos uma commodity para visualizar os dados.")
    else:
        st.markdown("---")
        st.subheader("2. Análise Econômica por Nutriente")
        
        econ_param = st.selectbox("Selecione o parâmetro para análise de custo específico:", ['Proteína Bruta (PB)', 'Fibra Bruta (FB)', 'Energia Metabolizável - Aves', 'Energia Metabolizável - Suínos', 'NDT (Energia)'])
        econ_unit = get_unit(df_raw, econ_param)
        
        cols_econ = st.columns(len(selected_comms))
        for i, comm in enumerate(selected_comms):
            val_nutri = get_nutrient(df_raw, comm, econ_param)
            custo, math_str = calc_cost_per_nutrient(prices[comm], val_nutri, econ_unit)
            
            with cols_econ[i]:
                if pd.isna(custo):
                    st.metric(f"Custo/{econ_unit} ({comm})", "N/D")
                else:
                    st.metric(f"Custo/{econ_unit} ({comm})", f"R$ {custo:.4f}")
                with st.expander("ℹ️ Como é feito?"):
                    if pd.isna(custo):
                        st.write("Dado nutricional não disponível (N/D).")
                    else:
                        st.write(f"**Preço:** R$ {prices[comm]:.2f}/t")
                        st.write(f"**Nutriente:** {val_nutri} {econ_unit}")
                        st.write(f"**Em 1 tonelada:** {math_str}")
                        st.write(f"**Cálculo:** R$ {prices[comm]:.2f} ÷ {math_str.split('=')[1].strip()} = R$ {custo:.4f}")

        st.markdown("---")
        st.subheader("3. Preço Limite / Teto (Regra de Substituição)")
        st.info("O sistema calcula automaticamente o Preço Limite quando há 2 ou mais commodities. Ele responde: 'Com base no ingrediente A, qual o valor máximo a pagar no ingrediente B?'")
        
        if len(selected_comms) >= 2:
            col_ref, col_eval, col_crit, col_btn = st.columns([2, 2, 2, 1])
            
            # Controle de inversão via session_state
            if 'inv_ref' not in st.session_state: st.session_state.inv_ref = selected_comms[0]
            if 'inv_eval' not in st.session_state: st.session_state.inv_eval = selected_comms[1]
            
            # Garantir que os itens no session_state ainda estão selecionados
            if st.session_state.inv_ref not in selected_comms: st.session_state.inv_ref = selected_comms[0]
            if st.session_state.inv_eval not in selected_comms: st.session_state.inv_eval = selected_comms[1]

            ref_comm = col_ref.selectbox("Commodity de Referência (Base):", selected_comms, index=selected_comms.index(st.session_state.inv_ref))
            eval_comm = col_eval.selectbox("Commodity a ser Avaliada:", selected_comms, index=selected_comms.index(st.session_state.inv_eval))
            crit_param = col_crit.selectbox("Critério de Comparação:", all_parameters)
            
            with col_btn:
                st.write("") # spacing
                st.write("")
                if st.button("🔄 Inverter"):
                    st.session_state.inv_ref, st.session_state.inv_eval = eval_comm, ref_comm
                    st.rerun()

            val_ref = get_nutrient(df_raw, ref_comm, crit_param)
            val_eval = get_nutrient(df_raw, eval_comm, crit_param)
            
            if pd.isna(val_ref) or pd.isna(val_eval) or val_ref == 0:
                st.error("Não é possível calcular o preço limite pois faltam dados nutricionais (N/D) para este parâmetro.")
            else:
                limite = prices[ref_comm] * (val_eval / val_ref)
                diferenca = limite - prices[eval_comm]
                
                col_res1, col_res2 = st.columns(2)
                status = f"🟢 Vantajoso comprar (Margem: R$ {diferenca:.2f}/t)" if prices[eval_comm] <= limite else f"🔴 Inviável (Ultrapassou R$ {abs(diferenca):.2f}/t)"
                col_res1.metric(f"Preço Limite ({eval_comm})", f"R$ {limite:.2f}", status, delta_color="normal" if prices[eval_comm] <= limite else "inverse")
                
                with col_res2.expander("ℹ️ Auditoria da Conta do Preço Limite"):
                    st.write(f"**Referência:** {ref_comm} (Preço: R$ {prices[ref_comm]} | Nutriente: {val_ref})")
                    st.write(f"**Avaliado:** {eval_comm} (Preço: R$ {prices[eval_comm]} | Nutriente: {val_eval})")
                    st.write(f"**Fórmula:** Preço Ref × (Nutriente Avaliado ÷ Nutriente Ref)")
                    st.write(f"**Cálculo:** {prices[ref_comm]} × ({val_eval} ÷ {val_ref}) = **R$ {limite:.2f}**")

        st.markdown("---")
        st.subheader("4. Comparativo Nutricional Dinâmico")
        selected_params = st.multiselect("Selecione os parâmetros que deseja visualizar:", all_parameters, default=['Proteína Bruta (PB)', 'Energia Metabolizável - Aves', 'FDN'])
        
        # Grid layout para os gráficos de barra
        cols_graf = st.columns(2)
        for i, param in enumerate(selected_params):
            unit = get_unit(df_raw, param)
            vals = {c: get_nutrient(df_raw, c, param) for c in selected_comms}
            max_val = max([v for v in vals.values() if not pd.isna(v)], default=0)
            # Para não estourar a barra visual, adiciona 20% de margem no eixo max
            max_axis = max_val * 1.2 if max_val > 0 else 100 
            
            with cols_graf[i % 2]:
                st.markdown(f"**{param} ({unit})**")
                st.markdown(render_dynamic_bar(vals, max_axis, unit), unsafe_allow_html=True)

# ==========================================
# ABA 2: SIMULADOR DE SUBSTITUIÇÃO
# ==========================================
with tab2:
    st.subheader("Simulador de Formulação e Substituição")
    
    # Inicializar estado do simulador
    if 'form_orig' not in st.session_state:
        st.session_state.form_orig = {c: 0.0 for c in all_commodities}
        st.session_state.form_orig['Milho'] = 60.0
        st.session_state.form_orig['Farelo de Soja'] = 30.0
        st.session_state.form_orig['DDGS'] = 10.0
        
    if 'form_new' not in st.session_state:
        st.session_state.form_new = st.session_state.form_orig.copy()

    col_orig, col_subst, col_new = st.columns([1, 1, 1])
    
    # 1. Formulação Original
    with col_orig:
        st.markdown("### 📋 Formulação Original (%)")
        soma_orig = 0
        for comm in all_commodities:
            st.session_state.form_orig[comm] = st.number_input(f"{comm} (Orig)", min_value=0.0, max_value=100.0, value=float(st.session_state.form_orig.get(comm, 0.0)), step=1.0)
            soma_orig += st.session_state.form_orig[comm]
            
        if abs(soma_orig - 100.0) > 0.01:
            st.error(f"Soma: {soma_orig:.1f}%. A formulação original deve somar 100%.")
        else:
            st.success("Soma: 100% OK")
            if st.button("Copiar Original para Reestruturada"):
                st.session_state.form_new = st.session_state.form_orig.copy()
                st.rerun()

    # 2. Conexão / Substituição Visual
    with col_subst:
        st.markdown("### 🔄 Motor de Substituição")
        st.info("Defina qual ingrediente vai aumentar, e quem vai ceder espaço na mesma proporção física.")
        
        inc_comm = st.selectbox("Ingrediente a AUMENTAR (+):", all_commodities)
        dec_comm = st.selectbox("Ingrediente a REDUZIR (-):", all_commodities, index=1)
        qtd_subst = st.number_input("Quantidade a transferir (%):", min_value=0.0, value=5.0, step=1.0)
        
        st.markdown(f"<div style='text-align:center; padding: 10px; background-color:#1e293b; border-radius:10px; margin-bottom: 10px;'>"
                    f"<b>{inc_comm}</b> (+{qtd_subst}%)<br> ⬆ <br> ⬇ <br><b>{dec_comm}</b> (-{qtd_subst}%)"
                    f"</div>", unsafe_allow_html=True)
                    
        if st.button("Aplicar Substituição na Reestruturada"):
            if st.session_state.form_new[dec_comm] >= qtd_subst:
                st.session_state.form_new[inc_comm] += qtd_subst
                st.session_state.form_new[dec_comm] -= qtd_subst
                st.success("Substituição aplicada!")
            else:
                st.error(f"Erro: O ingrediente {dec_comm} não possui {qtd_subst}% disponível para reduzir.")

    # 3. Formulação Reestruturada
    with col_new:
        st.markdown("### 🛠️ Formulação Reestruturada (%)")
        soma_new = 0
        for comm in all_commodities:
            st.session_state.form_new[comm] = st.number_input(f"{comm} (Nova)", min_value=0.0, max_value=100.0, value=float(st.session_state.form_new.get(comm, 0.0)), step=1.0)
            soma_new += st.session_state.form_new[comm]
            
        if abs(soma_new - 100.0) > 0.01:
            st.error(f"Soma: {soma_new:.1f}%. A formulação reestruturada deve somar 100%.")
        else:
            st.success("Soma: 100% OK")

    st.markdown("---")
    # Cálculos da Dieta
    if abs(soma_orig - 100.0) <= 0.01 and abs(soma_new - 100.0) <= 0.01:
        st.subheader("COMPARAÇÃO — ORIGINAL × REESTRUTURADA")
        
        # Função para calcular nutrientes da dieta
        def calc_dieta(form_dict, prices_dict, df):
            custo_ton = sum((form_dict[c]/100) * prices_dict[c] for c in all_commodities)
            nutri = {}
            for param in all_parameters:
                total_param = 0
                valido = True
                for c in all_commodities:
                    perc = form_dict[c] / 100
                    if perc > 0:
                        v = get_nutrient(df, c, param)
                        if pd.isna(v): 
                            valido = False # Se um ingrediente ativo não tem o dado, a dieta não pode calcular
                        else:
                            total_param += v * perc
                nutri[param] = total_param if valido else np.nan
            return custo_ton, nutri

        custo_orig, nutri_orig = calc_dieta(st.session_state.form_orig, prices, df_raw)
        custo_new, nutri_new = calc_dieta(st.session_state.form_new, prices, df_raw)
        
        # Impacto Econômico
        dif_custo = custo_new - custo_orig
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("Custo Original (R$/t)", f"R$ {custo_orig:.2f}")
        col_res2.metric("Custo Reestruturado (R$/t)", f"R$ {custo_new:.2f}")
        
        status_eco = f"🟢 Barateou R$ {abs(dif_custo):.2f}/t" if dif_custo < 0 else (f"🔴 Encareceu R$ {abs(dif_custo):.2f}/t" if dif_custo > 0 else "⚪ Sem alteração")
        col_res3.metric("Impacto Econômico", f"R$ {dif_custo:.2f}", status_eco, delta_color="inverse")
        
        with st.expander("ℹ️ Como o custo da dieta é calculado?"):
            st.write("Soma-se a (Porcentagem de inclusão ÷ 100) multiplicada pelo Preço da Tonelada de cada ingrediente.")
            calc_str = " + ".join([f"({st.session_state.form_new[c]}% × R${prices[c]})" for c in all_commodities if st.session_state.form_new[c] > 0])
            st.write(f"**Conta (Nova):** {calc_str} = R$ {custo_new:.2f}")

        # Impacto Nutricional
        st.markdown("#### Impacto Nutricional")
        nutri_table = []
        for param in all_parameters:
            v_o = nutri_orig[param]
            v_n = nutri_new[param]
            unit = get_unit(df_raw, param)
            
            if pd.isna(v_o) or pd.isna(v_n):
                dif_str = "N/D"
            else:
                dif = v_n - v_o
                dif_str = f"+{dif:.2f}" if dif > 0 else f"{dif:.2f}"
                
            nutri_table.append({
                "Parâmetro": f"{param} ({unit})",
                "Original": f"{v_o:.2f}" if not pd.isna(v_o) else "N/D",
                "Reestruturada": f"{v_n:.2f}" if not pd.isna(v_n) else "N/D",
                "Diferença": dif_str
            })
            
        st.dataframe(pd.DataFrame(nutri_table), use_container_width=True)

# ==========================================
# ABA 3: BASE DE DADOS
# ==========================================
with tab3:
    st.subheader("Base de Dados Nutricional")
    st.markdown("Os dados abaixo alimentam todos os cálculos da aplicação. Valores vazios representam falta de dados de literatura (N/D).")
    st.dataframe(df_raw, use_container_width=True)
    
    st.info("💡 **Auditoria e Transparência**: Esta matriz pode ser alimentada por um Google Sheets no formato: `Coluna A = Parâmetro`, `Coluna B = Unidade`, `Demais Colunas = Commodities`.")
