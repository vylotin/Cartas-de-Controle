import plotly.graph_objects as go
import pandas as pd
import numpy as np

def construir_figura_plotly(df_calc: pd.DataFrame, config: dict, nome_ind: str, col_data: str, fases: list, col_fase_atual: str, mostrar_rotulos: bool, aba_nome: str) -> go.Figure:
    """Gera gráfico Laney isolado por fase com quebras estritas e limites variáveis reais."""
    fig = go.Figure()
    modo_grafico = "lines+markers+text" if mostrar_rotulos else "lines+markers"
    
    # 1. Identificar o tipo de gráfico e definir símbolos e sufixos
    is_u_chart = config["tipo"].upper().startswith("U")
    simbolo_media = "Ū" if is_u_chart else "P̄"
    sufixo_valor = "" if is_u_chart else "%"
    
    ultimo_global = df_calc.iloc[-1]
    df_calc = df_calc.copy()
    df_calc[col_data] = pd.to_datetime(df_calc[col_data])

    fases_coords = []
    for fase in fases:
        if col_fase_atual != "Nenhuma" and col_fase_atual in df_calc.columns:
            df_fase = df_calc[df_calc[col_fase_atual] == fase]
        else:
            df_fase = df_calc
            
        if not df_fase.empty:
            fases_coords.append({
                "fase": fase,
                "df": df_fase,
                "start": df_fase[col_data].iloc[0],
                "end": df_fase[col_data].iloc[-1]
            })

    vlines_datas = []

    for idx, coord in enumerate(fases_coords):
        df_fase = coord["df"]
        start_date = coord["start"]
        end_date = coord["end"]

        if idx > 0:
            end_anterior = fases_coords[idx - 1]["end"]
            left_midpoint = end_anterior + (start_date - end_anterior) / 2
            vlines_datas.append(left_midpoint)
        else:
            left_midpoint = start_date

        if idx < len(fases_coords) - 1:
            start_proxima = fases_coords[idx + 1]["start"]
            right_midpoint = end_date + (start_proxima - end_date) / 2
        else:
            right_midpoint = end_date

        # Preserva os degraus e a variação real de LSC e LIC conforme o denominador do mês
        x_limites = [left_midpoint] + df_fase[col_data].tolist() + [right_midpoint]
        y_lsc = [df_fase["LSC"].iloc[0]] + df_fase["LSC"].tolist() + [df_fase["LSC"].iloc[-1]]
        y_lic = [df_fase["LIC"].iloc[0]] + df_fase["LIC"].tolist() + [df_fase["LIC"].iloc[-1]]
        y_media = [df_fase["MEDIA"].iloc[0]] + df_fase["MEDIA"].tolist() + [df_fase["MEDIA"].iloc[-1]]

        fig.add_trace(go.Scatter(x=x_limites, y=y_lsc, mode="lines", line_shape="hv", line=dict(color="#B22222", width=0.8), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x_limites, y=y_lic, mode="lines", line_shape="hv", line=dict(color="#B22222", width=0.8), hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x_limites, y=y_media, mode="lines", line_shape="hv", line=dict(color="#228B22", width=1), hoverinfo="skip"))

        # 2. Aplicar sufixo dinâmico nos rótulos e hover
        fig.add_trace(go.Scatter(
            x=df_fase[col_data], y=df_fase["TAXA"], mode=modo_grafico,
            line=dict(color="#0055A4", width=1.2), marker=dict(size=8, color="#0055A4"),
            text=df_fase["TAXA"].apply(lambda v: f"{v:.1f}{sufixo_valor}") if mostrar_rotulos else None,
            textposition="top center", 
            hovertemplate=f"<b>%{{x|%b/%y}}</b><br>Taxa: %{{y:.2f}}{sufixo_valor}<extra></extra>"
        ))

        ultimo_fase = df_fase.iloc[-1]
        if pd.notna(ultimo_fase["MEDIA"]):
            # 3. Aplicar símbolo dinâmico da média (Ū ou P̄)
            fig.add_annotation(
                x=end_date, y=ultimo_fase["MEDIA"], text=f"{simbolo_media} = {ultimo_fase['MEDIA']:.2f}{sufixo_valor}", 
                showarrow=False, xanchor="right", yanchor="bottom", yshift=3, 
                font=dict(size=11, family="Arial", color="#228B22")
            )

    df_out = df_calc[df_calc["OUTLIER"]]
    if not df_out.empty:
        fig.add_trace(go.Scatter(x=df_out[col_data], y=df_out["TAXA"], mode="markers", marker=dict(size=10, color="#D50000", symbol="square"), hoverinfo="skip"))
    
    df_run = df_calc[df_calc["RUN"] & ~df_calc["OUTLIER"]]
    if not df_run.empty:
        fig.add_trace(go.Scatter(x=df_run[col_data], y=df_run["TAXA"], mode="markers", marker=dict(size=10, color="#f59e0b", symbol="diamond"), hoverinfo="skip"))

    for data_linha in vlines_datas:
        fig.add_vline(x=data_linha, line_width=1, line_dash="dash", line_color="#9370DB")

    # 4. Ajustar os rótulos globais de limite e média na direita
    for valor, label in [
        (ultimo_global["LSC"], f"LSC={ultimo_global['LSC']:.2f}{sufixo_valor}"), 
        (ultimo_global["MEDIA"], f"{simbolo_media}={ultimo_global['MEDIA']:.2f}{sufixo_valor}"), 
        (ultimo_global["LIC"], f"LIC={ultimo_global['LIC']:.2f}{sufixo_valor}")
    ]:
        if pd.notna(valor):
            fig.add_annotation(
                x=1.02, y=valor, xref="paper", yref="y", text=label, 
                showarrow=False, xanchor="left", font=dict(size=14, family="Arial", color="#000000")
            )

    sufixo_titulo = "Densidade de Incidência (TDI)" if is_u_chart else "Taxa de Utilização (%)"
    fig.update_layout(
        width=777, height=480,
        title=dict(text=f"{nome_ind} — {sufixo_titulo} ({aba_nome.upper()})", font=dict(size=18, color="#333"), x=0.5, xanchor="center"),
        plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified",
        xaxis=dict(type="date", tickformat="%b/%y", showgrid=False, linecolor="gray", mirror=True),
        yaxis=dict(showgrid=False, linecolor="gray", mirror=True),
        showlegend=False, margin=dict(l=50, r=120, t=60, b=40)
)
    return fig