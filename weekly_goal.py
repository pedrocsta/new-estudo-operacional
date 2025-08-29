# weekly_goal.py
import streamlit as st
from streamlit_extras.stylable_container import stylable_container
from dialogs import dialog_weekly_goal

from auth import get_current_user
from db import (
    get_weekly_goal,
    get_total_minutes_by_date_range,
    get_questions_breakdown_by_date_range,
)
import datetime as dt
import textwrap


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
    """
    Barra de progresso compacta com a % centralizada dentro da parte preenchida.
    - Usa min-width para que 0.0% fique visível mesmo com 0%.
    - Dedent para evitar que o HTML seja renderizado como 'código' pelo Markdown.
    """
    # Percentual (cap em 0..100)
    percent = 0.0 if target <= 0 else (value / target) * 100.0
    percent = max(0.0, min(percent, 100.0))
    percent_text = f"{percent:.1f}%"

    # Texto à direita do cabeçalho
    right_value = value_label if value_label is not None else str(value)
    right_target = target_label if target_label is not None else (str(target) if target > 0 else "-")
    right_text = f"{right_value}/{right_target}"

    # Largura mínima (px) para caber "0.0%"
    MIN_PX = 35

    html = textwrap.dedent(f"""
    <div style="margin:0;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-weight:600; font-size:.92rem; opacity:.95;">{label}</span>
        <span style="font-weight:600; font-size:.88rem; opacity:.95;">{right_text}</span>
      </div>

      <div style="background:#2A2A2A; border-radius:8px; height:18px; overflow:hidden; position:relative;">
        <div style="
              width:{percent:.4f}%;
              min-width:{MIN_PX}px;
              background:{color};
              height:100%;
              border-radius:8px;
              display:flex; align-items:center; justify-content:center;
              font-size:.78rem; font-weight:700; color:#FFFFFF; opacity:.95;">
          {percent_text}
        </div>
      </div>
    </div>
    """).strip()

    st.markdown(html, unsafe_allow_html=True)


def render_weekly_goal():
    with stylable_container(
        key="meta-de-estudo-semanal",
        css_styles="""
        {
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px;

            div[data-testid="stHorizontalBlock"] { align-items: center; display: flex; }

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) > div > div { margin-left: auto; }

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2)] { justify-content:flex-end; }
            div[data-testid="stButton"] > button {
                height: 1.8rem !important;
                min-height: 1rem !important;
                width: 2rem;
                gap: 0;
            }
        }
        """
    ):
        titulo, butao = st.columns([4, 1])

        with titulo:
            st.markdown(
                "<h2 style='font-weight:600; font-size:1.05rem; margin:0; padding:0;'>METAS DE ESTUDO SEMANAL</h2>",
                unsafe_allow_html=True,
            )

        with butao:
            if st.button("𖣓", key="edit-button"):
                dialog_weekly_goal()

        user = get_current_user()
        if not user:
            st.info("Entre na sua conta para visualizar suas metas semanais.")
            return

        # Se o usuário ainda não tem metas, trate como 0 por padrão
        goal = get_weekly_goal(user["id"]) or {"target_hours": 0, "target_questions": 0}

        # Semana atual (segunda → domingo)
        today = dt.date.today()
        start_week = today - dt.timedelta(days=today.weekday())
        end_week = start_week + dt.timedelta(days=6)

        # Minutos estudados na semana
        minutes_by_day = get_total_minutes_by_date_range(
            user["id"], start_week.isoformat(), end_week.isoformat()
        )
        total_minutes = sum(minutes_by_day.values())
        target_minutes = int(goal["target_hours"]) * 60

        # Questões na semana
        breakdown = get_questions_breakdown_by_date_range(
            user["id"], start_week.isoformat(), end_week.isoformat()
        )
        total_questions = sum((v["hits"] + v["mistakes"]) for v in breakdown.values())
        target_questions = int(goal["target_questions"])

        # Barras (porcentagem dentro; com min-width para sempre exibir "0.0%")
        render_progress_bar(
            label="Horas de Estudo",
            value=total_minutes,
            target=target_minutes,
            color="#687364",
            value_label=minutes_to_hhmm(total_minutes),
            target_label=minutes_to_hhmm(target_minutes),
        )

        render_progress_bar(
            label="Questões",
            value=total_questions,
            target=target_questions,
            color="#687364",
            value_label=str(total_questions),
            target_label=str(target_questions),
        )
