import streamlit as st
from streamlit_extras.stylable_container import stylable_container
from dialogs import dialog_weekly_goal

from auth import get_current_user
from db import get_weekly_goal, get_total_minutes_by_date_range, get_questions_breakdown_by_date_range
import streamlit.components.v1 as components

import datetime as dt

def minutes_to_hhmm(total_minutes: int) -> str:
    h = max(0, int(total_minutes)) // 60
    m = max(0, int(total_minutes)) % 60
    return f"{h}h{m:02d}min"

def render_progress_bar(
    label: str,
    value: int,
    target: int,
    color: str,
    value_label: str | None = None,
    target_label: str | None = None,
):
    """Renderiza uma barra de progresso customizada com % dentro e rótulos personalizados."""
    # Cálculo de % (proteção para alvo zero)
    percent = (value / target * 100) if target > 0 else 0
    percent = min(percent, 100.0)

    # Rótulos mostrados à direita do título da barra
    right_text = f"{value_label if value_label is not None else value}/{target_label if target_label is not None else (target if target > 0 else '-')}"

    st.markdown(f"""
        <div style="margin: 8px 0;">
            <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:2px;">
                <span style="font-weight:600; font-size: 0.95rem;">{label}</span>
                <span style="font-weight:600;">{right_text}</span>
            </div>
            <div style="background-color:#2A2A2A; border-radius:6px; height:22px; position:relative; overflow:hidden;">
                <div style="width:{percent}%; background:{color}; height:100%; border-radius:6px; display:flex; align-items:center; justify-content:center; color:white; font-size:0.75rem; font-weight:600;">
                    {percent:.1f}%
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_weekly_goal():
    with stylable_container(
        key="meta-de-estudo-semanal",
        css_styles="""
        {
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px;

            div[data-testid="stHorizontalBlock"] { align-items: center; display: flex;}

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) > div > div { margin-left: auto;}

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) > div > div > div > button {
                height: 1.8rem;
                min-height: 1rem;
                width: 2rem;
            }
        }
        """
    ):        
        titulo, butao = st.columns([4, 1])

        with titulo:
            st.markdown(
                "<h2 style='font-weight:600; font-size:1.1rem; margin:0; padding:0;'>METAS DE ESTUDO SEMANAL</h2>",
                unsafe_allow_html=True
            )

        with butao:
            if st.button("𖣓", key="edit-button"):
                dialog_weekly_goal()


        user = get_current_user()
        if not user:
            st.info("Entre na sua conta para visualizar suas metas semanais.")
            return

        goal = get_weekly_goal(user["id"])
        if not goal:
            st.info("Nenhuma meta definida ainda. Clique no botão acima para criar uma.")
            return

        # --- Semana atual: segunda até domingo ---
        today = dt.date.today()
        start_week = today - dt.timedelta(days=today.weekday())  # segunda
        end_week = start_week + dt.timedelta(days=6)             # domingo

        # --- Cálculo de minutos estudados ---
        minutes_by_day = get_total_minutes_by_date_range(
            user["id"], start_week.isoformat(), end_week.isoformat()
        )
        total_minutes = sum(minutes_by_day.values())
        target_minutes = int(goal["target_hours"]) * 60

        # --- Cálculo de questões ---
        breakdown = get_questions_breakdown_by_date_range(
            user["id"], start_week.isoformat(), end_week.isoformat()
        )
        total_questions = sum((v["hits"] + v["mistakes"]) for v in breakdown.values())
        target_questions = int(goal["target_questions"])

        # --- Barras customizadas ---
        # Horas (mostra como 2h25min/40h00min)
        render_progress_bar(
            label="Horas de Estudo",
            value=total_minutes,
            target=target_minutes,
            color="#687364",
            value_label=minutes_to_hhmm(total_minutes),
            target_label=minutes_to_hhmm(target_minutes),
        )

        # Questões (mostra como 122/250)
        render_progress_bar(
            label="Questões",
            value=total_questions,
            target=target_questions,
            color="#687364",
            value_label=str(total_questions),
            target_label=str(target_questions),
        )