import streamlit as st
from pathlib import Path
from datetime import date, timedelta

def local_css(rel_path: str = "assets/styles/styles.css") -> None:
    css_path = Path(rel_path) 
    if not css_path.exists():
        st.error(f"CSS não encontrado: {css_path}")
        return
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def week_range_starting_sunday(d: date) -> tuple[date, date]:
    """Retorna (domingo, sábado) da semana de d."""
    back = (d.weekday() + 1) % 7  # Monday=0 ... Sunday=6
    sunday = d - timedelta(days=back)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday

def fmt_horas(minutos: int) -> str:
    """Formata minutos como '00h00min' obrigatoriamente."""
    h, m = divmod(int(minutos), 60)
    return f"{h:02d}h{m:02d}min"