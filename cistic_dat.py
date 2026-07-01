import streamlit as st
import anthropic
import json
import re
import time
import random
import pandas as pd

# ============================================================
# PROJEKT:  AI E-Commerce Data Cleaner & Enricher (Shoptet Engine)
# ============================================================

st.set_page_config(page_title="AI Data Cleaner & Enricher", page_icon="⚙️", layout="wide")

# Globální definice modelu pro Anthropic
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
    ai_instruction = f"Tón popisku must be: {ai_tone}."
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
# INTELIGENTNÍ AI TRANSFORMACE + AUDIT NÁZVŮ
# ──────────────────────────────────────────────────────────────
def enrich_product_with_ai(clean_name, original_name, max_chars, instruction):
    if not client:
        return {"audit_status": "❌ Chyba", "nazev_opraveny": clean_name, "popis": "Chyba API", "klicova_slova": []}
    
    text_zadani = (
        "Jsi špičkový e-commerce copywriter a auditor produktových dat.\n"
        "Tvým hlavním úkolem je zkontrolovat text v poli 'Očištěný název z Regex filtru' a na základě něj a původního názvu navrhnout ideální finální název produktu pro e-shop a napsat popisek.\n"
        "NIKDY si nevymýšlej jiný druh zboží, drž se striktně zadaného produktu!\n\n"
        f"PŮVODNÍ NÁZEV PRO KONTEXT: {original_name}\n"
        f"OČIŠTĚNÝ NÁZEV Z REGEX FILTRU: {clean_name}\n"
        f"INSTRUKCE PRO STYL POPISKU: {instruction}\n"
        f"MAXIMÁLNÍ DÉLKA POPISKU: {max_chars} znaků.\n\n"
        "PRAVIDLA PRO REAKCI:\n"
        "Odpověz výhradně formátem JSON.\n"
        "Do pole 'audit_status' napiš buď '✅ V pořádku' nebo '⚠️ AI doporučuje úpravu' nebo '❌ Prázdný název'.\n"
        "Do pole 'nazev_opraveny' napiš gramaticky opravený a reprezentativní název tohoto konkrétního produktu.\n"
        "Do pole 'popis' napiš marketingový popisek pro tento produkt.\n"
        "Do pole 'klicova_slova' dej seznam 2-5 klíčových slov.\n"
    )
    
    try:
        response = client.messages.create(
            model=MODEL_NAME, 
            max_tokens=1024, 
            messages=[{"role": "user", "content": text_zadani}]
        )
        
        # Bezpečné načtení textu bez ohledu na verzi knihovny anthropic
        if hasattr(response, 'content') and isinstance(response.content, list):
            block = response.content[0]
            raw_text = block.text.strip() if hasattr(block, 'text') else str(block).strip()
        else:
            raw_text = response.content.strip()

        if not raw_text.startswith("{"):
            start_idx = raw_text.find("{")
            end_idx = raw_text.rfind("}") + 1
            if start_idx != -1 and end_idx != 0: 
                raw_text = raw_text[start_idx:end_idx]
        return json.loads(raw_text)
    except Exception as e:
        return {"audit_status": "❌ Chyba", "nazev_opraveny": clean_name, "popis": f"AI Chyba: {str(e)}", "klicova_slova": []}

# ──────────────────────────────────────────────────────────────
# MAIN INTERFACE
# ──────────────────────────────────────────────────────────────
st.title("🪄 AI E-commerce Data Cleaner & Enricher PRO")
st.caption("Verze: **SHOPTET AUTOMATION ENGINE**")

tab1, tab2 = st.tabs(["📁 Nahrát Shoptet CSV / Excel", "✍️ Ruční zadání textu"])
full_products_count = 0
original_df = None
final_products_list = []
demo_selection_strategy = "Prvních 20 produktů"

