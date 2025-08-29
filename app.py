import streamlit as st
from datetime import datetime

from utils import local_css
from painel import render_painel
from streak import render_streak
from dialogs import dialog_study_record
from auth import render_auth_gate, logout
from day_studies import render_day_studies
from weekly_goal import render_weekly_goal
from weekly_study import render_weekly_study
from db import get_study_records_by_user_cached, delete_study_record


st.set_page_config(
    page_title="Estudo Operacional",
    page_icon="assets/images/logo.png",
    layout="wide"
)

st.session_state.setdefault("_compact", False)

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

# ===== Linha 01 (100%): CONSTÂNCIA NOS ESTUDOS =====
render_streak()

# ===== Grade principal (2 "linhas" conceituais) =====
# Esquerda (larga) = PAINEL (ocupa "linhas" 1 e 2)
# Meio (estreita)  = METAS (em cima) + ESTUDO SEMANAL (embaixo)
# Direita (média)  = ESTUDOS DO DIA (ocupa "linhas" 1 e 2)
col_left, col_mid, col_right = st.columns([2.1, 1.9, 1])

with col_left:
    # PAINEL ocupa toda a altura da coluna esquerda
    render_painel()

with col_mid:
    # Linha "de cima" da coluna do meio
    render_weekly_goal()
    # Linha "de baixo" da coluna do meio
    render_weekly_study()

with col_right:
    # Ocupa a coluna direita inteira
    render_day_studies()

# ===== Registros de estudo =====
st.markdown("---")
st.subheader("Meus Registros de Estudo")

if user:
    records = get_study_records_by_user_cached(user["id"])
    if not records:
        st.info("Nenhum registro encontrado.")
    else:
        for r in records:
            # formata data
            try:
                dt_br = datetime.strptime(r["study_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                dt_br = r["study_date"]
            header = f"{dt_br} - {r.get('category','')}: {r.get('subject','')}"

            # Cabeçalho com expander + botão lixeira alinhado à direita
            head_left, head_right = st.columns([29, 1])
            with head_left:
                exp = st.expander(header)
            with head_right:
                if st.button("🗑️", key=f"delete-{r['id']}"):
                    ok = delete_study_record(r["id"], user["id"])
                    if ok:
                        st.toast("Registro excluído com sucesso.")
                        st.rerun()
                    else:
                        st.error("Não foi possível excluir este registro.")

            # Conteúdo dentro do expander
            with exp:
                dur_h = r["duration_sec"] // 3600
                dur_m = (r["duration_sec"] % 3600) // 60
                st.write(f"**Duração:** {dur_h}h {dur_m}min")

                if (r.get("topic") or "").strip():
                    st.write(f"**Conteúdo:** {r['topic']}")

                if (r.get("hits") or 0) > 0 or (r.get("mistakes") or 0) > 0:
                    st.write(f"**Questões:** {r.get('hits') or 0} acertos / {r.get('mistakes') or 0} erros")

                if r.get("page_start") or r.get("page_end"):
                    st.write(f"**Páginas:** {r.get('page_start') or '-'} até {r.get('page_end') or '-'}")

                if (r.get("comment") or "").strip():
                    st.write(f"**Comentário:** {r['comment']}")

                st.caption(f"Salvo em {r['created_at']}")
