# app.py
import streamlit as st
import pandas as pd
import os
import zipfile
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
        # TRATAMENTO DE ERRO: Proteção caso o Excel esteja aberto
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
# PAINEL DE ALTERAÇÃO EM TEMPO REAL (ÁREA RESTRITA)
# =====================================================================
with st.expander("✏️ Edição de Dados em Tempo Real", expanded=False):
    st.markdown("Modificações na tabela são refletidas nos gráficos imediatamente em tempo de execução.")
    df_editado = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=200)

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
                # TRATAMENTO DE ERRO: Caso tente salvar com ele aberto
                st.error("❌ O arquivo está aberto no Excel. Feche-o antes de salvar.")
            except Exception as e:
                st.error(f"❌ Falha de gravação de arquivo: {e}")

colunas_disponiveis = df_editado.columns.tolist()
col_data = next((c for c in colunas_disponiveis if any(k in c.lower() for k in ["data", "mes", "mês"])), colunas_disponiveis[0])

indicadores_ativos = {
    nome: cfg for nome, cfg in CONFIG_INDICADORES.items()
    if cfg["num"] in colunas_disponiveis and cfg["den"] in colunas_disponiveis
}

if not indicadores_ativos:
    st.error("❌ Nenhuma topografia com padrão CCIH reconhecida nas colunas desta aba.")
    st.stop()

# =====================================================================
# MOTOR DE PREPARAÇÃO DO RELATÓRIO ZIP (OTIMIZADO - SOB DEMANDA)
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
abas_graficos = st.tabs(list(indicadores_ativos.keys()))

def aplicar_estilo_vetorizado(df_sub: pd.DataFrame) -> pd.DataFrame:
    estilos = pd.DataFrame("", index=df_sub.index, columns=df_sub.columns)
    if "OUTLIER" in df_sub.columns:
        estilos.loc[df_sub["OUTLIER"] == True, :] = "background-color: #fca5a5"
    if "RUN" in df_sub.columns:
        estilos.loc[(df_sub["RUN"] == True) & (df_sub["OUTLIER"] == False), :] = "background-color: #fef3c7"
    return estilos

for idx, (nome_ind, config) in enumerate(indicadores_ativos.items()):
    with abas_graficos[idx]:
        col_fase_atual = config["fase"] if config["fase"] in colunas_disponiveis else "Nenhuma"
        
        res: ResultadoLaney = calcular_analises_completas(
            df_editado, col_data, config["num"], config["den"], col_fase_atual, config["tipo"], config["mult"]
        )
        
        if res.df.empty:
            st.warning("Dados insuficientes na planilha para a extração analítica deste indicador.")
            continue
            
        ultimo = res.df.iloc[-1]
        n_causas = int(res.df["CAUSA_ESPECIAL"].sum())

        status_txt = "SURTO" if ultimo["OUTLIER"] else ("TENDÊNCIA" if ultimo["RUN"] else "ESTÁVEL")
        data_label = ultimo[col_data].strftime("%b/%y") if isinstance(ultimo[col_data], datetime) else str(ultimo[col_data])
        
        # --- ALTERNÂNCIA DINÂMICA: TDI vs UTILIZAÇÃO (%) ---
        is_u_chart = config["tipo"].upper().startswith("U")
        label_taxa = "TDI Mês" if is_u_chart else "Utilização (%)"
        sufixo_taxa = "" if is_u_chart else "%"
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Mês Avaliado", data_label)
        m2.metric(label_taxa, f"{ultimo['TAXA']:.2f}{sufixo_taxa}")
        m3.metric("Status Atual", status_txt)
        
        if int(res.df["RUN"].sum()) > 0:
            st.markdown('<div class="audit-banner">⚠️ <b>Atenção à Tendência (Nelson Rule 2):</b> Foram detectados pontos sequenciais contínuos no mesmo lado da média histórica.</div>', unsafe_allow_html=True)

        fig_tela = construir_figura_plotly(
            res.df, config, nome_ind, col_data, res.fases, col_fase_atual, mostrar_rotulos, aba_selecionada
        )
        
        slug_export = f"{nome_ind}_{aba_selecionada}".replace(" ", "_").replace("/", "-")
        st.plotly_chart(fig_tela, use_container_width=False, key=f"chart_prod_{config['num']}_{idx}", config={
            "displayModeBar": True, "modeBarButtons": [["toImage"]], "displaylogo": False,
            "toImageButtonOptions": {"format": "png", "filename": f"CCIH_{slug_export}"}
        })

        with st.expander("📊 Planilha Resumida de Limites Operacionais", expanded=False):
            cols_tabela = [c for c in [col_data, config["num"], config["den"], "TAXA", "LSC", "LIC", "OUTLIER", "RUN"] if c in res.df.columns]
            st.dataframe(
                res.df[cols_tabela].style.apply(aplicar_estilo_vetorizado, axis=None), 
                use_container_width=True, 
                height=200
            )

# Rodapé Corporativo Estático Fixo
st.markdown("""
    <div style="text-align: center; padding: 20px; color: #475569; font-size: 0.75rem; border-top: 1px solid rgba(0,0,0,0.05); margin-top: 40px;">
        Controle de Infecção Hospitalar | CIDS | SCIH | HUGO
    </div>
""", unsafe_allow_html=True)