with tab1:
    uploaded_file = st.file_uploader("Vyberte váš exportní soubor z e-shopu", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                original_df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
            else:
                original_df = pd.read_excel(uploaded_file)
            
            # Detekce sloupce s názvem
            default_index = 0
            for target_col in ["název", "nazev", "name"]:
                if target_col in original_df.columns:
                    default_index = list(original_df.columns).index(target_col)
                    break
                
            column_with_names = st.selectbox(
                "Vyberte sloupec, který obsahuje názvy produktů k vyčištění:", 
                options=original_df.columns, 
                index=default_index
            )
            
            series_products = original_df[column_with_names].fillna("").astype(str)
            full_products_count = len(original_df)
            final_products_list = series_products.tolist()
            
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric(label="Celkový počet položek v souboru", value=f"{full_products_count} ks")
            with col_stat2:
                st.info(f"Všechny ostatní parametry (Kódy, Ceny, Sklady) budou plně zachovány a přeloženy do Shoptet formátu.")
                
            if full_products_count > 20:
                st.warning("💡 **Demo režim:** Soubor obsahuje více produktů. V rámci ukázky zpracujeme max 20 řádků.")
                demo_selection_strategy = st.radio(
                    "Vyberte, jakých 20 vzorků chcete vyzkoušet:",
                    ["Prvních 20 produktů", "Náhodný výběr 20 produktů"]
                )
        except Exception as e:
            st.error(f"Chyba při čtení souboru: {e}")

with tab2:
    if uploaded_file is None:
        sample_data = "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\nSilonové punčochy dnes za 30% dolů"
        text_input = st.text_area("Vložte zkušební názvy (každý na nový řádek):", value=sample_data, height=120)
        final_products_list = [line.strip() for line in text_input.split("\n") if line.strip()]
        full_products_count = len(final_products_list)
        original_df = pd.DataFrame({"název": final_products_list})
        column_with_names = "název"

if "processed_df" not in st.session_state: st.session_state.processed_df = None
if "total_time" not in st.session_state: st.session_state.total_time = 0
if "was_truncated" not in st.session_state: st.session_state.was_truncated = False

run_main = st.button("🚀 Spustit kompletní transformaci dat", type="primary")

# ──────────────────────────────────────────────────────────────
# SPUŠTĚNÍ TRANSFORMACE
# ──────────────────────────────────────────────────────────────
if run_main or run_sidebar:
    if not final_products_list:
        st.error("Žádná data k analýze.")
    elif client is None:
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
        audit_statuses = []
        regex_clean_names = []
        final_names_shoptet = []
        descriptions_shoptet = []
        seo_keywords = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        for idx in range(limit):
            status_text.text(f"Zpracovávám {idx + 1} z {limit}...")
            original_name = str(working_df.iloc[idx][column_with_names])
            
            clean_name = clean_product_name(original_name, custom_stopwords, all_selected_chars)
            if not clean_name: clean_name = "Produkt"
                
            ai_data = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            
            audit_statuses.append(ai_data.get("audit_status", "✅ V pořádku"))
            regex_clean_names.append(clean_name)
            final_names_shoptet.append(ai_data.get("nazev_opraveny", clean_name))
            descriptions_shoptet.append(ai_data.get("popis", ""))
            
            kw_data = ai_data.get("klicova_slova", [])
            seo_keywords.append(", ".join(kw_data) if isinstance(kw_data, list) else str(kw_data))
            
            progress_bar.progress((idx + 1) / limit)
            
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        
        # Uložení náhledů pro uživatele
        working_df["Původní špinavý název"] = working_df[column_with_names]
        working_df[column_with_names] = final_names_shoptet
        
        desc_col = "popis" if "popis" in working_df.columns else ("description" if "description" in working_df.columns else "popis")
        working_df[desc_col] = descriptions_shoptet
        
        working_df.insert(0, "🔍 Stav auditu", audit_statuses)
        working_df["_seo_cache"] = seo_keywords
        
        st.session_state.processed_df = working_df

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ A KPI METRIK
# ──────────────────────────────────────────────────────────────
if st.session_state.processed_df is not None:
    df_results = st.session_state.processed_df
    
    st.write("---")
    st.subheader("✨ Výsledky transformace")
    
    if st.session_state.was_truncated:
        st.warning(f"⚠️ **Ukázka zpracování dat dokončena:** Ze souboru o celkovém počtu {full_products_count} položek bylo vybráno 20 vzorků.")
        
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="Zobrazeno v tabulce", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování AI", value=f"{st.session_state.total_time} s")
    with col_kpi3:
        saved_minutes = len(df_results) * 3
        st.metric(label="Ušetřený čas copywritera", value=f"~ {saved_minutes} min", delta="🔥 Efektivita")
    
    st.write("---")
    st.subheader("📊 KONTROLA: Audit a rychlá editace dat")
    st.info("💡 **Tip:** V tabulce vidíte česká záhlaví pro pohodlnou editaci. Při stažení se automaticky přeloží do formátu pro Shoptet.")
    
    view_df = df_results.copy()
    if "_seo_cache" in view_df.columns:
        view_df = view_df.drop(columns=["_seo_cache"])
        
    edited_df = st.data_editor(view_df, use_container_width=True)
    
    st.write("---")
    st.write("### 📥 Nastavení exportu a stažení")
    
    add_seo_column = st.checkbox("Přidat do stahovaného souboru sloupec s SEO klíčovými slovy", value=False)
    
    download_df = pd.DataFrame(edited_df)
    
    if add_seo_column and "_seo_cache" in df_results.columns:
        download_df["shortDescription"] = df_results["_seo_cache"].values
        
    if "🔍 Stav auditu" in download_df.columns:
        download_df = download_df.drop(columns=["🔍 Stav auditu"])
    if "Původní špinavý název" in download_df.columns:
        download_df = download_df.drop(columns=["Původní špinavý název"])
        
    # --- AUTOMATICKÝ PŘEKLAD DO SHOPTET FORMÁTU ---
    shoptet_mapping = {
        "kód": "code",
        "název": "name",
        "nazev": "name",
        "cena": "price",
        "nákupní cena": "purchasePrice",
        "nakupni cena": "purchasePrice",
        "dph": "vat",
        "sklad": "stock",
        "jednotka": "unit",
        "výrobce": "manufacturer",
        "vyrobce": "manufacturer",
        "kategorie": "categoryText",
        "popis": "description"
    }
    download_df = download_df.rename(columns=shoptet_mapping)
        
    csv_buffer = download_df.to_csv(index=False, encoding='utf-8-sig', sep=';')
    st.download_button(
        label="📥 STÁHNOUT FINÁLNÍ ČISTÉ CSV PRO SHOPTET IMPORT", 
        data=csv_buffer, 
        file_name="shoptet_import_ready.csv", 
        mime="text/csv", 
        use_container_width=True
    )
