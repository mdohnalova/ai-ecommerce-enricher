import streamlit as st
import anthropic
import re
import time
import random
import pandas as pd

# ============================================================
# PROJEKT:  AI E-Commerce Data Cleaner & Enricher (Shoptet Engine)
# ============================================================

st.set_page_config(page_title="AI Data Cleaner & Enricher", page_icon="⚙️", layout="wide")

MODEL_NAME = "claude-3-5-sonnet-20241022"

# ──────────────────────────────────────────────────────────────
# INICIALIZACE ANTHROPIC CLIENTA
# ──────────────────────────────────────────────────────────────
try:
    api_key = st.secrets["anthropic"]["api_key"]
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    st.error(f"❌ Chyba při načítání API klíče ze Streamlit Secrets: {e}")
    client = None

# ──────────────────────────────────────────────────────────────
# BOČNÍ PANEL: KONFIGURACE FILTRŮ
# ──────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Konfigurace filtrů na míru")

st.sidebar.subheader("1. Výběr znaků k odstranění")
available_chars = ["!", "?", "*", "#", "@", "~", "%", "&", "$", "_", "=", "+", "^", "<", ">", "[", "]", "{", "}", "\"", "'"]
selected_chars = st.sidebar.multiselect(
    "Vyberte přednastavené znaky k odstranění:",
    options=available_chars,
    default=["!", "?", "*", "#", "@"]
)

custom_chars_input = st.sidebar.text_input("Dopište další znaky bez oddělování (např. §°×):", value="")
all_selected_chars = list(set(list(selected_chars) + list(custom_chars_input)))

clean_marketing_percentages = st.sidebar.checkbox("Chytře mazat slevová procenta (např. Sleva 30%)", value=True)
clean_numbers = st.sidebar.checkbox("Všechna samostatná čísla", value=False)

st.sidebar.subheader("2. Marketingový balast")
custom_stopwords_input = st.sidebar.text_area(
    "Zakázaná slova / stop-slova (oddělte čárkou):",
    value="akce, sleva, výprodej, doprava zdarma, novinka, dnes za dolů, skladem, ihned",
)
custom_stopwords = [word.strip().lower() for word in custom_stopwords_input.split(",") if word.strip()]

st.sidebar.subheader("3. Nastavení AI textů & Stylu")
prompt_mode = st.sidebar.radio("Jak chcete definovat styl popisků?", ["Rychlé předvolby tónu", "Vlastní zadání (Prompt / Instrukce)"])

if prompt_mode == "Rychlé předvolby tónu":
    ai_tone = st.sidebar.selectbox("Tón e-commerce popisku:", ["Profesionální a důvěryhodný", "Přátelský a lidský", "Úderný a prodejní (Hard-sell)", "Eko / Udržitelný styl"])
    ai_instruction = f"Tón popisku musí být: {ai_tone}."
else:
    ai_instruction = st.sidebar.text_area("Napište instrukce pro AI (co má s textem udělat):", value="Napiš popisky produktů jako marketingový specialista s důrazem na SEO.")

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
# POMOCNÉ AI VOLÁNÍ PŘES JEDNODUCHÝ SEPARÁTOR (PRO TIŠTĚNÍ BEZ CHYB)
# ──────────────────────────────────────────────────────────────
def enrich_product_with_ai(clean_name, original_name, max_chars, instruction):
    if not client:
        return f"✅ V pořádku | {clean_name} |  | "
    
    prompt = (
        "Jsi špičkový e-commerce copywriter a auditor produktových dat.\n"
        "Zkontroluj produkt a vygeneruj data oddělená svislítkem '|'.\n\n"
        f"PŮVODNÍ NÁZEV: {original_name}\n"
        f"OČIŠTĚNÝ NÁZEV: {clean_name}\n"
        f"INSTRUKCE PRO POPIS: {instruction}\n"
        f"MAX DÉLKA POPISU: {max_chars} znaků.\n\n"
        "Odpověz PŘESNĚ v tomto formátu na jednom řádku a nepoužívej žádné jiné texty:\n"
        "Stav auditu (buď: ✅ V pořádku nebo ⚠️ K úpravě) | Finální vylepšený název e-shopu | Prodejní popisek | 3-5 klíčových slov oddělených čárkou"
    )
    
    try:
        response = client.messages.create(
            model=MODEL_NAME, 
            max_tokens=800, 
            messages=[{"role": "user", "content": prompt}]
        )
        if hasattr(response, 'content') and isinstance(response.content, list):
            return response.content[0].text.strip()
        return response.content.strip()
    except:
        return f"✅ V pořádku | {clean_name} |  | "

