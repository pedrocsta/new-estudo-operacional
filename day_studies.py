# day_studies.py
import datetime as dt
import hashlib
import colorsys

import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import plotly.graph_objects as go

from auth import get_current_user
from utils import fmt_horas
from db import (
    get_user_created_date,
    get_day_subject_breakdown,
    get_subject_colors,
    upsert_subject_color,
)

MAX_ROWS = 7  # limite de matérias/linhas

def _clamp(date_val: dt.date, min_d: dt.date, max_d: dt.date) -> dt.date:
    return max(min_d, min(max_d, date_val))

# --------- Geração determinística de cor (PASTEL) ----------
def _subject_to_color_hex(subject: str) -> str:
    """Hash -> HSL -> cor PASTEL estável (#RRGGBB)."""
    h = int(hashlib.md5(subject.strip().lower().encode("utf-8")).hexdigest(), 16)
    hue = (h % 360) / 360.0
    sat = 0.45
    light = 0.78
    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return f"#{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

def _ensure_colors(user_id: int, subjects: list[str]) -> dict[str, str]:
    """Garante que todas as matérias tenham cor no DB."""
    existing = get_subject_colors(user_id)
    for s in subjects:
        if s not in existing:
            hexc = _subject_to_color_hex(s)
            upsert_subject_color(user_id, s, hexc)
            existing[s] = hexc
    return existing

