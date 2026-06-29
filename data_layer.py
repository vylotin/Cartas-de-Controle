# data_layer.py
import os
import pandas as pd
from io import BytesIO
import streamlit as st

@st.cache_data(show_spinner="Carregando planilha clínica…")
def carregar_excel(conteudo_bytes: bytes) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(BytesIO(conteudo_bytes))
    return {aba: xls.parse(aba) for aba in xls.sheet_names}

def ler_arquivo(fonte) -> tuple[dict[str, pd.DataFrame], bytes]:
    if isinstance(fonte, str):
        with open(fonte, "rb") as f:
            raw = f.read()
    else:
        raw = fonte.read()
        fonte.seek(0)
    return carregar_excel(raw), raw

def salvar_excel_multiaba(path_destino: str, df_atualizado: pd.DataFrame, aba_ativa: str, abas_dict: dict):
    if os.path.exists(path_destino):
        with pd.ExcelWriter(path_destino, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_atualizado.to_excel(writer, sheet_name=aba_ativa, index=False)
    else:
        with pd.ExcelWriter(path_destino, engine="openpyxl") as writer:
            for aba, df_aba in abas_dict.items():
                df_salvar = df_atualizado if aba == aba_ativa else df_aba
                df_salvar.to_excel(writer, sheet_name=aba, index=False)