# ──────────────────────────────────────────────────────────────
# MAIN INTERFACE (ROVNOU V SHOPTET NORMĚ)
# ──────────────────────────────────────────────────────────────
st.title("🪄 AI E-commerce Data Cleaner & Enricher PRO")
st.caption("Verze: **SHOPTET NATIVE AUTOMATION ENGINE V3**")

uploaded_file = st.file_uploader("Vyberte váš Shoptet exportní soubor (.csv nebo .xlsx)", type=["csv", "xlsx"])

full_products_count = 0
original_df = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            original_df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
        else:
            original_df = pd.read_excel(uploaded_file)
        
        # --- PŘEKLAD DO SHOPTET STANDARDU HNED NA ZAČÁTKU ---
        shoptet_mapping = {
            "kód": "code", "nazev": "name", "název": "name", "cena": "price",
            "nákupní cena": "purchasePrice", "nakupni cena": "purchasePrice",
            "dph": "vat", "sklad": "stock", "jednotka": "unit",
            "výrobce": "manufacturer", "vyrobce": "manufacturer",
            "kategorie": "categoryText", "popis": "description"
        }
        original_df = original_df.rename(columns=shoptet_mapping)
        
        if "name" not in original_df.columns:
            st.error("❌ V souboru nebyl nalezen sloupec pro název produktu ('name' nebo 'název').")
        else:
            full_products_count = len(original_df)
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            st.metric(label="Celkový počet položek v souboru", value=f"{full_products_count} ks")
                
            if full_products_count > 20:
                st.warning("💡 **Demo režim:** Soubor obsahuje více produktů. V rámci ukázky zpracujeme max 20 řádků.")
                demo_selection_strategy = st.radio(
                    "Vyberte, jakých 20 vzorků chcete vyzkoušet:",
                    ["Prvních 20 produktů", "Náhodný výběr 20 produktů"]
                )
    except Exception as e:
        st.error(f"Chyba při čtení souboru: {e}")

if "processed_df" not in st.session_state: st.session_state.processed_df = None
if "total_time" not in st.session_state: st.session_state.total_time = 0
if "was_truncated" not in st.session_state: st.session_state.was_truncated = False

run_main = st.button("🚀 Spustit kompletní transformaci dat", type="primary")

