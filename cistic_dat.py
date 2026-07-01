
import streamlit as st
import anthropic
import json
import re
import time
import random
import pandas as pd

# ============================================================
# PROJEKT:  AI E-Commerce Enricher & Data Cleaner (Enterprise Demo)
# ============================================================

st.set_page_config(page_title="AI E-commerce Enricher PRO", page_icon="🛍️", layout="wide")

# ──────────────────────────────────────────────────────────────
# INICIALIZACE ANTHROPIC CLIENTA
# ──────────────────────────────────────────────────────────────
try:
    api_key = st.secrets["anthropic"]["api_key"]
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    st.error(f"❌ Chyba při načítání API klíče ze Streamlit Secrets: {e}")
    client = None

# Stabilní a funkční model
MODEL_NAME = "claude-3-5-sonnet-20241022"

# ──────────────────────────────────────────────────────────────
# BOČNÍ PANEL: ROZŠÍŘENÉ FILTRY A DYNAMICKÝ PROMPT
# ──────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Konfigurace filtrů na míru")

st.sidebar.subheader("1. Výběr znaků k odstranění")

available_chars = ["!", "?", "*", "#", "@", "~", "%", "&", "$", "_", "=", "+", "^", "<", ">", "[", "]", "{", "}", "\"", "'"]
selected_chars = st.sidebar.multiselect(
    "Vyberte přednastavené znaky k odstranění:",
    options=available_chars,
    default=["!", "?", "*", "#", "@"]
)

custom_chars_input = st.sidebar.text_input(
    "Dopište další znaky bez oddělování (např. §°×):",
    value=""
)

all_selected_chars = list(selected_chars) + list(custom_chars_input)
all_selected_chars = list(set(all_selected_chars))

clean_marketing_percentages = st.sidebar.checkbox("Chytře mazat slevová procenta (např. Sleva 30%)", value=True)
clean_numbers = st.sidebar.checkbox("Všechna samostatná čísla", value=False)

st.sidebar.subheader("2. Marketingový balast")
custom_stopwords_input = st.sidebar.text_area(
    "Zakázaná slova / stop-slova (oddělte čárkou):",
    value="akce, sleva, výprodej, doprava zdarma, novinka, dnes za dolů, skladem, ihned",
)
custom_stopwords = [word.strip().lower() for word in custom_stopwords_input.split(",") if word.strip()]

st.sidebar.subheader("3. Nastavení AI textů & Stylu")

prompt_mode = st.sidebar.radio(
    "Jak chcete definovat styl popisků?",
    ["Rychlé předvolby tónu", "Vlastní zadání (Prompt / Instrukce)"]
)

if prompt_mode == "Rychlé předvolby tónu":
    ai_tone = st.sidebar.selectbox(
        "Tón e-commerce popisku:",
        ["Profesionální a důvěryhodný", "Přátelský a lidský", "Úderný a prodejní (Hard-sell)", "Eko / Udržitelný styl"]
    )
    ai_instruction = f"Tón popisku musí být: {ai_tone}."
else:
    ai_tone = "Vlastní prompt"
    ai_instruction = st.sidebar.text_area(
        "Napište instrukce pro AI (co má s textem udělat):",
        value="Napiš to jako kreativní a vtipný post na sociální sítě, přidej emoji a na konec doplň hashtags.",
    )

max_char_length = st.sidebar.slider("Maximální délka popisku (znaků):", min_value=50, max_value=1000, value=250)

st.sidebar.write("---")
run_sidebar = st.sidebar.button("🚀 Spustit kompletní transformaci", key="sidebar_run_btn", use_container_width=True)

# ──────────────────────────────────────────────────────────────
# LOGIKA ČIŠTĚNÍ (REGEX / STRIP)
# ──────────────────────────────────────────────────────────────
def clean_product_name(name, user_stopwords, selected_characters):
    if not name or pd.isna(name):
        return ""
    result = str(name).strip()
    
    if clean_marketing_percentages:
        for word in user_stopwords:
            pattern1 = r"\b" + re.escape(word) + r"\b\s*\d+\s*%"
            pattern2 = r"\d+\s*%\s*\b" + re.escape(word) + r"\b"
            result = re.sub(pattern1, "", result, flags=re.IGNORECASE)
            result = re.sub(pattern2, "", result, flags=re.IGNORECASE)
            
    for word in user_stopwords:
        word_pattern = r"\b" + re.escape(word) + r"\b"
        result = re.sub(word_pattern, "", result, flags=re.IGNORECASE)
        
    if selected_characters:
        escaped_chars = "".join([re.escape(c) for c in selected_characters])
        result = re.sub(r"[" + escaped_chars + r"]", "", result)
        
    if clean_numbers:
        result = re.sub(r"\b\d+\b", "", result)
        
    return re.sub(r"\s+", " ", result).strip()

