# dialogs.py
import datetime as dt
import streamlit as st
from streamlit_extras.stylable_container import stylable_container

# ADICIONADOS:
from auth import get_current_user
from db import (
    create_study_record,
    get_user_created_date_cached,
    get_weekly_goal,          # NOVO
    upsert_weekly_goal        # NOVO
)

@st.dialog("Registro de Estudo", width="large")
def dialog_study_record():
    """
    Abre um diálogo para registrar um estudo.
    - Data mínima do date_input = data de criação da conta do usuário.
    - Validações: tempo > 0, categoria selecionada e disciplina preenchida.
    """

    # ==== Recupera usuário atual e calcula data mínima do seletor de data ====
    user = get_current_user()
    created_date = None
    if user:
        created_date_str = get_user_created_date_cached(user["id"])
        if created_date_str:
            try:
                created_date = dt.datetime.strptime(created_date_str, "%Y-%m-%d").date()
            except Exception:
                created_date = None  # fallback seguro

    # ===== LINHA 0: Data (pills + date_input) =====
    left, right = st.columns([3, 1])
    with left:
        # ---------- Opção B (on_change) para os pills de data ----------
        DATA_OPTIONS = ["Hoje", "Ontem", "Outro"]
        DATA_DEFAULT = "Hoje"

        # Guarda o último valor válido entre reruns
        st.session_state.setdefault("_last_modo_data_registro", DATA_DEFAULT)

        def _ensure_modo_data_selected():
            cur = st.session_state.get("modo_data_registro")
            if cur not in DATA_OPTIONS:
                # Se o usuário "desmarca" (None), restaura o último válido
                st.session_state["modo_data_registro"] = st.session_state["_last_modo_data_registro"]
            else:
                # Atualiza o último válido
                st.session_state["_last_modo_data_registro"] = cur

        # Monta kwargs sem conflitar default x session_state
        modo_kwargs = dict(
            label="Escolha uma data:",
            options=DATA_OPTIONS,
            selection_mode="single",
            label_visibility="collapsed",
            key="modo_data_registro",
            on_change=_ensure_modo_data_selected,
        )
        if "modo_data_registro" not in st.session_state:
            modo_kwargs["default"] = st.session_state["_last_modo_data_registro"]

        st.pills(**modo_kwargs)

        # Valor saneado (sempre um selecionado)
        modo_data = st.session_state.get("modo_data_registro", st.session_state["_last_modo_data_registro"])
        # ---------------------------------------------------------------------

    with right:
        if modo_data == "Outro":
            data_outro = st.date_input(
                "Selecione outra data",
                value=dt.date.today(),
                format="DD/MM/YYYY",
                label_visibility="collapsed",
                key="data_outro_registro",
                min_value=created_date or dt.date.today(),
                max_value=dt.date.today(),
            )
            st.session_state["study_date"] = data_outro
        else:
            base = dt.date.today()
            st.session_state["study_date"] = base if modo_data == "Hoje" else base - dt.timedelta(days=1)

            # Se a data calculada (Hoje/ Ontem) ficar ANTES da criação da conta, força para a mínima.
            if created_date and st.session_state["study_date"] < created_date:
                st.session_state["study_date"] = created_date

    # ===== Linha 01 =====
    c, d, t = st.columns([1, 2, 1])
    with c:
        categoria = st.selectbox(
            "Categoria",
            ["Teoria", "Revisão", "Questões", "Leitura de Lei", "Jurisprudência"],
            index=None,
            placeholder="Selecione..."
        )
    with d:
        disciplina = st.text_input("Disciplina")
    with t:
        tempo_estudo = st.time_input(
            "Tempo de Estudo",
            value=dt.time(0, 0),
            step=dt.timedelta(minutes=1),
            key="tempo_estudo"
        )

    # ===== Linha 02 =====
    topico = st.text_input("Conteúdo")

    # ===== Linha 03: Questões e Páginas =====
    col_q, col_p = st.columns(2)
    with col_q:
        with stylable_container(
            key="card_questoes",
            css_styles="""
                { border: 3px solid rgba(104,115,100,.4); border-radius: 12px; padding: 14px 16px; }
            """
        ):
            st.markdown('<p style="padding:0 0 1rem 0;">QUESTÕES</p>', unsafe_allow_html=True)
            q1, q2 = st.columns(2)
            with q1:
                acertos = st.number_input("Acertos", min_value=0, step=1, format="%d", key="num_acertos")
            with q2:
                erros = st.number_input("Erros", min_value=0, step=1, format="%d", key="num_erros")

    with col_p:
        with stylable_container(
            key="card_paginas",
            css_styles="""
                { border: 3px solid rgba(104,115,100,.4); border-radius: 12px; padding: 14px 16px; }
            """
        ):
            st.markdown('<p style="padding:0 0 1rem 0;">PÁGINAS</p>', unsafe_allow_html=True)
            p1, p2 = st.columns(2)
            with p1:
                inicio = st.number_input("Início", min_value=0, step=1, format="%d", key="pag_inicio")
            with p2:
                fim = st.number_input("Fim", min_value=0, step=1, format="%d", key="pag_fim")

    # ===== Linha 04: Comentário (textarea) =====
    comentario = st.text_area(
        "Comentário",
        value="",
        height=100,
        key="comentario_estudo",
    )

    st.markdown('<div style="padding:0 10px; margin-bottom:15px;"></div>', unsafe_allow_html=True)

    # ===== Regras para habilitar "Salvar" =====
    tempo_valido = (tempo_estudo.hour > 0) or (tempo_estudo.minute > 0) or (tempo_estudo.second > 0)
    categoria_valida = categoria is not None
    disciplina_valida = bool(disciplina.strip())

    pode_salvar = tempo_valido and categoria_valida and disciplina_valida

    # ===== Botões =====
    col1, col2 = st.columns(2)
    with col2:
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()
        with btn2:
            if st.button("Salvar", type="primary", use_container_width=True, disabled=not pode_salvar):
                # ----- MONTA PAYLOAD E SALVA -----
                if not user:
                    st.error("Você precisa estar logado para salvar o registro.")
                    st.stop()

                # Data de estudo como string YYYY-MM-DD (forçada a respeitar a data mínima)
                study_date = st.session_state.get("study_date", dt.date.today())
                if created_date and study_date < created_date:
                    study_date = created_date
                if study_date > dt.date.today():
                    study_date = dt.date.today()
                study_date_str = study_date.isoformat()

                # Tempo total em segundos
                duration_sec = tempo_estudo.hour * 3600 + tempo_estudo.minute * 60 + tempo_estudo.second

                try:
                    create_study_record(
                        user_id=user["id"],
                        study_date=study_date_str,
                        category=categoria,
                        subject=disciplina,
                        topic=topico,
                        duration_sec=duration_sec,
                        hits=int(acertos) if acertos is not None else None,
                        mistakes=int(erros) if erros is not None else None,
                        page_start=int(inicio) if inicio is not None else None,
                        page_end=int(fim) if fim is not None else None,
                        comment=comentario,
                    )
                    st.success("Registro salvo com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha ao salvar o registro: {e}")

