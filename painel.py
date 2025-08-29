import streamlit as st
from streamlit_extras.stylable_container import stylable_container
from auth import get_current_user
from db import get_disciplinas_resumo
from utils import fmt_horas


def _pct_badge_html(pct: int) -> str:
    """Retorna HTML do badge quadrado de % conforme faixas."""
    try:
        p = int(pct)
    except Exception:
        p = 0

    # Decide cor de fundo e texto
    if p <= 0:
        bg, fg = "#F5F2E8", "#000000"  # branco, texto preto
    elif p < 65:
        bg, fg = "#C96C67", "#FFFFFF"  # vermelho, texto branco
    elif p < 75:
        bg, fg = "#E2C76D", "#000000"  # amarelo, texto preto
    else:
        bg, fg = "#7BA77A", "#FFFFFF"  # verde, texto branco

    return (
        f"<span style=\"display:inline-block; min-width:28px; padding:2px 6px; "
        f"border-radius:6px; background:{bg}; color:{fg}; "
        f"font-weight:700; font-size:.85rem; line-height:1.2; text-align:center;\">"
        f"{p}"
        f"</span>"
    )


def render_painel():
    user = get_current_user()
    if not user:
        return
    
    with stylable_container(
        key="painel",
        css_styles="""
        {
            display: block;
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px;
            text-align: center;
        }
        """
    ):
        st.markdown(
            '<h2 style="font-weight:600; font-size:1.1rem; margin:0; padding:0;">PAINEL</h2>',
            unsafe_allow_html=True
        )
        
        linhas = get_disciplinas_resumo(user["id"])
        if not linhas:
            st.caption("Nenhum estudo registrado ainda.")
            return

        # Ordena por nome
        linhas = sorted(linhas, key=lambda d: (d.get("subject") or "").lower())

        # Cabeçalho
        cols = st.columns([4, 1, 0.5, 0.5, 0.5, 0.5])
        headers = [
            "Disciplinas",
            "<div style='border-left:1px solid #444;border-right:1px solid #444;'>Tempo</div>",
            "<span style='color:#7BA77A'>✔</span>",
            "<span style='color:#C96C67'>✕</span>",
            "∑",
            "%"
        ]
        for c, h in zip(cols, headers):
            c.markdown(
                f"<div style='font-size: 1.1rem; font-weight: 600;'>{h}</div>",
                unsafe_allow_html=True
            )

        # Linhas
        for i, d in enumerate(linhas):
            bg = "#1A1A1A" if i % 2 else "#222222"
            c = st.columns([4, 1, 0.5, 0.5, 0.5, 0.5])

            # Disciplina
            c[0].markdown(
                f"<div style='background:{bg};padding:4px; text-align: left;'>{d['subject']}</div>",
                unsafe_allow_html=True
            )

            # Tempo
            total_sec = int(d.get("total_sec") or 0)
            tempo_fmt = fmt_horas(total_sec // 60) if total_sec else "-"
            c[1].markdown(
                f"<div style='background:{bg};padding:4px 8px;"
                "border-left:1px solid #444;border-right:1px solid #444;"
                "box-sizing:border-box;'>"
                f"{tempo_fmt}"
                "</div>",
                unsafe_allow_html=True
            )

            # Acertos / Erros / Total
            c[2].markdown(
                f"<div style='background:{bg};padding:4px;color:#7BA77A'>{d['hits']}</div>",
                unsafe_allow_html=True
            )
            c[3].markdown(
                f"<div style='background:{bg};padding:4px;color:#C96C67'>{d['mistakes']}</div>",
                unsafe_allow_html=True
            )
            c[4].markdown(
                f"<div style='background:{bg};padding:4px'>{d['total']}</div>",
                unsafe_allow_html=True
            )

            # % badge
            pct_html = _pct_badge_html(int(d.get("pct", 0)))
            c[5].markdown(
                f"<div style='background:{bg};padding:4px;'>{pct_html}</div>",
                unsafe_allow_html=True
            )
