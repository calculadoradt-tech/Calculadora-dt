import re
import unicodedata
from functools import partial
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components
# ======================== 1. CONFIGURAÇÃO E CONSTANTES ========================
PAGE_TITLE = "Calculadora de Ensaios Físicos"
PAGE_ICON = "🧪"

PG_INICIO = "Inicio"
PG_LINHAS = "Linha de Produtos"
LINHAS_PRODUTOS = ("Basecoat", "Graute", "Rejunte", "Revestimento")

# --- DEFINIÇÃO DOS ENSAIOS DISPONÍVEIS ---
REQ_RETENCAO = "RETENÇÃO DE ÁGUA (%) - ABNT NBR 13277"
REQ_DENSIDADE = "DENSIDADE NO ESTADO FRESCO (kg/m³) - ABNT NBR 13278"
REQ_FLEXAO = "FLEXÃO 4x4x16 (MPa) - ABNT NBR 13279:2005"
REQ_COMPRESSAO_PRISMA = "COMPRESSÃO 4x4x16 (MPa) - ABNT NBR 13279:2005"
REQ_COMPRESSAO_CILINDRICA = "COMPRESSÃO 5x10 (MPa) - ABNT NBR 7215" # Novo para Graute/Rejunte
REQ_VAR_DIM = "VARIAÇÃO DIMENSIONAL (mm/m) - ABNT NBR 15261"
REQ_VAR_MASSA = "VARIAÇÃO DE MASSA (%) - ABNT NBR 15261"
REQ_CAPILARIDADE = "CAPILARIDADE (g/dm²·min^0,5) - ABNT NBR 15259"
REQ_ADERENCIA_AUTO = "POTENCIAL DE ADERÊNCIA (MPa) - ABNT NBR 15258 - Automática"
REQ_ADERENCIA_MANUAL = "POTENCIAL DE ADERÊNCIA (MPa) - ABNT NBR 15258 - Manual"
REQ_PERMEABILIDADE = "PERMEABILIDADE 48h (mL/cm³) - ABNT NBR 16648 anexo C"
REQ_RETRACAO = "RETRAÇÃO (%) - Baseado na ABNT NBR 15261"

# --- CONFIGURAÇÃO POR PRODUTO (Baseada nas Planilhas) ---
REQUISITOS = {
    "Basecoat": [
        REQ_RETENCAO,
        REQ_DENSIDADE,
        REQ_FLEXAO,
        REQ_COMPRESSAO_PRISMA, # Basecoat usa Prisma
        REQ_VAR_DIM,
        REQ_VAR_MASSA,
        REQ_CAPILARIDADE,
        REQ_ADERENCIA_AUTO,
        REQ_PERMEABILIDADE,
        REQ_RETRACAO
    ],
    "Graute": [
        # Planilha Graute: Foco em Densidade, Expansão e Compressão
        REQ_DENSIDADE,
        REQ_COMPRESSAO_CILINDRICA, # NBR 7215 (5x10)
        REQ_VAR_DIM,               # Expansão
        REQ_VAR_MASSA
    ],
    "Rejunte": [
        # Planilha Rejunte: Identificado NBR 7215 (Cilíndrica) e NBR 14992 (Retenção)
        REQ_RETENCAO,
        REQ_DENSIDADE,
        REQ_COMPRESSAO_CILINDRICA, # Rejunte na planilha usa 5x10
        REQ_VAR_DIM,
        REQ_CAPILARIDADE,
        REQ_PERMEABILIDADE,
        REQ_RETRACAO
    ],
    "Revestimento": [
        # Padrão Argamassa Colante/Revestimento
        REQ_RETENCAO,
        REQ_DENSIDADE,
        REQ_FLEXAO,
        REQ_COMPRESSAO_PRISMA,
        REQ_ADERENCIA_MANUAL,
        REQ_ADERENCIA_AUTO,
        REQ_CAPILARIDADE,
        REQ_VAR_DIM
    ]
}

# --- LIMITES E TOLERÂNCIAS (Extraídos das Planilhas) ---

# --- Medidas feitas em milimetros.
#=========================================================//=================================================================

CONFIG_LIMITES = {
    "padrao": {
        "flexao_var_max": 0.3,
        "compressao_var_max": 0.5,
        "variacao_dim_max": 0.20,
        "compressao_cilindrica_var_pct": 6.0,
        "aderencia_var_pct": 30.0,
        "min_cps_aderencia": 6,
        "capilaridade_var_pct": 20.0,
        "retracao_var_pct": 20.0,
        "permeabilidade_var_pct": 30.0,
        "comprimento_padrao": 250.0 
    },
    "Basecoat": {
        "flexao_var_max": 0.3,
        "compressao_var_max": 0.5,
        "variacao_dim_max": 0.20,
        "aderencia_var_pct": 30.0,
        "permeabilidade_var_pct": 30.0,
        "comprimento_padrao": 160.0 
    },
    "Graute": {
        "compressao_cilindrica_var_pct": 6.0,
        "variacao_dim_max": 0.20,
        # Calculado com base na planilha (0.18mm diff -> 1.38 mm/m)
        "comprimento_padrao": 130.43 
    },
    "Rejunte": {
        "compressao_cilindrica_var_pct": 6.0,
        "variacao_dim_max": 0.20,
        "comprimento_padrao": 160.0 
    },
    "Revestimento": {
        "flexao_var_max": 0.3,
        "compressao_var_max": 0.5,
        "variacao_dim_max": 0.20,
        "capilaridade_var_pct": 20.0,
        "aderencia_var_pct": 30.0,
        "comprimento_padrao": 160.0 
    }
}

def obter_config(chave_limite):
    """Retorna o valor do limite para o produto atual selecionado."""
    produto = st.session_state.get("produto", "padrao")
    # Se o produto não estiver no dict, usa o padrao
    config_produto = CONFIG_LIMITES.get(produto, CONFIG_LIMITES["padrao"])
    return config_produto.get(chave_limite, CONFIG_LIMITES["padrao"][chave_limite])

# ======================== 2. UTILITÁRIOS ========================