# ──────────────────────────────────────────────────────────────
# INTELIGENTNÍ AI TRANSFORMACE + AUDIT NÁZVŮ
# ──────────────────────────────────────────────────────────────
def enrich_product_with_ai(clean_name, original_name, max_chars, instruction):
    if not client:
        return {"audit_status": "❌ Chyba", "nazev_opraveny": clean_name, "popis": "Chyba: API klient není inicializován.", "klicova_slova": []}
    
    text_zadani = (
        "Jsi špičkový e-commerce copywriter a auditor produktových dat. "
        "Tvým úkolem je nejprve zkontrolovat sloupec 'Regex čištění' (Cleaned Name) a posoudit, zda dává smysl jako název produktu, nebo zda v něm nezůstal balast či chyba. "
        "Odpověď musí být výhradně platná JSON struktura.\n\n"
        f"Původní neočištěný název pro kontext: {original_name}\n"
        f"Očištěný název z Regex filtru (zkontroluj ho!): {clean_name}\n"
        f"Instrukce pro popis: {instruction}\n"
        f"Maximální délka popisku: {max_chars} znaků.\n\n"
        "PRAVIDLA PRO AUDIT (audit_status):\n"
        "1. Pokud je očištěný název gramaticky v pořádku, srozumitelný a bez zapomenutých znaků, vrať: '✅ V pořádku'.\n"
        "2. Pokud očištěný název obsahuje zapomenuté divné znaky, nedává smysl, nebo v něm uživatel zřejmě zapomněl něco odmazat, vrať: '⚠️ AI doporučuje úpravu'.\n"
        "3. Pokud je očištěný název prázdný nebo úplně zničený, vrať: '❌ Prázdný název'.\n\n"
        "V poli 'nazev_opraveny' navrhni finální reprezentativní název produktu pro e-shop.\n\n"
        'Struktura JSON, kterou musíš striktně dodržet: '
        '{"audit_status": "...", "nazev_opraveny": "...", "popis": "...", "klicova_slova": ["...", "..."]}'
    )
    
    try:
        response = client.messages.create(
            model=MODEL_NAME, 
            max_tokens=1024, 
            messages=[{"role": "user", "content": text_zadani}]
        )
        
        raw_text = response.content[0].text.strip() if isinstance(response.content, list) else response.content.strip()
        if not raw_text.startswith("{"):
            start_idx = raw_text.find("{")
            end_idx = raw_text.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                raw_text = raw_text[start_idx:end_idx]

        return json.loads(raw_text)
    except Exception as e:
        return {"audit_status": "❌ Chyba", "nazev_opraveny": clean_name, "popis": f"AI Chyba: {str(e)}", "klicova_slova": ["chyba"]}

# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Data Cleaner PRO")
st.caption("Verze: **ENTERPRISE DEMO - PRODUCTION READY**")

tab1, tab2 = st.tabs(["📁 Nahrát soubor (CSV / Excel)", "✍️ Ruční zadání textu"])
full_products_count = 0
df_input = None
column_with_names = None
desc_column = None
demo_selection_strategy = "Prvních 20 produktů"  # Bezpečný default

