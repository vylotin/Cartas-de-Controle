# app.py
import streamlit as st
import pandas as pd
import os
import zipfile
import uuid
from datetime import datetime
from io import BytesIO
from html import escape

# Importações dos módulos refatorados e seguros
from config import CONFIG_INDICADORES, ARQUIVO_SALVO
from audit import registrar_auditoria
from auth import render_login_widget
from data_layer import ler_arquivo, salvar_excel_multiaba, carregar_excel
from statistics import calcular_analises_completas, ResultadoLaney
from charts import construir_figura_plotly

# Título corporativo adequado e seguro para ambiente hospitalar
st.set_page_config(
    page_title="CCIH — Painel de Controle | HUGO",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🦠"
)

# Estilização CSS Sanitizada Estática
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600;800&family=IBM+Plex+Mono&display=swap');
    html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
    .audit-banner {
        background: #f8fafc;
        border-left: 4px solid #6366f1;
        border-radius: 6px;
        padding: 12px 14px;
        font-size: 0.85rem;
        color: #475569;
        margin-bottom: 15px;
    }
    .stPlotlyChart { image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges; }
    </style>
""", unsafe_allow_html=True)    

# =====================================================================
# MOTORES DE TRADUÇÃO DE DATA (INGLÊS -> PT-BR)
# =====================================================================
MESES_PT = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
MESES_INV = {v.lower(): k for k, v in MESES_PT.items()}

def format_to_pt(date_val):
    """Converte formato YYYY-MM-DD para string Mês/Ano (Ex: Jun/26)"""
    if pd.isnull(date_val): return ""
    try:
        dt = pd.to_datetime(date_val)
        return f"{MESES_PT[dt.month]}/{dt.strftime('%y')}"
    except:
        return str(date_val)

def parse_from_pt(str_val):
    """Lê a string digitada pelo usuário (Ex: Jun/26) e volta para Datetime oculto"""
    if pd.isnull(str_val) or str_val == "": return pd.NaT
    if isinstance(str_val, datetime): return str_val
    try:
        str_val = str(str_val).replace('-', '/').replace(' ', '')
        m, y = str_val.split('/')
        mes = MESES_INV[m.strip()[:3].lower()]
        ano = int(y) if int(y) > 100 else int(y) + 2000
        return pd.to_datetime(f"{ano}-{mes:02d}-01")
    except:
        return pd.to_datetime(str_val, errors='coerce')

# =====================================================================
# INTERFACE LATERAL: FLUXO DE DADOS
# =====================================================================
with st.sidebar:
    st.markdown("### 🦠 CCIH Control Charts")
    st.markdown("---")
    st.header("📂 Fonte de Dados")

    abas_dict = None
    raw_bytes = None

    if os.path.exists(ARQUIVO_SALVO):
        st.success("✅ Base salva encontrada")
        usar_salvo = st.checkbox("Continuar com a base salva", value=True)
    else:
        usar_salvo = False

    if usar_salvo:
        try:
            abas_dict, raw_bytes = ler_arquivo(ARQUIVO_SALVO)
        except PermissionError:
            st.error(f"❌ Acesso negado: O arquivo '{ARQUIVO_SALVO}' está bloqueado. Feche-o no Excel e atualize a página.")
            st.stop()
    else:
        st.info("Faça upload de uma nova base clínica.")
        arquivo_up = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
        if arquivo_up:
            abas_dict, raw_bytes = ler_arquivo(arquivo_up)

    df = None
    aba_selecionada = None
    if abas_dict is not None:
        aba_selecionada = st.selectbox("📑 Aba (Dataset)", list(abas_dict.keys()))
        df = abas_dict[aba_selecionada]

    st.markdown("---")
    if os.environ.get("CCIH_SHOW_AUDIT_LOGS") and os.path.exists("ccih_audit.log"):
        with st.expander("📋 Log de Auditoria"):
            with open("ccih_audit.log", "r", encoding="utf-8") as lf:
                linhas = lf.readlines()
            st.code("".join(linhas[-20:]), language=None)

st.title("🦠 CCIH — Gráficos de Controle")
st.caption("Gráficos Laney com quebras estruturais e critérios baseados nos Limites Operacionais e Regras de Nelson.")

if df is None:
    st.info("👈 Carregue uma base de dados na barra lateral para inicializar o painel.")
    st.stop()

# =====================================================================
# PAINEL DE ALTERAÇÃO EM TEMPO REAL COM DATAS PT-BR
# =====================================================================
colunas_disponiveis = df.columns.tolist()
col_data = next((c for c in colunas_disponiveis if any(k in c.lower() for k in ["data", "mes", "mês"])), colunas_disponiveis[0])

# Prepara os dados para exibir "Jun/26"
df_display = df.copy()
df_display[col_data] = df_display[col_data].apply(format_to_pt)

with st.expander("✏️ Edição de Dados em Tempo Real", expanded=False):
    st.markdown("Você pode editar as datas no padrão brasileiro, ex: **Jun/26**, **Fev/26**.")
    df_editado_str = st.data_editor(df_display, num_rows="dynamic", use_container_width=True, height=200)

    # Converte tudo de volta para matemática pura
    df_editado = df_editado_str.copy()
    df_editado[col_data] = df_editado[col_data].apply(parse_from_pt)
    df_editado = df_editado.dropna(subset=[col_data]) 

    st.markdown("#### 🔒 Confirmação de Gravação (Administrador)")
    if render_login_widget():
        if st.button("💾 Salvar Alterações Definitivas no Excel", use_container_width=True):
            try:
                salvar_excel_multiaba(ARQUIVO_SALVO, df_editado, aba_selecionada, abas_dict)
                carregar_excel.clear()
                registrar_auditoria(f"SAVE_DATA | aba={aba_selecionada} | linhas={len(df_editado)}")
                st.success("✅ Arquivo atualizado em disco com sucesso.")
                st.rerun()
            except PermissionError:
                st.error("❌ O arquivo está aberto no Excel. Feche-o antes de salvar.")
            except Exception as e:
                st.error(f"❌ Falha de gravação de arquivo: {e}")

colunas_disponiveis = df_editado.columns.tolist()

indicadores_ativos = {
    nome: cfg for nome, cfg in CONFIG_INDICADORES.items()
    if cfg["num"] in colunas_disponiveis and cfg["den"] in colunas_disponiveis
}

if not indicadores_ativos:
    st.error("❌ Nenhuma topografia com padrão CCIH reconhecida nas colunas desta aba.")
    st.stop()

# =====================================================================
# MOTOR DE PREPARAÇÃO DO RELATÓRIO ZIP 
# =====================================================================
st.markdown("#### 📦 Exportação de Relatórios Clínicos")
col_zip, col_toggle = st.columns([1, 3])
mostrar_rotulos = col_toggle.toggle("🏷️ Mostrar Rótulos numéricos nas Linhas Principais", value=False)

if st.session_state.get("admin_ok", False):
    if col_zip.button("🗜️ Compilar Pacote de Gráficos", use_container_width=True):
        with st.spinner("Processando imagens via Kaleido..."):
            buffer_zip = BytesIO()
            try:
                with zipfile.ZipFile(buffer_zip, "w") as zf:
                    for nome_ind, config in indicadores_ativos.items():
                        col_fase_atual = config["fase"] if config["fase"] in colunas_disponiveis else "Nenhuma"
                        res: ResultadoLaney = calcular_analises_completas(
                            df_editado, col_data, config["num"], config["den"], col_fase_atual, config["tipo"], config["mult"]
                        )
                        if not res.df.empty:
                            fig_virtual = construir_figura_plotly(
                                res.df, config, nome_ind, col_data, res.fases, col_fase_atual, mostrar_rotulos, aba_selecionada
                            )
                            # Aplica os meses em português no gráfico exportado
                            tick_vals = res.df[col_data].tolist()
                            tick_text = [format_to_pt(d) for d in tick_vals]
                            fig_virtual.update_layout(xaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_text))

                            img_bytes = fig_virtual.to_image(format="png", width=2400, height=1000)
                            nome_arquivo = f"{nome_ind}_{aba_selecionada}.png".replace(" ", "_").replace("/", "-")
                            zf.writestr(nome_arquivo, img_bytes)
                
                buffer_zip.seek(0)
                st.session_state.zip_ready_data = buffer_zip.getvalue()
                st.toast("Pacote compilado com sucesso!", icon="✅")
            except Exception:
                st.error("⚠️ Falha na exportação estática. Verifique se o pacote `kaleido` está instalado.")

    if "zip_ready_data" in st.session_state:
        col_zip.download_button(
            label="⬇️ Baixar Gráficos Prontos (ZIP)",
            data=st.session_state.zip_ready_data,
            file_name=f"Graficos_CCIH_{aba_selecionada}_{datetime.now():%Y%m%d}.zip",
            mime="application/zip",
            use_container_width=True
        )
else:
    col_zip.info("🔒 Autentique-se como Administrador acima para liberar a exportação em massa de relatórios.")

# =====================================================================
# PROVIMENTO DINÂMICO DOS PAINÉIS DE MONITORAMENTO 
# =====================================================================
st.markdown(f"### 📍 Painel de Monitoramento Dinâmico — Unidade: {escape(aba_selecionada.upper())}")

PARES_MONITORAMENTO = {
    "IPCS x CVC": ("IPCS", "CVC"),
    "ITU-CV x CVD": ("ITU-CV", "CVD"),
    "PAV x VM": ("PAV", "VM")
}

def aplicar_estilo_vetorizado(df_sub: pd.DataFrame) -> pd.DataFrame:
    estilos = pd.DataFrame("", index=df_sub.index, columns=df_sub.columns)
    if "OUTLIER" in df_sub.columns:
        estilos.loc[df_sub["OUTLIER"] == True, :] = "background-color: #fca5a5"
    if "RUN" in df_sub.columns:
        estilos.loc[(df_sub["RUN"] == True) & (df_sub["OUTLIER"] == False), :] = "background-color: #fef3c7"
    return estilos

def renderizar_bloco_grafico(nome_ind, config, m_col):
    # 1. Garante que os dados estejam no formato correto antes de calcular
    df_para_calculo = df_editado.copy()
    
    # 2. Chama o motor de cálculo
    res: ResultadoLaney = calcular_analises_completas(
        df_para_calculo, col_data, config["num"], config["den"], 
        config["fase"] if config["fase"] in colunas_disponiveis else "Nenhuma", 
        config["tipo"], config["mult"]
    )
    
    if res.df.empty: return

    # 1. GERAR A DATA FORMATADA EM PT-BR (Ex: Mai/26)
    # Isso cria uma lista fixa de meses na ordem exata dos seus dados
    meses_br = [format_to_pt(d) for d in res.df[col_data].tolist()]
    
    # 2. ADICIONAR A COLUNA DE MESES EM PT-BR NO DATAFRAME
    res.df['mes_br'] = meses_br

    fig_tela = construir_figura_plotly(
        res.df, config, nome_ind, 'mes_br', res.fases, config.get("fase"), mostrar_rotulos, aba_selecionada
    )
    
    # 3. FORÇAR O EIXO X A SER CATEGÓRICO E ESPAÇADO
    # Exibe um rótulo a cada 3 meses para não poluir
    intervalo = 3
    ticks_limpos = [m if i % intervalo == 0 else "" for i, m in enumerate(meses_br)]
    
    fig_tela.update_layout(
        xaxis=dict(
            type="category",
            tickmode="array",
            tickvals=list(range(len(meses_br))),
            ticktext=ticks_limpos,
            showgrid=False,
            linecolor="gray",
            mirror=True
        ),
        margin=dict(l=50, r=50, t=50, b=80) # Respiro no fundo para as datas
    )
    
    # ... resto do código (uuid, plotly_chart, expander) ...
    slug_export = f"{nome_ind}_{aba_selecionada}".replace(" ", "_").replace("/", "-")
    chave_unica = uuid.uuid4().hex[:8] 
    
    m_col.plotly_chart(fig_tela, use_container_width=True, key=f"chart_{config['num']}_{slug_export}_{chave_unica}")
    
    with m_col.expander("📊 Limites", expanded=False):
        st.dataframe(res.df.style.apply(aplicar_estilo_vetorizado, axis=None), use_container_width=True, height=150)

# Criar abas principais
abas_pares = st.tabs(list(PARES_MONITORAMENTO.keys()) + ["Outros Indicadores"])
indicadores_renderizados = []

for idx, (titulo_aba, (ind_infec, ind_uso)) in enumerate(PARES_MONITORAMENTO.items()):
    with abas_pares[idx]:
        col1, col2 = st.columns(2)
        
        with col1:
            if ind_infec in indicadores_ativos:
                renderizar_bloco_grafico(ind_infec, indicadores_ativos[ind_infec], col1)
                indicadores_renderizados.append(ind_infec)
            else:
                st.info(f"Indicador {ind_infec} não encontrado na planilha ativa.")

        with col2:
            if ind_uso in indicadores_ativos:
                renderizar_bloco_grafico(ind_uso, indicadores_ativos[ind_uso], col2)
                indicadores_renderizados.append(ind_uso)
            else:
                st.info(f"Indicador {ind_uso} não encontrado na planilha ativa.")

        # =========================================================
        # TABELA RESUMO HORIZONTAL
        # =========================================================
        if ind_infec in indicadores_ativos and ind_uso in indicadores_ativos:
            st.markdown("---")
            
            col_num_infec = indicadores_ativos[ind_infec]["num"]
            col_num_uso = indicadores_ativos[ind_uso]["num"]
            mult_infec = indicadores_ativos[ind_infec]["mult"]
            is_u_chart = indicadores_ativos[ind_infec]["tipo"].upper().startswith("U")
            label_taxa = "TDI" if is_u_chart else "Taxa (%)"
            
            df_temp = df_editado.copy()
            df_temp[col_data] = pd.to_datetime(df_temp[col_data])
            
            nome_unidade = escape(aba_selecionada.upper())
            col_headers = [nome_unidade, "2025"]
            row_infec = [f"N {col_num_infec}"] 
            row_uso = [f"{col_num_uso}"]       
            row_taxa = [label_taxa]            
            
            df_2025 = df_temp[df_temp[col_data].dt.year == 2025]
            soma_infec_2025 = df_2025[col_num_infec].sum() if not df_2025.empty else 0
            soma_uso_2025 = df_2025[col_num_uso].sum() if not df_2025.empty else 0
            taxa_2025 = (soma_infec_2025 / soma_uso_2025 * mult_infec) if soma_uso_2025 > 0 else 0
            
            row_infec.append(int(soma_infec_2025))
            row_uso.append(int(soma_uso_2025))
            row_taxa.append(f"{taxa_2025:.2f}".replace(".", ",")) 
            
            df_2026 = df_temp[df_temp[col_data].dt.year == 2026].copy()
            if not df_2026.empty:
                # Usa a mesma tradução robusta para a tabela resumo
                df_2026["Mês_Rotulo"] = df_2026[col_data].apply(format_to_pt)
                
                df_2026_grp = df_2026.groupby(df_2026[col_data].dt.month).agg({
                    "Mês_Rotulo": "first",
                    col_num_infec: "sum",
                    col_num_uso: "sum"
                }).sort_index()
                
                for _, row in df_2026_grp.iterrows():
                    col_headers.append(row["Mês_Rotulo"])
                    n_inf = row[col_num_infec]
                    n_uso = row[col_num_uso]
                    taxa = (n_inf / n_uso * mult_infec) if n_uso > 0 else 0
                    
                    row_infec.append(int(n_inf))
                    row_uso.append(int(n_uso))
                    row_taxa.append(f"{taxa:.2f}".replace(".", ","))
            
            tabela_resumo = pd.DataFrame([row_infec, row_uso, row_taxa], columns=col_headers)
            st.dataframe(tabela_resumo, use_container_width=True, hide_index=True)

with abas_pares[-1]:
    indicadores_restantes = [ind for ind in indicadores_ativos.keys() if ind not in indicadores_renderizados]
    
    if not indicadores_restantes:
        st.write("Todos os indicadores já foram exibidos nas abas anteriores.")
    else:
        for ind_extra in indicadores_restantes:
            st.markdown(f"#### {ind_extra}")
            renderizar_bloco_grafico(ind_extra, indicadores_ativos[ind_extra], st)
            st.divider()

st.markdown("""
    <div style="text-align: center; padding: 20px; color: #475569; font-size: 0.75rem; border-top: 1px solid rgba(0,0,0,0.05); margin-top: 40px;">
        Controle de Infecção Hospitalar | CIDS | SCIH | HUGO
    </div>
""", unsafe_allow_html=True)