def configurar_pagina():
    """Configura o cabeçalho e estilo global da página."""
    st.set_page_config(page_title=PAGE_TITLE, page_icon=PAGE_ICON, layout="centered")
    st.markdown(
        """
        <style>
        div.stButton > button[kind="primary"] {background-color:#d32f2f;color:white;border:0}
        div.stButton > button:not([kind="primary"]) {background-color:#00695c;color:white;border:0}
        </style>
        """,
        unsafe_allow_html=True,
    )

def norm(txt: str) -> str:
    """Normaliza texto para comparação (remove acentos e caracteres especiais)."""
    s = unicodedata.normalize("NFKD", txt)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

def slugify(txt: str) -> str:
    """Cria um slug para IDs de página (ex: Retenção de Água -> retencao-de-agua)."""
    s = unicodedata.normalize("NFKD", txt)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)

def navegar_para(page_id: str):
    """Atualiza o estado para trocar de página."""
    st.session_state.pagina = page_id
    # st.rerun() # Opcional: força recarregamento imediato em versões mais novas do Streamlit

def inicializar_estado():
    """Inicializa variáveis de sessão se não existirem."""
    if "pagina" not in st.session_state:
        st.session_state.pagina = PG_INICIO
    if "produto" not in st.session_state:
        st.session_state.produto = None
    if "req_por_linha" not in st.session_state:
        st.session_state.req_por_linha = {l: None for l in LINHAS_PRODUTOS}

# ... (após a função inicializar_estado)

def obter_proximo_calculo():
    """Descobre qual é o ID da próxima página com base na lista de requisitos."""
    linha = st.session_state.get("produto")
    pag_atual = st.session_state.get("pagina")
    
    if not linha or not pag_atual or linha not in REQUISITOS:
        return None
        
    # Gera a lista de IDs para esta linha de produtos
    lista_reqs = REQUISITOS[linha]
    ids_ordenados = []
    
    for req in lista_reqs:
        id_pag = deciding_destino_calculo_wrapper(linha, req) # Usa wrapper para evitar erro de definição
        ids_ordenados.append(id_pag)
        
    # Encontra onde estamos e pega o próximo
    try:
        idx = ids_ordenados.index(pag_atual)
        if idx < len(ids_ordenados) - 1:
            return ids_ordenados[idx + 1] 
    except ValueError:
        pass 
    return None





def inject_hotkeys():
    """Script invisível que clica no botão 'Próximo' ao apertar Ctrl."""
    js = """
    <script>
    const doc = window.parent.document;
    doc.addEventListener('keydown', function(e) {
        if (e.key === 'Control') {
            const buttons = doc.querySelectorAll('button[kind="primary"]');
            buttons.forEach(btn => {
                if (btn.innerText.includes("⮕")) {
                    btn.click();
                }
            });
        }
    });
    </script>
    """
    components.html(js, height=0, width=0)

# Função auxiliar para resolver a ordem de definição do Python
def deciding_destino_calculo_wrapper(linha, req):
    # Tenta chamar a função original se ela já estiver definida
    if 'decidir_destino_calculo' in globals():
        return decidir_destino_calculo(linha, req)
    return f"{linha}::{slugify(req)}" # Fallback simples


# ======================== 3. COMPONENTES DE UI ========================


def ui_sidebar():
    """Renderiza a barra lateral."""
    st.sidebar.title("Quartzolit")
    
    # Navegação Rápida
    if st.session_state.pagina in (PG_INICIO, PG_LINHAS):
        opcoes = [PG_INICIO, PG_LINHAS]
        idx = opcoes.index(st.session_state.pagina) if st.session_state.pagina in opcoes else 0
        escolha = st.sidebar.radio(
        "Navegação", 
        opcoes, 
        index=idx, 
        key="navegacao_lateral_unica" # <--- A chave única resolve o conflito
    )
        if escolha != st.session_state.pagina:
            navegar_para(escolha)
            st.rerun()
    else:
        # Botão de voltar simples se estiver dentro de uma calculadora
        st.sidebar.button("← Voltar para Menu", on_click=partial(navegar_para, PG_LINHAS))

def ui_navegacao_botoes(voltar_label: str, voltar_destino: str, ir_label: Optional[str] = None, ir_callback=None):
    """
    Renderiza barra de navegação. 
    Agora injeta os atalhos e busca automaticamente o próximo ensaio.
    """
    # 1. Injeta o ouvinte de teclado (Ctrl)
    inject_hotkeys()
    
    st.divider()
    col1, col2 = st.columns(2)
    
    # Botão Voltar (Esquerda)
    with col1:
        if st.button(f"↩ {voltar_label}", key=f"btn_voltar_{voltar_destino}_{st.session_state.pagina}"):
            navegar_para(voltar_destino)
            st.rerun()

    # Botão Ir / Próximo (Direita)
    with col2:
        # Caso 1: Navegação Manual (Ex: Menu Inicial -> Lista)
        if ir_label and ir_callback:
            if st.button(f"{ir_label} ⮕", type="primary", key=f"btn_ir_manual"):
                ir_callback()
                st.rerun()
        
        # Caso 2: Navegação Automática entre Calculadoras
        else:
            prox_id = obter_proximo_calculo()
            if prox_id:
                if st.button("Próximo Ensaio ⮕", type="primary", key=f"btn_prox_auto"):
                    navegar_para(prox_id)
                    st.rerun()

# ======================== 4. LÓGICA DE ROTEAMENTO (MATCHERS) ========================

def match_retencao(n: str) -> bool:
    return ("reten" in n) and ("agua" in n)

def match_dens_fresco(n: str) -> bool:
    return ("densidade" in n) and ("estado" in n) and ("fresc" in n)

def decidir_destino_calculo(linha: str, requisito: str) -> str:
    """Gera o ID único da página para o roteador."""
    return f"{linha}::{slugify(requisito)}"
# ======================== 5. PÁGINAS (VIEWS) ========================

def view_inicio():
    st.title("BOAS VINDAS")
    with st.expander("Assista ao vídeo tutorial", expanded=True):
        st.video("https://www.youtube.com/watch?v=d1xeEk7nRho")
    
    st.info("Utilize o menu lateral ou o botão abaixo para começar.")
    if st.button("Ir para Produtos ⮕", type="primary"):
        navegar_para(PG_LINHAS)
        st.rerun()