with tab1:
    uploaded_file = st.file_uploader("Vyberte soubor s produkty", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
            else:
                df_input = pd.read_excel(uploaded_file)
            
            # Najde sloupec s názvem
            for col in df_input.columns:
                if str(col).lower().strip() in ["name", "název", "nazev"]:
                    column_with_names = col
                    break
            if column_with_names is None:
                column_with_names = df_input.columns[0]
                
            # Najde sloupec s popisem
            for col in df_input.columns:
                if str(col).lower().strip() in ["description", "popis"]:
                    desc_column = col
                    break
            if desc_column is None:
                desc_column = "description"
            
            full_products_count = len(df_input)
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric(label="Celkový počet položek v souboru", value=f"{full_products_count} ks")
            with col_stat2:
                st.info(f"Nalezené sloupce v souboru ➔ Název: **{column_with_names}** | Popis: **{desc_column}**")
            
            if full_products_count > 20:
                st.warning(f"💡 **Omezení bezplatné verze:** V rámci Demo režimu můžete otestovat transformaci maximálně na **20 produktech**.")
                demo_selection_strategy = st.radio(
                    "Vyberte, jakých 20 vzorků chcete z nahrávky vyzkoušet:",
                    ["Prvních 20 produktů", "Náhodný výběr 20 produktů"]
                )
                
        except Exception as e:
            st.error(f"Chyba při čtení souboru: {e}")

with tab2:
    if uploaded_file is None:
        sample_data = "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\nSilonové punčochy dnes za 30% dolů"
        text_input = st.text_area("Vložte názvy (každý na nový řádek):", value=sample_data, height=120)
        if text_input:
            lines = [line.strip() for line in text_input.split("\n") if line.strip()]
            df_input = pd.DataFrame({
                "code": [f"TEST-{i+1}" for i in range(len(lines))],
                "name": lines,
                "price": [499] * len(lines),
                "description": [""] * len(lines)
            })
            column_with_names = "name"
            desc_column = "description"
            full_products_count = len(lines)

if "processed_df" not in st.session_state:
    st.session_state.processed_df = None
if "total_time" not in st.session_state:
    st.session_state.total_time = 0
if "was_truncated" not in st.session_state:
    st.session_state.was_truncated = False

run_main = st.button("🚀 Spustit kompletní transformaci dat", type="primary")

# ──────────────────────────────────────────────────────────────
# SPUŠTĚNÍ TRANSFORMACE
# ──────────────────────────────────────────────────────────────
if (run_main or run_sidebar) and df_input is not None and column_with_names is not None:
    if not client:
        st.error("Nemohu spustit transformaci, protože API klíč Anthropic není správně nakonfigurován.")
    else:
        # Bezpečné vytvoření pracovního DataFrame bez varování o kopii
        if len(df_input) > 20:
            st.session_state.was_truncated = True
            if demo_selection_strategy == "Náhodný výběr 20 produktů":
                working_df = df_input.sample(n=20, random_state=random.randint(1, 100)).copy()
            else:
                working_df = df_input.iloc[:20].copy()
        else:
            working_df = df_input.copy()
            st.session_state.was_truncated = False
            
        limit = len(working_df)
        audit_statuses = []
        final_names = []
        final_descriptions = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        # Čisté 2D indexování pomocí iloc[řádek, sloupec_index]
        for idx in range(limit):
            status_text.text(f"Zpracovávám {idx + 1} z {limit}...")
            
            # OPRAVENO: Bezpečné získání hodnoty z 2D matice
            col_idx = working_df.columns.get_loc(column_with_names)
            original_name = str(working_df.iloc[idx, col_idx])
            
            # 1. Krok: Vyčištění přes Regex
            clean_name = clean_product_name(original_name, custom_stopwords, all_selected_chars)
            if not clean_name:
                clean_name = "Produkt"
                
            # 2. Krok: Obohacení a kontrola přes AI
            ai_data = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            
            audit_statuses.append(ai_data.get("audit_status", "✅ V pořádku"))
            final_names.append(ai_data.get("nazev_opraveny", clean_name))
            final_descriptions.append(ai_data.get("popis", ""))
            
            progress_bar.progress((idx + 1) / limit)
            
        status_text.empty()
        progress_bar.empty()
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        
        # Pojistka struktury tabulky
        if desc_column not in working_df.columns:
            working_df[desc_column] = ""
            
        # Zápis přes .loc na základě aktuálních indexů
        working_df.loc[:, column_with_names] = final_names
        working_df.loc[:, desc_column] = final_descriptions
        
        # Odstranění starého a vložení čistého pomocného auditního sloupce na začátek
        if "🔍 Stav auditu" in working_df.columns:
            working_df = working_df.drop(columns=["🔍 Stav auditu"])
        working_df.insert(0, "🔍 Stav auditu", audit_statuses)
        
        st.session_state.processed_df = working_df

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ A EXPORT
# ──────────────────────────────────────────────────────────────
if st.session_state.processed_df is not None:
    df_results = st.session_state.processed_df
    
    st.write("---")
    st.subheader("✨ Výsledky transformace")
    
    if st.session_state.was_truncated:
        st.warning(f"⚠️ **Ukázka zpracování dat dokončena:** Ze souboru o celkovém počtu {full_products_count} položek bylo vybráno 20 vzorků. Všechny původní sloupce byly zachovány.")
        
    col_kpi1, col_kpi2 = st.columns(2)
    with col_kpi1:
        st.metric(label="Zobrazeno řádků v tabulce", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování AI", value=f"{st.session_state.total_time} s")
    
    st.write("---")
    st.write("### 📥 Export stahovaných dat")
    
    df_to_export = df_results.copy()
    
    if "🔍 Stav auditu" in df_to_export.columns:
        df_to_export = df_to_export.drop(columns=["🔍 Stav auditu"])
        
    csv_buffer = df_to_export.to_csv(index=False, encoding='utf-8-sig', sep=';')
    st.download_button(
        label="📥 STÁHNOUT KOMPLETNÍ SHOPTET CSV S VAŠIMI DATY", 
        data=csv_buffer, 
        file_name="shoptet_clean_data.csv", 
        mime="text/csv", 
        use_container_width=True
    )
    
    st.write("---")
    st.subheader("📊 KONTROLA: Rychlá editace před stažením")
    st.info("💡 Tabulka níže obsahuje VŠECHNY původní sloupce z vašeho souboru. Sloupce s názvem a popisem byly bezpečně nahrazeny.")
    
    edited_df = st.data_editor(df_results, use_container_width=True)
    st.session_state.processed_df = pd.DataFrame(edited_df)