# ──────────────────────────────────────────────────────────────
# SPUŠTĚNÍ TRANSFORMACE
# ──────────────────────────────────────────────────────────────
if (run_main or run_sidebar) and original_df is not None:
    if client is None:
        st.error("API klíč není nakonfigurován.")
    else:
        if len(original_df) > 20:
            st.session_state.was_truncated = True
            if demo_selection_strategy == "Náhodný výběr 20 produktů":
                working_df = original_df.sample(n=20, random_state=random.randint(1, 100)).copy()
            else:
                working_df = original_df.iloc[:20].copy()
        else:
            working_df = original_df.copy()
            st.session_state.was_truncated = False
            
        limit = len(working_df)
        ai_raw_responses = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        for idx in range(limit):
            status_text.text(f"Zpracovávám produkt {idx + 1} z {limit}...")
            original_name = str(working_df.iloc[idx]["name"])
            
            # Předčištění přes regex filtry zdarma
            clean_name = clean_product_name(original_name, custom_stopwords, all_selected_chars)
            if not clean_name: clean_name = "Produkt"
            
            # Volání AI pro uložení surových dat do pomocného řetězce
            raw_response = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            ai_raw_responses.append(raw_response)
            
            progress_bar.progress((idx + 1) / limit)
            
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        
        # --- ROZPARSOVÁNÍ POMOCNÉHO SLOUPEČKU ZPĚT DO STRUKTURY ---
        audit_statuses = []
        final_names = []
        final_descriptions = []
        seo_keywords = []
        
        for idx, resp in enumerate(ai_raw_responses):
            parts = resp.split("|")
            orig_name_clean = clean_product_name(str(working_df.iloc[idx]["name"]), custom_stopwords, all_selected_chars)
            
            # Výchozí hodnoty pro případ nouze
            status = "✅ V pořádku"
            f_name = orig_name_clean if orig_name_clean else "Produkt"
            f_desc = ""
            f_seo = ""
            
            if len(parts) >= 1: status = parts[0].strip()
            if len(parts) >= 2: f_name = parts[1].strip()
            if len(parts) >= 3: f_desc = parts[2].strip()
            if len(parts) >= 4: f_seo = parts[3].strip()
            
            audit_statuses.append(status)
            final_names.append(f_name)
            final_descriptions.append(f_desc)
            seo_keywords.append(f_seo)
            
        # Zápis upravených dat přímo do Shoptet struktury
        working_df["name"] = final_names
        working_df["description"] = final_descriptions
        
        # Pomocné sloupce pro zobrazení
        working_df.insert(0, "🔍 Stav auditu", audit_statuses)
        working_df["_seo_cache"] = seo_keywords
        
        st.session_state.processed_df = working_df

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ V SHOPTET NORMĚ
# ──────────────────────────────────────────────────────────────
if st.session_state.processed_df is not None:
    df_results = st.session_state.processed_df
    
    st.write("---")
    st.subheader("✨ Výsledky kompletní transformace")
    
    if st.session_state.was_truncated:
        st.warning(f"⚠️ **Ukázka zpracování dokončena:** Zobrazeno 20 vzorků z celkových {full_products_count} položek.")
        
    col_kpi1, col_kpi2 = st.columns(2)
    with col_kpi1:
        st.metric(label="Počet položek v tabulce", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování", value=f"{st.session_state.total_time} s")
    
    st.write("---")
    st.info("📊 Tabulka je upravená v Shoptet formátu (`code`, `name`, `description`). Sloupec 'Stav auditu' slouží pro tvou kontrolu a do výsledného souboru se neuloží.")
    
    # Skryjeme interní cache sloupec před uživatelem pro čistý design
    view_df = df_results.copy()
    if "_seo_cache" in view_df.columns:
        view_df = view_df.drop(columns=["_seo_cache"])
        
    edited_df = st.data_editor(view_df, use_container_width=True)
    
    st.write("---")
    st.write("### 📥 Nastavení exportu")
    add_seo_column = st.checkbox("Přidat do stahovaného souboru sloupec s SEO klíčovými slovy (jako shortDescription)", value=False)
    
    download_df = pd.DataFrame(edited_df)
    
    if add_seo_column and "_seo_cache" in df_results.columns:
        download_df["shortDescription"] = df_results["_seo_cache"].values
        
    # Odstraníme pomocný sloupec Auditu před stažením
    if "🔍 Stav auditu" in download_df.columns:
        download_df = download_df.drop(columns=["🔍 Stav auditu"])
        
    csv_buffer = download_df.to_csv(index=False, encoding='utf-8-sig', sep=';')
    st.download_button(
        label="📥 STÁHNOUT FINÁLNÍ ČISTÉ CSV PRO SHOPTET IMPORT", 
        data=csv_buffer, 
        file_name="shoptet_data_ready.csv", 
        mime="text/csv", 
        use_container_width=True
    )
