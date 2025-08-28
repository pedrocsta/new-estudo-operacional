# auth.py
import streamlit as st
import bcrypt
from typing import Optional, Dict, Any
from db import init_db, get_user_by_email, create_user

# -------------- Helpers de segurança --------------

def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

def verify_password(password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except Exception:
        return False

# -------------- Sessão --------------

def get_current_user() -> Optional[Dict[str, Any]]:
    return st.session_state.get("user")

def set_current_user(user: Dict[str, Any]) -> None:
    st.session_state["user"] = {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
    }

def logout():
    st.session_state.pop("user", None)
    st.toast("Você saiu da conta.")

# -------------- UI de login/cadastro --------------

def _login_view():
    st.subheader("Entrar")
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if submit:
        if not email or not password:
            st.error("Preencha e‑mail e senha.")
            return

        user = get_user_by_email(email)
        if not user:
            st.error("E‑mail não encontrado.")
            return

        if not verify_password(password, user["password_hash"]):
            st.error("Senha incorreta.")
            return

        set_current_user(user)
        st.success(f"Bem-vindo(a), {user['first_name']}!")
        st.rerun()

def _signup_view():
    st.subheader("Criar conta")
    with st.form("signup_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            first_name = st.text_input("Nome")
        with c2:
            last_name = st.text_input("Sobrenome")
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        password2 = st.text_input("Confirme a senha", type="password")
        submit = st.form_submit_button("Cadastrar", use_container_width=True)

    if submit:
        if not (first_name and last_name and email and password and password2):
            st.error("Preencha todos os campos.")
            return
        if len(password) < 6:
            st.error("A senha deve ter pelo menos 6 caracteres.")
            return
        if password != password2:
            st.error("As senhas não conferem.")
            return

        if get_user_by_email(email):
            st.error("Já existe uma conta com este e‑mail.")
            return

        pw_hash = hash_password(password)
        user_id = create_user(first_name, last_name, email, pw_hash)
        st.success("Conta criada! Faça login para continuar.")
        # opcional: já loga após criar
        user = get_user_by_email(email)
        if user:
            set_current_user(user)
            st.rerun()

def render_auth_gate() -> bool:
    """
    Renderiza a tela de login/cadastro se não houver usuário logado.
    Retorna True se o usuário está autenticado; False caso contrário.
    """
    init_db()  # garante a tabela

    user = get_current_user()
    if user:
        return True

    # Tela pública (não logado)
    st.markdown(
        '<h2 style="font-weight:600; font-size:2.8rem; margin:0; padding:0;">Estudo Operacional</h2>',
        unsafe_allow_html=True
    )
    st.caption("Acesse sua conta para ver seu painel de estudos.")

    tab1, tab2 = st.tabs(["Entrar", "Criar conta"])
    with tab1:
        _login_view()
    with tab2:
        _signup_view()

    return False
