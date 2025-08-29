import datetime as dt
from datetime import timedelta
import pandas as pd
import altair as alt
import streamlit as st
from streamlit_extras.stylable_container import stylable_container

from auth import get_current_user
from db import (
    get_user_created_date_cached,
    get_total_minutes_by_date_range_cached,
    get_questions_breakdown_by_date_range_cached
)
from utils import week_range_starting_sunday, fmt_horas


WEEKDAY_LABELS_PT = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SAB"]


def _sunday_of_week(d: dt.date) -> dt.date:
    back = (d.weekday() + 1) % 7  # Monday=0 ... Sunday=6
    return d - dt.timedelta(days=back)


def _clamp(date_val: dt.date, min_d: dt.date, max_d: dt.date) -> dt.date:
    return max(min_d, min(max_d, date_val))


def render_weekly_study():
    user = get_current_user()
    if not user:
        return

    # -------------------- Config. de Pills (Opção B) --------------------
    OPTIONS = ["TEMPO", "QUESTÕES"]
    DEFAULT_PILL = "TEMPO"

    # Garante um "último válido" desde o primeiro run
    st.session_state.setdefault("_last_pill_semana", DEFAULT_PILL)

    # Antes de renderizar qualquer coisa, clamp do valor atual para evitar None
    current_sel = st.session_state.get("pill-semana", st.session_state["_last_pill_semana"])
    if current_sel not in OPTIONS:
        current_sel = st.session_state["_last_pill_semana"]
        st.session_state["pill-semana"] = current_sel  # mantém consistência de estado
    # -------------------------------------------------------------------

    today = dt.date.today()

    created = None
    if user:
        created_str = get_user_created_date_cached(user["id"])
        if created_str:
            try:
                created = dt.datetime.strptime(created_str, "%Y-%m-%d").date()
            except Exception:
                created = None

    min_week_start = _sunday_of_week(created or today)
    max_week_start = _sunday_of_week(today)

    if "week_start" not in st.session_state:
        st.session_state.week_start = max_week_start

    st.session_state.week_start = _clamp(st.session_state.week_start, min_week_start, max_week_start)

    week_start = st.session_state.week_start
    week_end = week_start + dt.timedelta(days=6)

    can_prev = week_start > min_week_start
    can_next = week_start < max_week_start

    with stylable_container(
        key="estudo-semanal",
        css_styles="""
        {
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px;

            /* layout do cabeçalho */
            div[data-testid="stHorizontalBlock"] { align-items: center; display: flex; text-align: center; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) > div > div { margin-left: auto; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) > div > div { margin-left: auto; }
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(3) > div > div { margin-right: auto; }

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] > div { gap: 0; }

            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
                flex: 0 0 auto !important;
                max-width: fit-content !important;
            }

            .st-key-btn-prev-week button, .st-key-btn-next-week button {
                height: 1.8rem !important;
                min-height: 1rem !important;
                width: 2rem;
            }

            .st-key-pill-semana button { width: 100%;}

            div[data-testid="stElementToolbar"] { display: none; }
            div[data-testid="stVegaLiteChart"] details { display: none; }
        }
        """
    ):
        # ---- Título + navegação ----
        titulo, butao = st.columns([1, 1])
        with titulo:
            st.markdown(
                "<h2 style='font-weight:600; font-size:1.1rem; margin:0; padding:0;'>ESTUDOS SEMANAL</h2>",
                unsafe_allow_html=True
            )

        with butao:
            st.markdown('<div class="header-week">', unsafe_allow_html=True)

            btn_prev, date, btn_next = st.columns([1, 5, 1])

            with btn_prev:
                if st.button("⭠", key="btn-prev-week", disabled=not can_prev):
                    st.session_state.week_start = _clamp(
                        week_start - dt.timedelta(days=7),
                        min_week_start,
                        max_week_start
                    )
                    st.rerun()

            with date:
                st.markdown(f"{week_start.strftime('%d/%m/%Y')} – {week_end.strftime('%d/%m/%Y')}")

            with btn_next:
                if st.button("⭢", key="btn-next-week", disabled=not can_next):
                    st.session_state.week_start = _clamp(
                        week_start + dt.timedelta(days=7),
                        min_week_start,
                        max_week_start
                    )
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        with stylable_container(
            key="estudo-semanasasal",
            css_styles="""
            {
                padding: 5px 0 15px 0;
            }
            """
        ):
            grafico, acoes = st.columns([3, 1])

            with grafico:
                sunday, saturday = week_range_starting_sunday(week_start)
                week_dates = [sunday + timedelta(days=i) for i in range(7)]
                week_keys = [d.strftime("%Y-%m-%d") for d in week_dates]

                # Valor SEMPRE saneado (garantido acima)
                sel = current_sel

                # Altura usada nos dois gráficos (e na conversão px -> unidades do eixo Y)
                CHART_HEIGHT = 180 if st.session_state.get("_compact") else 200

                if sel == "TEMPO":
                    totals_dict = get_total_minutes_by_date_range_cached(user["id"], week_keys[0], week_keys[-1])
                    minutos = [totals_dict.get(k, 0) for k in week_keys]
                    horas = [m / 60.0 for m in minutos]
                    tempo_fmt = [fmt_horas(m) for m in minutos]

                    # topo DINÂMICO (mínimo 1h; arredonda para 0.5h)
                    import math
                    max_h = max(horas) if horas else 0.0
                    raw_top = max(1.0, max_h * 1.10)
                    top_hours = math.ceil(raw_top * 2.0) / 2.0

                    df = pd.DataFrame({
                        "label": WEEKDAY_LABELS_PT,
                        "valor": horas,
                        "tooltip": tempo_fmt,
                    })

                    # seleção de hover por dia
                    hover_time = alt.selection_point(on="mouseover", empty="none", fields=["label"])

                    chart = (
                        alt.Chart(df)
                        .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8)
                        .encode(
                            x=alt.X(
                                "label:N",
                                sort=WEEKDAY_LABELS_PT,
                                axis=alt.Axis(
                                    title=None, labelColor="#EDEDED", tickColor="#1A1A1A", labelAngle=0
                                ),
                            ),
                            y=alt.Y(
                                "valor:Q",
                                scale=alt.Scale(domain=[0, top_hours], nice=False),
                                axis=alt.Axis(
                                    title=None,
                                    grid=True, gridColor="#2a2a2a", tickColor="#2a2a2a",
                                    labelColor="#EDEDED",
                                    tickCount=5,
                                ),
                            ),
                            color=alt.value("#51594E"),
                            opacity=alt.condition(hover_time, alt.value(1.0), alt.value(0.8)),
                            tooltip=[alt.Tooltip("tooltip:N", title="Tempo:")],
                        )
                        .add_params(hover_time)
                        .properties(height=CHART_HEIGHT, padding={"left": 0, "right": 10, "top": 0, "bottom": 0})
                        .configure_view(stroke=None, fill="#1A1A1A")
                        .configure(background="#1A1A1A")
                    )

                else:
                    brk = get_questions_breakdown_by_date_range_cached(user["id"], week_keys[0], week_keys[-1])

                    hits = [brk.get(k, {}).get("hits", 0) for k in week_keys]
                    mistakes = [brk.get(k, {}).get("mistakes", 0) for k in week_keys]
                    totals = [h + m for h, m in zip(hits, mistakes)]

                    df = pd.DataFrame({
                        "label": WEEKDAY_LABELS_PT * 2,
                        "tipo": (["Acertos"] * 7) + (["Erros"] * 7),
                        "valor": hits + mistakes,
                    })

                    max_total = max(totals) if totals else 0
                    top = max(10, ((max_total + 9) // 10) * 10)

                    common_tooltip = [
                        alt.Tooltip("tipo:N", title="Tipo:"),
                        alt.Tooltip("valor:Q", title="Quantidade:", format="d"),
                    ]

                    base = alt.Chart(df).transform_calculate(
                        # 0 = Acertos (embaixo), 1 = Erros (em cima)
                        tipo_order="datum.tipo === 'Erros' ? 1 : 0"
                    )

                    # seleção de hover por dia + tipo
                    hover_q = alt.selection_point(on="mouseover", empty="none", fields=["label", "tipo"])

                    # barras empilhadas (cores fixas) + hover por OPACIDADE
                    bars = base.mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
                        x=alt.X(
                            "label:N",
                            sort=WEEKDAY_LABELS_PT,
                            axis=alt.Axis(title=None, labelColor="#EDEDED", tickColor="#1A1A1A", labelAngle=0),
                        ),
                        y=alt.Y(
                            "valor:Q",
                            stack="zero",
                            scale=alt.Scale(domain=[0, top], nice=False),
                            axis=alt.Axis(
                                title=None, grid=True, gridColor="#2a2a2a", tickColor="#2a2a2a",
                                labelColor="#EDEDED", tickCount=5
                            ),
                        ),
                        color=alt.Color(
                            "tipo:N",
                            scale=alt.Scale(domain=["Acertos", "Erros"], range=["#51594E", "#733636"]),
                            legend=None,
                        ),
                        opacity=alt.condition(hover_q, alt.value(1.0), alt.value(0.8)),
                        order=alt.Order("tipo_order:Q", sort="ascending"),
                        tooltip=common_tooltip,
                    ).add_params(hover_q)

                    # ===== Mostrar número só quando o segmento tiver altura suficiente =====
                    FONT_SIZE = 12
                    PX_NEEDED = FONT_SIZE
                    min_val_for_label = top * (PX_NEEDED / CHART_HEIGHT)

                    labels = (
                        base
                        .transform_stack(
                            stack="valor",
                            groupby=["label"],
                            sort=[alt.SortField("tipo_order", order="ascending")],
                            as_=["y0", "y1"],
                            offset="zero",
                        )
                        .transform_filter("datum.valor > 0")
                        .transform_filter(f"datum.y1 - datum.y0 >= {min_val_for_label}")
                        .transform_calculate(y_mid="(datum.y0 + datum.y1) / 2")
                        .mark_text(color="white", fontSize=FONT_SIZE, fontWeight="bold")
                        .encode(
                            x=alt.X("label:N", sort=WEEKDAY_LABELS_PT),
                            y=alt.Y("y_mid:Q"),
                            text=alt.Text("valor:Q"),
                            order=alt.Order("tipo_order:Q", sort="ascending"),
                            tooltip=common_tooltip,
                            opacity=alt.condition(hover_q, alt.value(1.0), alt.value(0.8)),
                        )
                    )

                    chart = (bars + labels).properties(
                        height=CHART_HEIGHT, padding={"left": 0, "right": 10, "top": 0, "bottom": 0}
                    ).configure_view(stroke=None, fill="#1A1A1A"
                    ).configure(background="#1A1A1A")

                st.altair_chart(chart, use_container_width=True)

            with acoes:
                # Função de validação do estado (Opção B)
                def _ensure_pill_selected():
                    cur = st.session_state.get("pill-semana")
                    if cur not in OPTIONS:
                        st.session_state["pill-semana"] = st.session_state["_last_pill_semana"]
                    else:
                        st.session_state["_last_pill_semana"] = cur

                st.pills(
                    label="Escolha um tipo de gráfico:",
                    options=OPTIONS,
                    selection_mode="single",
                    default=st.session_state["_last_pill_semana"],
                    label_visibility="collapsed",
                    key="pill-semana",
                    on_change=_ensure_pill_selected,
                )