def view_selecao_linhas():
    st.title("Linha de Produtos")
    st.subheader("Selecione um produto")

    idx = LINHAS_PRODUTOS.index(st.session_state.produto) if st.session_state.produto in LINHAS_PRODUTOS else 0
    prod = st.selectbox("Linha de Produtos", LINHAS_PRODUTOS, index=idx, key="sb_linhas")
    st.session_state.produto = prod

    st.caption("Ao prosseguir, você verá a lista de requisitos ABNT para esta linha.")
    
    ui_navegacao_botoes(
        voltar_label="Início",
        voltar_destino=PG_INICIO,
        ir_label="Ver Requisitos",
        ir_callback=lambda: navegar_para(prod)
    )

def view_selecao_requisito(nome_linha: str):
    st.markdown(f"## Calculadora — {nome_linha}")
    st.write("Selecione o ensaio físico:")

    reqs = REQUISITOS[nome_linha]
    cur = st.session_state.req_por_linha.get(nome_linha)
    idx = reqs.index(cur) if cur in reqs else 0

    requisito = st.selectbox("Requisito (Norma)", reqs, index=idx, key=f"req_{nome_linha}")
    st.session_state.req_por_linha[nome_linha] = requisito

    def acao_ir():
        destino = decidir_destino_calculo(nome_linha, requisito)
        navegar_para(destino)

    ui_navegacao_botoes(
        voltar_label="Voltar para Produtos",
        voltar_destino=PG_LINHAS,
        ir_label="Ir para Ensaio",
        ir_callback=acao_ir
    )

def view_generica_construcao(titulo: str, linha: str):
    st.markdown(f"## {linha} — {titulo}")
    st.warning("🚧 Página em construção.")
    st.write(f"ID Técnico: `{slugify(titulo)}`")
    ui_navegacao_botoes(f"Voltar para {linha}", linha)

# --- CALCULADORAS ESPECÍFICAS ---

# ======================== 5. CALCULADORAS GENÉRICAS ========================

