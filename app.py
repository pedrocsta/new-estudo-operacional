import streamlit as st

from utils import local_css
from painel import render_painel
from streak import render_streak
from dialogs import dialog_study_record
from auth import render_auth_gate, logout
from day_studies import render_day_studies
from weekly_goal import render_weekly_goal
from weekly_study import render_weekly_study
from db import get_study_records_by_user, delete_study_record

st.set_page_config(
    page_title="Estudo Operacional",
    page_icon="assets/images/logo.png",
    layout="wide"
)

local_css()

# ⬇️ BLOQUEIA O APP SE NÃO ESTIVER LOGADO
if not render_auth_gate():
    st.stop()

# ----------------- CONTEÚDO PRIVADO -----------------
user = st.session_state.get("user")

if user:
    full_name = f"{user['first_name']} {user['last_name']}"
    with st.popover(full_name):
        if st.button("Sair", use_container_width=True):
            logout()
            st.rerun()

title, button = st.columns([1, 1])
with title:
    st.markdown(
        '<h2 style="font-weight:600; font-size:2rem; margin:0; padding:0;">Home</h2>',
        unsafe_allow_html=True
    )

with button:
    if st.button("Adicionar Estudo", type="primary", key="adicionar-estudos"):
        dialog_study_record()

st.markdown(
    '<div style="padding: 0 10px; margin-bottom:15px; border-bottom:1px solid #2A2A2A;"></div>',
    unsafe_allow_html=True
)

# ===== Linha 01: CONSTÂNCIA NOS ESTUDOS (100%) =====
render_streak()

# ===== Linhas 02 e 03 combinadas: Esquerda empilhada / Direita ocupando a altura toda =====
col_esq, col_dir = st.columns([3, 1])  # ajuste as proporções como preferir

with col_esq:
    # Faixa superior da coluna esquerda
    meta_semanal, estudo_semanal = st.columns([1, 2])
    with meta_semanal:
        render_weekly_goal()
    with estudo_semanal:
        render_weekly_study()

    # Faixa inferior da coluna esquerda (ocupa toda a largura da esquerda)
    render_painel()

with col_dir:
    # Coluna direita deve ocupar a altura inteira “ao lado” das duas faixas da esquerda
    render_day_studies()

# ===== Registros de estudo =====
st.markdown("---")
st.subheader("Meus Registros de Estudo")

if user:
    records = get_study_records_by_user(user["id"])
    if not records:
        st.info("Nenhum registro encontrado.")
    else:
        for r in records:
            with st.expander(f"{r['study_date']} • {r['category']} - {r['subject']}"):
                ac_left, ac_right = st.columns([8, 2])
                with ac_right:
                    if st.button("🗑️ Excluir", key=f"delete-{r['id']}", use_container_width=True):
                        ok = delete_study_record(r["id"], user["id"])
                        if ok:
                            st.toast("Registro excluído com sucesso.")
                            st.rerun()
                        else:
                            st.error("Não foi possível excluir este registro.")

                st.write(f"**Conteúdo:** {r.get('topic') or '-'}")
                st.write(f"**Duração:** {r['duration_sec']//3600}h {(r['duration_sec']%3600)//60}min")
                st.write(f"**Questões:** {r.get('hits') or 0} acertos / {r.get('mistakes') or 0} erros")
                st.write(f"**Páginas:** {r.get('page_start') or '-'} até {r.get('page_end') or '-'}")
                st.write(f"**Comentário:** {r.get('comment') or '-'}")
                st.caption(f"Salvo em {r['created_at']}")
