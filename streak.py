import streamlit as st
from streamlit_extras.stylable_container import stylable_container
import streamlit.components.v1 as components
from db import get_study_presence_since_signup
import datetime as dt


def _current_streak(presence: list[dict]) -> int:
    count = 0
    for d in reversed(presence):
        if d["has_study"]:
            count += 1
        else:
            break
    return count


def _build_grid_html(presence: list[dict]) -> str:
    css = f"""
        <style>
        html, body {{
            margin: 3px 0 0 0;
            padding: 2px 0 0 0;
        }}
        .streak-wrap{{ width:100%; }}
        .streak-grid{{ width:100%; }}

        .streak-row{{
            display:grid;
            /* n de colunas calculado no JS; cada coluna ocupa fração igual da largura */
            grid-template-columns: repeat(var(--cols, 10), 1fr);
            /* --cell serve só pro cálculo de quantas colunas cabem */
            --cell:46;
            /* faz o preenchimento começar pela direita (mais recente à direita) */
            direction: rtl;
        }}
        .streak-row,
        .streak-grid,
        .streak-wrap {{
            overflow: visible !important;
        }}

        .streak-cell{{
            /* sem largura fixa: a coluna (1fr) controla a largura para preencher 100% */
            width: auto;
            height:27px;
            position: relative; /* necessário para o caret ancorar na célula */
            display:flex;
            align-items:center;
            justify-content:center;
            font-size:12px;
            padding:3px 6px;
            box-sizing:border-box;
            border:1px solid #2a2a2a;
            overflow: visible;
            /* conteúdo não espelhado */
            direction: ltr;
        }}

        /* arredondar só primeiro e último (com RTL, first-child está à direita) */
        .streak-row .streak-cell:first-child {{
            border-top-right-radius:6px;
            border-bottom-right-radius:6px;
        }}
        .streak-row .streak-cell:last-child {{
            border-top-left-radius:6px;
            border-bottom-left-radius:6px;
        }}

        .ok{{background:#3C6F63;}}
        .ok .ico{{color:#BFE9D7;}}
        .fail{{background:#6B3B3B;}}
        .fail .ico{{color:#F5C7C7;}}
        .future{{background:#222; color:#BEBEBE;}}

        .ico{{font-weight:700;}}

        .streak-caret{{
            position:absolute; top:-10px; left:50%; z-index: 2;
            transform:translateX(-50%);
            width:0; height:0;
            border-left:6px solid transparent;
            border-right:6px solid transparent;
            border-top:6px solid #BEBEBE;
            pointer-events:none;
            filter: drop-shadow(0 1px 0 rgba(0,0,0,0.25));
        }}
        </style>
        """

    # monta as células reais (uma por dia) — presença invertida para mais recente primeiro
    cells_html = []
    for i, d in enumerate(reversed(presence)):
        klass = "ok" if d["has_study"] else "fail"
        mark = "✓" if d["has_study"] else "✕"
        date_obj = dt.datetime.strptime(d["date"], "%Y-%m-%d").date()
        title = date_obj.strftime("%d/%m/%Y")
        # seta somente na primeira célula (mais recente) -> fica à direita por causa do RTL
        caret = '<div class="streak-caret"></div>' if i == 0 else ""
        cells_html.append(
            f'<div class="streak-cell {klass}" title="{title}">{caret}<span class="ico">{mark}</span></div>'
        )

    # Script para calcular colunas, completar placeholders e reagir ao resize
    js = """
        <script>
        (function(){
        const row = document.querySelector('.streak-row');
        if(!row) return;

        function getCellSize(){
            // lê --cell da própria row (coerente com o CSS)
            const v = getComputedStyle(row).getPropertyValue('--cell');
            const n = parseInt(String(v).trim(), 10);
            return Number.isFinite(n) && n > 0 ? n : 46;
        }

        function setHeight(){
            // Altura real do conteúdo (row + pequenos buffers de borda)
            const h = Math.ceil(row.getBoundingClientRect().height) + 4;
            if (window.Streamlit && typeof window.Streamlit.setFrameHeight === 'function') {
              window.Streamlit.setFrameHeight(h);
            }
        }

        function layout(){
            // Remove placeholders anteriores
            row.querySelectorAll('.streak-cell.future').forEach(n => n.remove());

            const CELL = getCellSize();

            const wrap = row.closest('.streak-grid') || row.parentElement;
            const width = (wrap && wrap.clientWidth) ? wrap.clientWidth : row.clientWidth || 0;

            // calcula quantas colunas cabem com base na célula "nominal" (CELL)
            const cols = Math.max(1, Math.floor(width / CELL));

            // aplica cols via CSS var
            row.style.setProperty('--cols', cols);

            const total = row.querySelectorAll('.streak-cell:not(.future)').length;
            const remainder = total % cols;
            const toAdd = remainder === 0 ? 0 : (cols - remainder);

            for(let i=0;i<toAdd;i++){
              const div = document.createElement('div');
              div.className = 'streak-cell future';
              const today = new Date();
              div.title = today.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
              div.textContent = '';
              row.appendChild(div);
            }

            setHeight();
        }

        // roda agora e quando redimensionar
        layout();
        let rafId = null;
        window.addEventListener('resize', () => {
            if(rafId) cancelAnimationFrame(rafId);
            rafId = requestAnimationFrame(layout);
        });
        })();
        </script>
        """

    html = f"""
    {css}
    <div class="streak-wrap">
      <div class="streak-grid">
        <div class="streak-row">
            {''.join(cells_html)}
        </div>
      </div>
    </div>
    {js}
    """
    return html


def render_streak():
    user = st.session_state.get("user")
    if not user:
        return

    presence = get_study_presence_since_signup(user["id"])

    with stylable_container(
        key="streak",
        css_styles="""
        {
            display: block;
            background: #1A1A1A;
            border-radius: 12px;
            border: 1px solid #2a2a2a;
            padding: 10px 12px 14px 12px;
        }
        """
    ):
        st.markdown(
            '<h2 style="font-weight:600; font-size:1.1rem; margin:0; padding:0;">CONSTÂNCIA NOS ESTUDOS</h2>',
            unsafe_allow_html=True
        )

        if not presence:
            st.caption("Ainda não há dias de estudo para mostrar.")
            return

        streak_days = _current_streak(presence)
        st.markdown(
            f'<div style="margin:4px 0 8px 0; color:#D6D6D6; font-size:0.95rem;">Você está há <b>{streak_days} dia(s)</b> sem falhar!</div>',
            unsafe_allow_html=True
        )

        # altura pode crescer conforme o wrap quebra linhas; o JS ajusta dinamicamente
        components.html(_build_grid_html(presence), height=37, scrolling=False)