def render_day_studies():
    user = get_current_user()
    today = dt.date.today()

    created = None
    if user:
        created_str = get_user_created_date(user["id"])
        if created_str:
            try:
                created = dt.datetime.strptime(created_str, "%Y-%m-%d").date()
            except Exception:
                created = None

    min_day = created or today
    max_day = today

    if "selected_day" not in st.session_state:
        st.session_state.selected_day = today

    # clamp sempre
    st.session_state.selected_day = _clamp(st.session_state.selected_day, min_day, max_day)
    selected_day = st.session_state.selected_day

    can_prev = selected_day > min_day
    can_next = selected_day < max_day

    with stylable_container(
        key="estudo-do-dia",
        css_styles="""
        {
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px;

            div[data-testid="stHorizontalBlock"] { align-items: center; display: flex; text-align: center;}
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) > div > div { margin-left: auto;}
            div[data-testid="stButton"] > button {
                height: 1.8rem !important;
                min-height: 1rem !important;
                width: 2rem;
                gap: 0;
            }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) > div > div{ margin-left: auto; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(3) > div > div { margin-right: auto; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
                flex: 0 0 auto !important;
                max-width: fit-content !important;
            }

            /* Estilos da lista */
            .ds-flex{display:flex;flex-direction:column;gap:0;flex:1;min-height:0;}
            .ds-list{margin-top:2px;display:flex;flex-direction:column;overflow:auto;}
            .ds-row{display:flex;align-items:center;gap:8px;color:#EDEDED;font-size:14px;line-height:1.2;margin:8px 0;}
            .ds-dot{width:16px;height:16px;border-radius:4px;display:inline-block;flex-shrink:0;}
            .ds-label{white-space:nowrap;}
            .ds-line{flex:1;height:1px;background:#3a3a3a;opacity:.7;margin:0 8px;}
            .ds-value{color:#EDEDED;font-weight:600;white-space:nowrap;}
            .ds-empty-msg{flex:1;text-align:center;font-weight:600;opacity:.8;}
        }
        """
    ):
        titulo, butao = st.columns([1, 1.8])

        with titulo:
            st.markdown(
                "<h2 style='font-weight:600; font-size:1.1rem; margin:0; padding:0;'>ESTUDOS DO DIA</h2>",
                unsafe_allow_html=True
            )

        with butao:
            btn_prev, date_box, btn_next = st.columns([1, 4, 1])

            with btn_prev:
                if st.button("⭠", key="btn-prev-day", disabled=not can_prev):
                    st.session_state.selected_day = _clamp(selected_day - dt.timedelta(days=1), min_day, max_day)
                    st.rerun()

            with date_box:
                st.markdown(selected_day.strftime("%d/%m/%Y"))

            with btn_next:
                if st.button("⭢", key="btn-next-day", disabled=not can_next):
                    st.session_state.selected_day = _clamp(selected_day + dt.timedelta(days=1), min_day, max_day)
                    st.rerun()

        # --------- Dados do dia + gráfico ---------
        if not user:
            st.info("Entre na sua conta para ver seus estudos.")
            return

        day_iso = selected_day.isoformat()
        rows_db = get_day_subject_breakdown(user["id"], day_iso)

        studied = sorted(
            [{"subject": r["subject"], "minutes": int(r["total_sec"] // 60)} for r in rows_db],
            key=lambda x: x["minutes"],
            reverse=True
        )[:MAX_ROWS]

        total_min = sum(r["minutes"] for r in studied) if studied else 0

        # --- Gráfico ---
        if studied:
            subjects = [r["subject"] for r in studied]
            values_min = [max(1, r["minutes"]) for r in studied]
            color_map = _ensure_colors(user["id"], subjects)
            colors = [color_map[s] for s in subjects]

            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=subjects,
                        values=values_min,
                        marker=dict(colors=colors, line=dict(width=0)),
                        hole=0.0,
                        textinfo="none",
                        sort=False,
                        direction="clockwise",
                        hovertemplate="%{label}<extra></extra>",
                    )
                ]
            )
        else:
            # Sem estudos: círculo cinza escuro + hover especial
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=[""],
                        values=[1],
                        marker=dict(colors=["#2A2A2A"], line=dict(width=0)),
                        hole=0.0,
                        textinfo="none",
                        sort=False,
                        direction="clockwise",
                        hovertemplate="Você ainda não estudou hoje.<extra></extra>",
                    )
                ]
            )

        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=220,
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            hoverlabel=dict(namelength=-1)
        )

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Total central
        st.markdown(
            f"<div style='text-align:center; font-weight:700; font-size:1.3rem; margin:0;'>{fmt_horas(total_min)}</div>",
            unsafe_allow_html=True,
        )

        # ------- Lista sempre 7 linhas -------
        rows_real = []
        if studied:
            color_map = _ensure_colors(user["id"], [r["subject"] for r in studied])
            rows_real = [
                {"subject": r["subject"], "minutes": r["minutes"], "color": color_map[r["subject"]], "is_msg": False}
                for r in studied
            ]

        placeholders_needed = MAX_ROWS - len(rows_real)
        placeholders = [{"subject": "", "minutes": None, "color": "#1A1A1A", "is_msg": False} for _ in range(placeholders_needed)]

        if not rows_real and placeholders:
            # primeira linha especial de mensagem
            placeholders[0] = {
                "subject": "Sem estudos cadastrados neste dia.",
                "minutes": None,
                "color": "#1A1A1A",
                "is_msg": True
            }

        rows_7 = rows_real + placeholders

        html_rows = ''.join(
            (
                f'<div class="ds-row">'
                f'{"<div class=\'ds-empty-msg\' style=\'flex:1;text-align:center;font-weight:700;opacity:.8;\'>"
                   + r["subject"] + "</div>" if r.get("is_msg") else 
                   f"<span class=\'ds-dot\' style=\'background:{r['color']};\'></span>"
                   f"<span class=\'ds-label\'>{r['subject'] if r['subject'] else '&nbsp;'}</span>"
                   f"<span class=\'ds-line\' style=\'background:{'#1A1A1A' if r['minutes'] is None else ''};\'></span>"
                   f"<span class=\'ds-value\'>{fmt_horas(r['minutes']) if isinstance(r['minutes'], int) else '&nbsp;'}</span>"
                }'
                f'</div>'
            )
            for r in rows_7
        )

        st.markdown(f'<div class="ds-list">{html_rows}</div>', unsafe_allow_html=True)
