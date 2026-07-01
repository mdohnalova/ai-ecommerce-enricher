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

# Ověřený a stabilní model
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

ai_instruction = "Tón popisku musí být: Profesionální a důvěryhodný."

if prompt_mode == "Rychlé předvolby tónu":
    ai_tone = st.sidebar.selectbox(
        "Tón e-commerce popisku:",
        ["Profesionální a důvěryhodný", "Přátelský a lidský", "Úderný a prodejní (Hard-sell)", "Eko / Udržitelný styl"]
    )
    ai_instruction = f"Tón popisku musí být: {ai_tone}."
else:
    ai_user_input = st.sidebar.text_area(
        "Napište instrukce pro AI (co má s textem udělat):",
        value="Napiš to jako kreativní a vtipný post na sociální sítě, přidej emoji a na konec doplň hashtags.",
    )
    if ai_user_input.strip():
        ai_instruction = ai_user_input.strip()

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
    # Ultimátní fallback pro případ selhání
    fallback = {
        "audit_status": "⚠️ AI doporučuje úpravu",
        "nazev_opraveny": str(clean_name),
        "popis": f"Skvělý produkt {clean_name}, který splňuje vysoké standardy kvality a spolehlivosti.",
        "klicova_slova": ["produkt"]
    }
    
    if not client:
        return fallback
    
    text_zadani = (
        "Jsi špičkový e-commerce copywriter a auditor produktových dat. "
        "Tvým úkolem je zkontrolovat 'Očištěný název z Regex filtru' a posoudit, zda dává smysl jako název produktu.\n\n"
        f"Původní neočištěný název pro kontext: {original_name}\n"
        f"Očištěný název z Regex filtru: {clean_name}\n"
        f"Instrukce pro marketingový popis: {instruction}\n"
        f"Maximální délka popisku: {max_chars} znaků.\n\n"
        "STRIKTNÍ PRAVIDLA PRO REAGOVÁNÍ:\n"
        "1. Do pole 'audit_status' uveď buď '✅ V pořádku' nebo '⚠️ AI doporučuje úpravu'.\n"
        "2. V poli 'nazev_opraveny' MUSÍŠ VŽDY vrátit finální, opravený, gramaticky správný a reprezentativní název produktu. NIKDY ho nenechávej prázdný!\n"
        "3. Do pole 'popis' vytvoř prodejní popisek na základě očištěného názvu a instrukcí.\n\n"
        "Odpověď musí být výhradně platný JSON objekt bez jakýchkoliv keců okolo. Všechny uvozovky uvnitř textů řádně vyescapuj pomocí \\\".\n"
        'Struktura JSON: {"audit_status": "...", "nazev_opraveny": "...", "popis": "...", "klicova_slova": ["klíč1", "klíč2"]}'
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

        parsed = json.loads(raw_text)
        
        # Pojistka: Pokud by model vrátil prázdný název, použijeme očištěný název z regexu
        if "nazev_opraveny" not in parsed or not str(parsed["nazev_opraveny"]).strip():
            parsed["nazev_opraveny"] = str(clean_name)
            
        for k in fallback.keys():
            if k not in parsed:
                parsed[k] = fallback[k]
        return parsed
    except Exception:
        return fallback

# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Data Cleaner PRO")
st.caption("Verze: **PRODUCTION READY - COMPLETE SHOPTET STANDARD**")

tab1, tab2 = st.tabs(["📁 Nahrát soubor (CSV / Excel)", "✍️ Ruční zadání textu"])
full_products_count = 0
df_working = None
column_with_names = None
desc_column = "popis" 
demo_selection_strategy = "Prvních 20 produktů"

with tab1:
    uploaded_file = st.file_uploader("Vyberte soubor s produkty", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_working = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
            else:
                df_working = pd.read_excel(uploaded_file)
            
            name_cols = [c for c in df_working.columns if str(c).lower().strip() in ["name", "název", "nazev"]]
            default_idx = df_working.columns.get_loc(name_cols[0]) if name_cols else 0
            column_with_names = st.selectbox("Vyberte sloupec s názvy produktů:", df_working.columns, index=default_idx)
            
            desc_cols = [c for c in df_working.columns if str(c).lower().strip() in ["description", "popis"]]
            if desc_cols:
                desc_column = desc_cols[0]
            
            full_products_count = len(df_working)
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric(label="Celkový počet položek v tabulce", value=f"{full_products_count} ks")
            with col_stat2:
                st.info(f"Klíčové sloupce ➔ Název: **{column_with_names}** | Popis pro zápis: **{desc_column}**")
            
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
            df_working = pd.DataFrame({
                "kód": [f"TEST-{i+1}" for i in range(len(lines))],
                "název": lines,
                "cena": [499] * len(lines),
                "popis": [""] * len(lines)
            })
            column_with_names = "název"
            desc_column = "popis"
            full_products_count = len(lines)

if "final_df" not in st.session_state:
    st.session_state.final_df = None
if "total_time" not in st.session_state:
    st.session_state.total_time = 0
if "was_truncated" not in st.session_state:
    st.session_state.was_truncated = False

run_main = st.button("🚀 Spustit kompletní transformaci dat", type="primary")

# ──────────────────────────────────────────────────────────────
# SPUŠTĚNÍ TRANSFORMACE
# ──────────────────────────────────────────────────────────────
if (run_main or run_sidebar) and df_working is not None and column_with_names is not None:
    if not client:
        st.error("API klíč Anthropic není správně nakonfigurován.")
    else:
        df_output = df_working.copy()
        
        if desc_column not in df_output.columns:
            df_output[desc_column] = ""
            
        # Vytvoření nových a čistých sloupců přímo v přehledové tabulce
        if "🔍 Stav auditu" not in df_output.columns:
            df_output.insert(0, "🔍 Stav auditu", "Neupraveno AI")
        if "Regex čištění" not in df_output.columns:
            df_output.insert(1, "Regex čištění", df_output[column_with_names])
        if "Finální název (AI)" not in df_output.columns:
            df_output.insert(2, "Finální název (AI)", df_output[column_with_names])
        if "AI Popisek" not in df_output.columns:
            df_output.insert(3, "AI Popisek", df_output[desc_column])
        if "SEO Klíčová slova" not in df_output.columns:
            df_output["SEO Klíčová slova"] = ""

        if len(df_output) > 20:
            st.session_state.was_truncated = True
            if demo_selection_strategy == "Náhodný výběr 20 produktů":
                target_indices = random.sample(list(df_output.index), 20)
            else:
                target_indices = list(df_output.index[:20])
        else:
            st.session_state.was_truncated = False
            target_indices = list(df_output.index)
            
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        for step, idx in enumerate(target_indices):
            status_text.text(f"Zpracovávám {step + 1} z {len(target_indices)}...")
            
            original_name = str(df_output.loc[idx, column_with_names])
            
            # Krok A: Regex čištění
            clean_name = clean_product_name(original_name, custom_stopwords, all_selected_chars)
            if not clean_name:
                clean_name = "Produkt"
                
            # Krok B: AI obohacení s opravou názvu
            ai_data = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            
            # Bezpečný zápis do přehledových i originálních sloupců
            df_output.loc[idx, "🔍 Stav auditu"] = ai_data["audit_status"]
            df_output.loc[idx, "Regex čištění"] = clean_name
            df_output.loc[idx, "Finální název (AI)"] = ai_data["nazev_opraveny"]
            df_output.loc[idx, "AI Popisek"] = ai_data["popis"]
            
            # Propisování přímo do původních sloupců souboru pro Shoptet import
            df_output.loc[idx, column_with_names] = ai_data["nazev_opraveny"]
            df_output.loc[idx, desc_column] = ai_data["popis"]
            
            kws = ai_data["klicova_slova"]
            df_output.loc[idx, "SEO Klíčová slova"] = ", ".join(kws) if isinstance(kws, list) else str(kws)
            
            progress_bar.progress((step + 1) / len(target_indices))
            
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        st.session_state.final_df = df_output

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ A EXPORT
# ──────────────────────────────────────────────────────────────
if st.session_state.final_df is not None:
    df_results = st.session_state.final_df
    
    st.write("---")
    st.subheader("✨ Výsledky transformace")
    
    if st.session_state.was_truncated:
        st.warning(f"⚠️ **Demo verze:** Upraveno bylo 20 vybraných produktů. Zbylé produkty v tabulce zůstaly kompletně beze změny se svými původními daty.")
        
    col_kpi1, col_kpi2 = st.columns(2)
    with col_kpi1:
        st.metric(label="Celkový počet řádků v souboru", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování AI", value=f"{st.session_state.total_time} s")
    
    st.write("---")
    st.write("### 📥 Export hotového souboru")
    
    # Příprava čistého exportu, kde odfiltrujeme naše interní sloupce, pokud si je uživatel nepřeje
    all_available_cols = list(df_results.columns)
    
    # Definujeme výchozí doporučenou předvolbu pro Shoptet (obsahuje všechny původní sloupce zákazníka bez našich pomocných)
    default_export_cols = [c for c in all_available_cols if c not in ["🔍 Stav auditu", "Regex čištění", "Finální název (AI)", "AI Popisek", "SEO Klíčová slova"]]
    
    export_columns = st.multiselect(
        "Vyberte sloupce, které chcete zahrnout do výsledného stahovaného CSV:",
        options=all_available_cols,
        default=default_export_cols
    )
    
    if not export_columns:
        st.error("⚠️ Musíte vybrat alespoň jeden sloupec pro export.")
    else:
        df_to_export = df_results[export_columns]
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            csv_buffer = df_to_export.to_csv(index=False, encoding='utf-8-sig', sep=';')
            st.download_button(
                label="📥 STÁHNOUT KOMPLETNÍ CSV (Vybrané sloupce)", 
                data=csv_buffer, 
                file_name="shoptet_import_final.csv", 
                mime="text/csv", 
                use_container_width=True
            )
        with col_btn2:
            json_buffer = json.dumps(df_results.to_dict(orient="records"), ensure_ascii=False, indent=2)
            st.download_button(label="📥 Stáhnout kompletní zálohu JSON", data=json_buffer, file_name="shoptet_backup.json", mime="application/json", use_container_width=True)
    
    st.write("---")
    st.subheader("📊 Interaktivní kontrola a rychlá úprava v tabulce")
    st.info("💡 **Tip:** Pokud ve sloupci 'Finální název (AI)' nebo 'AI Popisek' uvidíte chybu, můžete na buňku poklikat a hodnotu přímo upravit ještě před stažením.")
    
    edited_df = st.data_editor(df_results, use_container_width=True)
    st.session_state.final_df = pd.DataFrame(edited_df)