def calc_retencao_agua_generica():
    st.subheader("Retenção de Água (%)")
    st.caption("Norma: ABNT NBR 13277")
    
    with st.form("form_retencao"):
        col1, col2 = st.columns(2)
        with col1: rr = st.number_input("RR (mm)", step=1.0, format="%.1f")
        with col2: rt = st.number_input("RT (mm)", step=1.0, format="%.1f")
        calcular = st.form_submit_button("Calcular")

    if calcular:
        if rt == 0:
            st.error("Erro: RT não pode ser zero.")
        else:
            ra = (rr / rt) * 100
            st.metric("Resultado (Ra)", f"{ra:.2f} %")
            if ra >= 100: st.warning("Atenção: Retenção calculada acima de 100%.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_densidade_fresco_generica():
    st.subheader("Densidade de Massa (Fresco)")
    st.caption("Norma: ABNT NBR 13278")

    with st.form("form_densidade"):
        col1, col2 = st.columns(2)
        with col1: massa = st.number_input("Massa (g)", step=0.1)
        with col2: volume = st.number_input("Volume (cm³)", value=400.0, step=1.0)
        calcular = st.form_submit_button("Calcular")

    if calcular:
        if volume == 0:
            st.error("Volume não pode ser zero.")
        else:
            densidade = (massa / volume) * 1000  # g/cm³ -> kg/m³
            st.metric("Densidade", f"{densidade:.0f} kg/m³")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_flexao_generica():
    # Limite dinâmico
    limite = obter_config("flexao_var_max")
    
    st.subheader("Flexão 4x4x16 (MPa)")
    st.caption(f"Norma: ABNT NBR 13279 | Regra: Excluir se variação > {limite} MPa da média")

    with st.form("form_flexao"):
        c1, c2, c3 = st.columns(3)
        with c1: cp1 = st.number_input("CP 1", key="fx1", step=0.01, format="%.2f")
        with c2: cp2 = st.number_input("CP 2", key="fx2", step=0.01, format="%.2f")
        with c3: cp3 = st.number_input("CP 3", key="fx3", step=0.01, format="%.2f")
        calcular = st.form_submit_button("Calcular")

    if calcular:
        valores = [cp1, cp2, cp3]
        if all(v == 0 for v in valores):
            st.warning("Preencha os valores.")
        else:
            media = sum(valores) / 3
            st.divider()
            
            validos = []
            for i, val in enumerate(valores):
                var = media - val # Lógica Excel (Média - Valor)
                passed = abs(var) <= limite
                if passed: validos.append(val)
                
                cor = "black" if passed else "red"
                icon = "" if passed else "❌"
    
def calc_retencao_agua_generica():
    produto_atual = st.session_state.get("produto")

    # ==================== CASO 1: BASECOAT (Lógica Completa) ====================
    if produto_atual == "Basecoat":
        st.subheader(f"💧 Retenção de Água — {produto_atual}")
        st.markdown("---")

        with st.form("form_retencao_basecoat"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                tara = st.number_input("Tara (g)", min_value=0.0, format="%.2f")
            with c2:
                massa_ini = st.number_input("Arg. + Tara Inicial (g)", min_value=0.0, format="%.2f")
            with c3:
                massa_fim = st.number_input("Arg. + Tara Final (g)", min_value=0.0, format="%.2f")
            with c4:
                agua_ml_kg = st.number_input("Água (mL/Kg)", min_value=0.0, format="%.1f", help="Relação água/pó")

            calcular = st.form_submit_button("Calcular Resultados", type="primary")

        if calcular:
            if massa_ini == 0 or agua_ml_kg == 0:
                st.warning("⚠️ Preencha os dados corretamente.")
            else:
                # --- CÁLCULOS ---
                massa_pasta = massa_ini - tara
                perda_agua = massa_ini - massa_fim
                
                # Fator Água: ml/kg / (1000 + ml/kg)
                fator_agua = agua_ml_kg / (1000 + agua_ml_kg)
                
                # Água total teórica na amostra
                agua_total_amostra = massa_pasta * fator_agua

                # Evita divisão por zero
                if agua_total_amostra > 0:
                    ra = (1 - (perda_agua / agua_total_amostra)) * 100
                else:
                    ra = 0

                # --- EXIBIÇÃO DETALHADA ---
                st.markdown("### 📊 Detalhes do Ensaio")
                
                # 1. Métricas Intermediárias (Para conferência)
                col_met1, col_met2, col_met3, col_met4 = st.columns(4)
                col_met1.metric("Massa da Pasta", f"{massa_pasta:.2f} g")
                col_met2.metric("Fator Água", f"{fator_agua:.4f}")
                col_met3.metric("Água Teórica Total", f"{agua_total_amostra:.2f} g", help="Quanto de água havia na amostra antes do ensaio")
                col_met4.metric("Água Perdida", f"{perda_agua:.2f} g", delta=f"-{perda_agua:.2f} g", delta_color="inverse")

                st.divider()

                # 2. Resultado Principal com Validação Lógica
                col_res, col_extra = st.columns([2, 3])
                
                with col_res:
                    if ra < 0:
                        st.error(f"❌ Resultado Inválido: {ra:.2f}%")
                        st.caption("A perda de água foi maior que a quantidade total de água calculada. Verifique se o valor de 'mL/Kg' está correto.")
                    else:
                        st.metric("💧 Retenção Obtida", f"{ra:.2f} %")
                
                with col_extra:
                    # Barra de progresso visual (apenas se for positivo)
                    if 0 <= ra <= 100:
                        st.caption("Nível de Retenção")
                        st.progress(int(ra))
                    elif ra > 100:
                        st.warning("Acima de 100% (Ganho de massa?)")

                # 3. Memória de Cálculo (Expansível)
                with st.expander("📝 Ver Fórmula e Memória de Cálculo"):
                    st.latex(r"RA = \left( 1 - \frac{M_{perdida}}{M_{pasta} \times F_{água}} \right) \times 100")
                    st.markdown(f"""
                    * **Massa Pasta:** {massa_ini} - {tara} = {massa_pasta:.2f} g
                    * **Fator Água:** {agua_ml_kg} / (1000 + {agua_ml_kg}) = {fator_agua:.4f}
                    * **Água Total:** {massa_pasta:.2f} * {fator_agua:.4f} = **{agua_total_amostra:.2f} g**
                    * **Cálculo Final:** (1 - ({perda_agua:.2f} / {agua_total_amostra:.2f})) * 100 = **{ra:.2f}%**
                    """)

    # ==================== CASO 2: OUTROS PRODUTOS ====================
    else:
        st.subheader("Retenção de Água (%)")
        st.caption("Norma: ABNT NBR 13277")
        
        with st.form("form_retencao"):
            col1, col2 = st.columns(2)
            with col1: rr = st.number_input("RR (mm)", step=1.0, format="%.1f")
            with col2: rt = st.number_input("RT (mm)", step=1.0, format="%.1f")
            calcular = st.form_submit_button("Calcular")

        if calcular:
            if rt == 0:
                st.error("Erro: RT não pode ser zero.")
            else:
                ra = (rr / rt) * 100
                st.metric("Resultado (Ra)", f"{ra:.2f} %")
                st.progress(min(100, int(ra))) # Adicionei barra de progresso aqui também

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", "Linha de Produtos"))

def calc_densidade_fresco_generica():
    st.subheader("Densidade de Massa (Fresco)")
    st.caption("Norma: ABNT NBR 13278")

    with st.form("form_densidade"):
        col1, col2, col3 = st.columns(3)
        with col1: 
            tara = st.number_input("Tara do Copo (g)", min_value=0.0, step=0.1, format="%.2f")
        with col2: 
            massa_bruta = st.number_input("Massa (Copo + Amostra) (g)", min_value=0.0, step=0.1, format="%.2f")
        with col3: 
            # Volume padrão inicia em 0.0 para forçar preenchimento
            volume = st.number_input("Volume do Copo (cm³)", value=0.0, min_value=0.0, step=1.0, format="%.2f")
            
        calcular = st.form_submit_button("Calcular")

    if calcular:
        if volume <= 0:
            st.error("Volume deve ser maior que zero.")
        elif massa_bruta < tara:
            st.error("A massa bruta não pode ser menor que a tara.")
        else:
            massa_amostra = massa_bruta - tara
            densidade_g_cm3 = massa_amostra / volume
            densidade_kg_m3 = densidade_g_cm3 * 1000

            st.divider()
            st.markdown("### Resultados")
            
            # Métricas principais
            c_res1, c_res2, c_res3 = st.columns(3)
            c_res1.metric("Massa Líquida (Amostra)", f"{massa_amostra:.2f} g")
            c_res2.metric("Densidade", f"{densidade_g_cm3:.4f} g/cm³")
            c_res3.metric("Densidade (SI)", f"{densidade_kg_m3:.0f} kg/m³")

            # Detalhamento do cálculo (Memória de Cálculo)
            st.info(f"**Memória de Cálculo:**\n\n"
                    f"$$\\text{{Massa Líquida}} = {massa_bruta:.2f} - {tara:.2f} = {massa_amostra:.2f} \\text{{ g}}$$\n\n"
                    f"$$\\text{{Densidade}} = \\frac{{{massa_amostra:.2f}}}{{{volume:.2f}}} = {densidade_g_cm3:.4f} \\text{{ g/cm³}}$$")

            # Cálculo opcional de Teor de Ar Incorporado
            with st.expander("Calcular Teor de Ar Incorporado (Opcional)"):
                st.caption("Insira a Densidade Teórica para calcular o Teor de Ar.")
                dt = st.number_input("Densidade Teórica (g/cm³)", min_value=0.0, step=0.0001, format="%.4f", key="dt_input")
                
                if dt > 0:
                    teor_ar = ((dt - densidade_g_cm3) / dt) * 100
                    st.metric("Teor de Ar Incorporado", f"{teor_ar:.2f} %")
                    st.latex(r"A = \frac{d_t - d}{d_t} \times 100")
                elif dt == 0:
                     st.warning("Insira uma densidade teórica maior que zero.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_flexao_generica():
    # Limite dinâmico
    limite = obter_config("flexao_var_max")
    
    st.subheader("Flexão 4x4x16 (MPa)")
    st.caption(f"Norma: ABNT NBR 13279 | Regra: Excluir se variação > {limite} MPa da média")

    with st.form("form_flexao"):
        c1, c2, c3 = st.columns(3)
        with c1: cp1 = st.number_input("CP 1", key="fx1", step=0.01, format="%.2f")
        with c2: cp2 = st.number_input("CP 2", key="fx2", step=0.01, format="%.2f")
        with c3: cp3 = st.number_input("CP 3", key="fx3", step=0.01, format="%.2f")
        calcular = st.form_submit_button("Calcular")

    if calcular:
        valores = [cp1, cp2, cp3]
        if all(v == 0 for v in valores):
            st.warning("Preencha os valores.")
        else:
            media = sum(valores) / 3
            st.divider()
            
            validos = []
            for i, val in enumerate(valores):
                var = media - val 
                passed = abs(var) <= limite
                if passed: validos.append(val)
                
                cor = "black" if passed else "red"
                icon = "" if passed else "❌"
                st.write(f"CP {i+1}: {val:.2f} MPa | Var: :{cor}[{var:.2f}] {icon}")

            st.divider()
            if len(validos) >= 2:
                media_final = sum(validos) / len(validos)
                st.success(f"Média Final: {media_final:.2f} MPa ({len(validos)} CPs válidos)")
            else:
                st.error("Ensaio Inválido (Menos de 2 CPs).")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_permeabilidade_generica():
    st.subheader("Permeabilidade 48h (mL/cm³)")
    st.caption("Norma: ABNT NBR 16648 Anexo C | Cálculo com correção pelo Testemunho")

    with st.form("form_perm_generica"):
        # Volume padrão 400ml é comum, mas deixamos editável
        volume_cp = st.number_input("Volume do CP (cm³)", value=400.0, step=1.0)
        
        st.write("Leituras de Massa (g)")
        
        # Cabeçalhos
        cols_labels = st.columns(4)
        labels = ["CP 1", "CP 2", "CP 3", "Testemunho"]
        for i, l in enumerate(labels):
            cols_labels[i].markdown(f"**{l}**")

        # Inputs Iniciais
        st.caption("Massa Inicial")
        c_ini = st.columns(4)
        inputs_ini = []
        for i in range(4):
            val = c_ini[i].number_input(f"Ini {i}", key=f"p_ini_{i}", format="%.2f")
            inputs_ini.append(val)

        # Inputs Finais
        st.caption("Massa Final")
        c_fim = st.columns(4)
        inputs_fim = []
        for i in range(4):
            val = c_fim[i].number_input(f"Fim {i}", key=f"p_fim_{i}", format="%.2f")
            inputs_fim.append(val)

        calcular = st.form_submit_button("Calcular")

    if calcular:
        if volume_cp <= 0:
            st.error("Volume inválido.")
        elif any(v == 0 for v in inputs_ini):
            st.warning("Preencha as massas iniciais.")
        else:
            # 1. Correção pelo Testemunho (Índice 3)
            # Se testemunho perdeu massa (evaporação), somamos essa perda aos CPs
            m_ini_test = inputs_ini[3]
            m_fim_test = inputs_fim[3]
            perda_testemunho = m_ini_test - m_fim_test
            correcao = perda_testemunho if perda_testemunho > 0 else 0
            
            resultados = []
            st.divider()
            st.write(f"**Correção (Testemunho):** {correcao:.2f} g")
            
            col_res = st.columns(3)
            
            # 2. Calcular CPs 1, 2 e 3
            for i in range(3):
                ini = inputs_ini[i]
                fim = inputs_fim[i]
                
                if ini > 0:
                    agua_abs = fim - ini
                    agua_total = agua_abs + correcao
                    perm = agua_total / volume_cp
                    resultados.append(perm)
                    
                    col_res[i].markdown(f"**CP {i+1}**")
                    col_res[i].markdown(f"Abs: {agua_abs:.2f} g")
                    col_res[i].info(f"{perm:.2f} mL/cm³")
                else:
                    resultados.append(0)

            # Média
            media = sum(resultados) / 3
            st.markdown("---")
            st.success(f"Permeabilidade Média: {media:.2f} mL/cm³")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", "Inicio"))

def calc_compressao_4x4x16_generica():
    limite = obter_config("compressao_var_max")
    
    st.subheader("Compressão 4x4x16 (MPa)")
    st.caption(f"Norma: ABNT NBR 13279 | Regra: Excluir se variação > {limite} MPa")

    with st.form("form_comp"):
        c1, c2, c3 = st.columns(3)
        # Inputs para 6 CPs
        with c1: 
            cp1 = st.number_input("CP 1", key="c1", step=0.1)
            cp4 = st.number_input("CP 4", key="c4", step=0.1)
        with c2:
            cp2 = st.number_input("CP 2", key="c2", step=0.1)
            cp5 = st.number_input("CP 5", key="c5", step=0.1)
        with c3:
            cp3 = st.number_input("CP 3", key="c3", step=0.1)
            cp6 = st.number_input("CP 6", key="c6", step=0.1)
        calcular = st.form_submit_button("Calcular")

    if calcular:
        valores = [cp1, cp2, cp3, cp4, cp5, cp6]
        media = sum(valores) / 6
        validos = []
        
        st.write(f"**Média Inicial:** {media:.2f} MPa")
        for val in valores:
            if abs(val - media) <= limite:
                validos.append(val)
            else:
                st.markdown(f":red[Excluído: {val:.2f}]")
        
        if len(validos) >= 4:
            mf = sum(validos) / len(validos)
            st.success(f"Resultado: {mf:.2f} MPa ({len(validos)} CPs)")
        else:
            st.error("Inválido: Menos de 4 CPs.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_capilaridade_generica():
    limite_pct = obter_config("capilaridade_var_pct")
    st.subheader("Capilaridade (g/dm²·min^0,5)")
    st.caption(f"Norma: ABNT NBR 15259 | Regra: Variação {limite_pct}%")

    with st.form("form_cap"):
        area = st.number_input("Área (cm²)", value=16.0)
        
        cols = st.columns(3)
        m10 = []; m90 = []
        for i in range(3):
            with cols[i]:
                st.markdown(f"**CP {i+1}**")
                m10.append(st.number_input(f"10min", key=f"c10_{i}"))
                m90.append(st.number_input(f"90min", key=f"c90_{i}"))
        
        calcular = st.form_submit_button("Calcular")

    if calcular:
        fator = (90**0.5 - 10**0.5) * (area/100)
        valores = []
        for i in range(3):
            if m10[i] > 0:
                c = (m90[i] - m10[i]) / fator
                valores.append(c)
            else:
                valores.append(0)
        
        media = sum(valores) / 3
        st.write(f"Média: {media:.2f}")
        
        validos = []
        for v in valores:
            if media > 0:
                pct = (v / media) * 100
                if (100 - limite_pct) <= pct <= (100 + limite_pct):
                    validos.append(v)
                else:
                    st.markdown(f":red[{v:.2f} (Desvio {pct:.1f}%)]")
            else:
                validos.append(v)

        if len(validos) >= 2:
            st.success(f"Aprovado: {sum(validos)/len(validos):.2f}")
        else:
            st.error("Repetir ensaio")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_retracao_generica():
    limite_pct = obter_config("retracao_var_pct")
    st.subheader("Retração (%)")
    st.caption(f"Norma: ABNT NBR 15261 | Regra: {limite_pct}% da média")
    
    with st.form("form_ret"):
        st.write("Leituras (Inicial e Final)")
        vals = []
        for i in range(3):
            c1, c2 = st.columns(2)
            ini = c1.number_input(f"CP{i+1} Ini", key=f"ri_{i}", format="%.3f")
            fim = c2.number_input(f"CP{i+1} Fin", key=f"rf_{i}", format="%.3f")
            vals.append((ini, fim))
        calcular = st.form_submit_button("Calcular")
        
    if calcular:
        res = []
        for ini, fim in vals:
            if ini > 0: res.append(((fim-ini)/ini)*100)
            else: res.append(0)
            
        media = sum(res)/3
        validos = [r for r in res if abs((r - media)/media if media else 0) <= (limite_pct/100)]
        
        if len(validos) >= 2:
            st.success(f"Retração: {sum(validos)/len(validos):.3f}%")
        else:
            st.error("Inválido")
            
    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_aderencia_automatica_generica():
    # Pega configurações do dicionário
    limite_pct = obter_config("aderencia_var_pct") # Padrão 30%
    min_cps = obter_config("min_cps_aderencia")    # Padrão 6 ou 8
    
    st.subheader("Potencial de Aderência (MPa) — Automática")
    st.caption(f"Norma: ABNT NBR 15258 | Regra: Variação {limite_pct}% | Mínimo {min_cps} CPs válidos")

    with st.form("form_aderencia_auto"):
        st.write("Leituras das 13 Chapinhas (MPa)")
        
        # Cria 3 colunas para organizar os 13 inputs
        c1, c2, c3 = st.columns(3)
        valores_input = []
        
        for i in range(1, 14):
            if i <= 5: col = c1
            elif i <= 9: col = c2
            else: col = c3
            
            with col:
                val = st.number_input(f"CP {i}", key=f"ad_au_{i}", step=0.01, format="%.2f")
                valores_input.append(val)
                
        calcular = st.form_submit_button("Calcular Aderência")

    if calcular:
        # Filtra zeros
        validos_iniciais = [v for v in valores_input if v > 0]
        
        if not validos_iniciais:
            st.warning("Preencha os valores.")
        else:
            media_ini = sum(validos_iniciais) / len(validos_iniciais)
            
            # Limites
            limite_inf = media_ini * (1 - (limite_pct/100))
            limite_sup = media_ini * (1 + (limite_pct/100))
            
            validos_finais = []
            
            st.divider()
            st.write(f"**Média Inicial:** {media_ini:.2f} MPa")
            st.caption(f"Intervalo aceito: {limite_inf:.2f} a {limite_sup:.2f}")
            
            cols_res = st.columns(4)
            for i, val in enumerate(valores_input):
                if val == 0: continue
                
                status = "✔"
                cor = "green"
                
                if val < limite_inf or val > limite_sup:
                    status = "❌"
                    cor = "red"
                else:
                    validos_finais.append(val)
                
                # Exibe resultado compactado
                cols_res[i % 4].markdown(f"**CP {i+1}:** :{cor}[{val:.2f} {status}]")

            st.divider()
            
            qtd = len(validos_finais)
            if qtd >= min_cps:
                media_final = sum(validos_finais) / qtd
                st.success(f"APROVADO: {media_final:.2f} MPa ({qtd} CPs válidos)")
            else:
                st.error(f"INVÁLIDO: Apenas {qtd} CPs válidos (Mínimo requerido: {min_cps})")
                st.caption("Repetir ensaio.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_aderencia_manual_generica():
    import math
    
    # Configurações
    limite_pct = obter_config("aderencia_var_pct")
    min_cps = obter_config("min_cps_aderencia")
    
    st.subheader("Potencial de Aderência (Manual) — kN para MPa")
    st.caption(f"Norma: ABNT NBR 15258 | Regra: Variação {limite_pct}% | Mínimo {min_cps} CPs")

    with st.form("form_aderencia_man"):
        diametro = st.number_input("Diâmetro Pastilha (mm)", value=50.0)
        st.write("Leituras de Carga (kN)")
        
        c1, c2, c3 = st.columns(3)
        kn_inputs = []
        for i in range(1, 14):
            if i <= 5: col = c1
            elif i <= 9: col = c2
            else: col = c3
            with col:
                val = st.number_input(f"CP {i} (kN)", key=f"ad_man_{i}", step=0.001, format="%.3f")
                kn_inputs.append(val)
                
        calcular = st.form_submit_button("Calcular e Converter")

    if calcular:
        if diametro <= 0:
            st.error("Diâmetro inválido.")
        else:
            # Área em mm²
            area = math.pi * ((diametro/2)**2)
            
            mpa_values = []
            for kn in kn_inputs:
                if kn > 0:
                    # (kN * 1000) / mm² = MPa
                    mpa_values.append( (kn * 1000) / area )
                else:
                    mpa_values.append(0)
            
            # Lógica igual à automática daqui pra frente
            validos_ini = [v for v in mpa_values if v > 0]
            
            if not validos_ini:
                st.warning("Sem dados.")
            else:
                media_ini = sum(validos_ini) / len(validos_ini)
                limite_inf = media_ini * (1 - (limite_pct/100))
                limite_sup = media_ini * (1 + (limite_pct/100))
                
                validos_finais = []
                st.divider()
                st.write(f"**Média Inicial:** {media_ini:.2f} MPa")
                
                cols = st.columns(3)
                for i, (kn, mpa) in enumerate(zip(kn_inputs, mpa_values)):
                    if kn == 0: continue
                    
                    is_ok = limite_inf <= mpa <= limite_sup
                    if is_ok: validos_finais.append(mpa)
                    
                    cor = "green" if is_ok else "red"
                    icon = "✔" if is_ok else "❌"
                    
                    with cols[i%3]:
                        st.markdown(f"**CP {i+1}:** {kn:.3f} kN ➝ :{cor}[{mpa:.2f} MPa {icon}]")
                
                st.divider()
                qtd = len(validos_finais)
                if qtd >= min_cps:
                    st.success(f"Média Final: {sum(validos_finais)/qtd:.2f} MPa ({qtd} CPs válidos)")
                else:
                    st.error(f"Inválido: {qtd} CPs (Mínimo {min_cps})")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_compressao_5x10_generica():
    # Tenta pegar um limite específico, ou usa padrão 6% (comum para NBR 7215)
    limite_pct = obter_config("compressao_cilindrica_var_pct")
    if not limite_pct: limite_pct = 6.0 # Fallback se não configurado
    
    st.subheader("Compressão 5x10 cm (MPa)")
    st.caption(f"Norma: ABNT NBR 7215 | Geometria: Cilíndrica (Ø5x10) | Regra: Variação {limite_pct}%")

    with st.form("form_comp_5x10"):
        st.write("Leitura dos Corpos de Prova (MPa)")
        # Geralmente são 3 ou 4 CPs para graute/rejunte, deixei 6 vagas por garantia
        c1, c2, c3 = st.columns(3)
        valores = []
        for i in range(6):
            if i < 2: col = c1
            elif i < 4: col = c2
            else: col = c3
            with col:
                val = st.number_input(f"CP {i+1}", key=f"c5x10_{i}", step=0.1, format="%.1f")
                valores.append(val)
                
        calcular = st.form_submit_button("Calcular")

    if calcular:
        validos_ini = [v for v in valores if v > 0]
        if not validos_ini:
            st.warning("Preencha os valores.")
        else:
            media = sum(validos_ini) / len(validos_ini)
            
            # Limites percentuais (diferente da 4x4x16 que é absoluto)
            lim_inf = media * (1 - (limite_pct/100))
            lim_sup = media * (1 + (limite_pct/100))
            
            validos_finais = []
            st.divider()
            st.write(f"**Média Inicial:** {media:.2f} MPa")
            
            cols = st.columns(3)
            for i, val in enumerate(valores):
                if val == 0: continue
                
                status = "✔"
                cor = "green"
                if val < lim_inf or val > lim_sup:
                    status = "❌"
                    cor = "red"
                else:
                    validos_finais.append(val)
                
                cols[i%3].markdown(f"**CP {i+1}:** :{cor}[{val:.2f} MPa {status}]")
                
            st.divider()
            if len(validos_finais) >= 2: # Mínimo 2 CPs válidos
                mf = sum(validos_finais) / len(validos_finais)
                st.success(f"Resultado Final: {mf:.2f} MPa ({len(validos_finais)} CPs)")
            else:
                st.error("Ensaio Inválido (Menos de 2 CPs válidos).")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_variacao_dimensional_generica():
    # Busca configurações
    limite = obter_config("variacao_dim_max")
    if not limite: limite = 0.20
    
    # Pega o comprimento padrão automaticamente (ex: 130.43 para Graute)
    comp_padrao = obter_config("comprimento_padrao") 
    if not comp_padrao: comp_padrao = 250.0

    st.subheader("Variação Dimensional (mm/m)")
    # Mostra qual base está sendo usada apenas como informação discreta
    st.caption(f"Norma: ABNT NBR 15261 | Base de Cálculo: {comp_padrao:.2f} mm")

    with st.form("form_var_dim"):
        st.write("Leituras do Comparador (mm)")
        
        # Layout igual à planilha: 3 CPs lado a lado
        c1, c2, c3 = st.columns(3)
        cols = [c1, c2, c3]
        inputs = [] 
        
        for i, col in enumerate(cols):
            with col:
                st.markdown(f"**CP {i+1}**")
                # Valores padrão 0.000 para facilitar
                ini = st.number_input(f"Inicial", key=f"vd_ini_{i}", format="%.3f")
                fim = st.number_input(f"Final (28 dias)", key=f"vd_fim_{i}", format="%.3f")
                inputs.append((ini, fim))
            
        calcular = st.form_submit_button("Calcular Resultados")

    if calcular:
        valores_calculados = []
        
        # --- CÁLCULO ---
        for ini, fim in inputs:
            # Lógica para detectar se o campo foi preenchido
            # Se ambos forem 0, consideramos vazio. Se tiver valor, calculamos.
            if ini == 0 and fim == 0:
                valores_calculados.append(None)
            else:
                delta_l = fim - ini
                # Fórmula: (Diferença / Base) * 1000
                res_mm_m = (delta_l / comp_padrao) * 1000
                valores_calculados.append(res_mm_m)

        valores_validos = [v for v in valores_calculados if v is not None]

        if not valores_validos:
            st.warning("Preencha as leituras de pelo menos um CP.")
        else:
            # Média Inicial
            media_inicial = sum(valores_validos) / len(valores_validos)
            
            st.divider()
            # Mostra a média amarela grande igual à planilha
            st.metric("Variação Dimensional Média", f"{media_inicial:.2f} mm/m")
            
            st.write("--- Detalhamento ---")
            
            # Verificação de Desvios
            cps_finais = []
            cols_res = st.columns(3)
            
            for i, val in enumerate(valores_calculados):
                if val is None:
                    cols_res[i].info(f"CP {i+1}: -")
                    continue
                
                # Desvio Absoluto (Coluna J da planilha)
                desvio_abs = abs(val - media_inicial)
                
                # Regra: Variação maior que 0,20 mm/m, excluir
                aprovado = desvio_abs <= limite
                
                cor = "green" if aprovado else "red"
                icon = "✔" if aprovado else "❌"
                
                # Exibe igual à planilha: Resultado e Desvio
                with cols_res[i]:
                    st.markdown(f"**CP {i+1}**")
                    st.markdown(f"Variação: :{cor}[{val:.2f}]")
                    st.caption(f"Desvio: {desvio_abs:.2f} {icon}")
                
                if aprovado:
                    cps_finais.append(val)

            st.divider()
            
            # Validação Final (Mínimo 2 CPs)
            if len(cps_finais) >= 2:
                media_final = sum(cps_finais) / len(cps_finais)
                if abs(media_final - media_inicial) > 0.001:
                    st.warning(f"Após exclusão de outliers, a nova média é: {media_final:.2f} mm/m")
                else:
                    st.success("Ensaio Válido")
            else:
                st.error("ENSAIO INVÁLIDO")
                st.write(f"Menos de 2 CPs atenderam ao critério de desvio máximo ({limite} mm/m). Repetir o ensaio.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))

def calc_variacao_massa_generica():
    st.subheader("Variação de Massa (%)")
    st.caption("Norma: ABNT NBR 15261")

    with st.form("form_var_massa"):
        st.write("Leituras de Massa (g)")
        c = st.columns(3)
        dados = []
        for i in range(3):
            with c[i]:
                st.markdown(f"**CP {i+1}**")
                ini = st.number_input("Inicial", key=f"vmi_{i}", format="%.2f")
                fin = st.number_input("Final", key=f"vmf_{i}", format="%.2f")
                dados.append((ini, fin))
        
        if st.form_submit_button("Calcular"):
            resultados = []
            for ini, fin in dados:
                if ini > 0:
                    # Cálculo: ((Final - Inicial) / Inicial) * 100
                    var_pct = ((fin - ini) / ini) * 100
                    resultados.append(var_pct)
                else:
                    resultados.append(0.0)
            
            media = sum(resultados) / 3
            st.divider()
            st.write(f"**Média:** {media:.2f}%")
            
            # Mostra valores individuais
            c_res = st.columns(3)
            for i, r in enumerate(resultados):
                c_res[i].metric(f"CP {i+1}", f"{r:.2f}%")
                
            st.success("Cálculo concluído.")

    ui_navegacao_botoes("Voltar", st.session_state.get("produto", PG_LINHAS))


# ======================== 6. CONTROLADOR PRINCIPAL (ROUTER) ========================

def main():
    configurar_pagina()
    inicializar_estado()

    # 1. Roteamento Básico (Páginas Estáticas)
    rotas = {
        PG_INICIO: view_inicio,
        PG_LINHAS: view_selecao_linhas,
    }

    # 2. Roteamento Dinâmico (Mapeia Produto + Ensaio -> Calculadora Genérica)
    for linha, reqs in REQUISITOS.items():
        # Rota para o menu de seleção de requisitos deste produto
        rotas[linha] = partial(view_selecao_requisito, linha)
        
        for req in reqs:
            # Gera ID único (ex: "Basecoat::flexao-mpa...") e normaliza nome para busca
            page_id = f"{linha}::{slugify(req)}"
            nome_normalizado = norm(req)

            # --- MAPEAMENTO INTELIGENTE DAS CALCULADORAS ---

            if "flexao" in nome_normalizado:
                rotas[page_id] = calc_flexao_generica
                
            elif "compressao" in nome_normalizado:
                # Prioriza detecção de Graute ou NBR 7215 (Cilíndrico 5x10)
                if "5x10" in nome_normalizado or "7215" in nome_normalizado or linha == "Graute":
                    rotas[page_id] = calc_compressao_5x10_generica
                # Caso contrário, assume Prismático (4x4x16) padrão
                else:
                    rotas[page_id] = calc_compressao_4x4x16_generica
            
            elif "retencao" in nome_normalizado:
                rotas[page_id] = calc_retencao_agua_generica
                
            elif "densidade" in nome_normalizado and "fresco" in nome_normalizado:
                rotas[page_id] = calc_densidade_fresco_generica
                
            elif "capilaridade" in nome_normalizado:
                rotas[page_id] = calc_capilaridade_generica
                
            elif "aderencia" in nome_normalizado:
                if "manual" in nome_normalizado:
                    rotas[page_id] = calc_aderencia_manual_generica
                else:
                    rotas[page_id] = calc_aderencia_automatica_generica
            
            elif "retracao" in nome_normalizado:
                rotas[page_id] = calc_retracao_generica
                
            elif "permeabilidade" in nome_normalizado:
                rotas[page_id] = calc_permeabilidade_generica

            elif "dimensional" in nome_normalizado:
                rotas[page_id] = calc_variacao_dimensional_generica
                
            elif "massa" in nome_normalizado and "variacao" in nome_normalizado:
                rotas[page_id] = calc_variacao_massa_generica

            # Fallback: Se o requisito existe mas não tem calculadora definida
            elif page_id not in rotas:
                rotas[page_id] = partial(view_generica_construcao, req, linha)

    # 3. Execução da Interface
    ui_sidebar() # Exibe o menu lateral

    pagina_atual = st.session_state.pagina
    funcao_renderizacao = rotas.get(pagina_atual)

    # Renderiza a página atual ou mostra erro 404
    if funcao_renderizacao:
        funcao_renderizacao()
    else:
        st.error(f"Erro 404: Página '{pagina_atual}' não encontrada.")
        if st.button("Voltar ao Início"):
            navegar_para(PG_INICIO)
            st.rerun()

if __name__ == "__main__":
    main()