@st.dialog("Definir Meta", width="small")
def dialog_weekly_goal():
    # Garante que só usuários logados editem metas
    user = get_current_user()
    if not user:
        st.error("Você precisa estar logado para definir suas metas semanais.")
        return

    # Carrega meta atual (se existir) para pré-preencher os inputs
    meta_atual = get_weekly_goal(user["id"]) or {"target_hours": 0, "target_questions": 0}
    valor_horas_inicial = int(meta_atual.get("target_hours", 0))
    valor_questoes_inicial = int(meta_atual.get("target_questions", 0))

    horas = st.number_input(
        "Quantas horas, em média, pretende estudar **por semana**?",
        min_value=0,
        step=1,
        format="%d",
        key="input-hrs",
        value=valor_horas_inicial
    )

    questoes = st.number_input(
        "Quantas questões, em média, pretende resolver **por semana**?",
        min_value=0,
        step=1,
        format="%d",
        key="input-qts",
        value=valor_questoes_inicial
    )

    col1, col2 = st.columns(2)
    with col2:
        btn1, btn2 = st.columns(2)
        with btn1:
            if st.button("Cancelar", use_container_width=True):
                st.rerun()

        with btn2:
            if st.button("Salvar", type="primary", use_container_width=True):
                upsert_weekly_goal(user_id=user["id"], target_hours=int(horas), target_questions=int(questoes))
                st.rerun()
