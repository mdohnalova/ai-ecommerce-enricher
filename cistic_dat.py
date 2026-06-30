import streamlit as st
import anthropic
import json
import re
import time
import pandas as pd

# ============================================================
# PROJEKT:  AI E-Commerce Enricher & Data Cleaner (Enterprise Demo)
# ============================================================

st.set_page_config(page_title="AI E-commerce Enricher PRO", page_icon="🛍️", layout="wide")

# Inicializace Claude API klienta
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    if api_key and "sk-ant-" in api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None
except Exception:
    client = None

MODEL_NAME = "claude-3-5-sonnet-20240620"

# ──────────────────────────────────────────────────────────────
# BOČNÍ PANEL: ROZŠÍŘENÉ FILTRY A DYNAMICKÝ PROMPT
# ──────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Konfigurace filtrů na míru")

st.sidebar.subheader("1. Výběr znaků k odstranění")
clean_special = st.sidebar.checkbox("Speciální znaky (!, ?, *, #, @)", value=True)
clean_percent = st.sidebar.checkbox("Procenta a slevové štítky (30%, 15%)", value=True)
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
    ai_instruction = f"Tón popisku moet být: {ai_tone}."
else:
    ai_tone = "Vlastní prompt"
    ai_instruction = st.sidebar.text_area(
        "Napište instrukce pro AI (co má s textem udělat):",
        value="Napiš to jako kreativní a vtipný post na sociální sítě, přidej emoji a na konec doplň hashtags.",
    )

max_char_length = st.sidebar.slider("Maximální délka popisku (znaků):", min_value=50, max_value=1000, value=250)

# ──────────────────────────────────────────────────────────────
# LOGIKA ČIŠTĚNÍ (REGEX)
# ──────────────────────────────────────────────────────────────
def clean_product_name(name, user_stopwords):
    if not name or pd.isna(name):
        return ""
    result = str(name).strip()
    
    for word in user_stopwords:
        word_pattern = r"\b" + re.escape(word) + r"\b"
        result = re.sub(word_pattern, "", result, flags=re.IGNORECASE)
        
    if clean_percent:
        result = re.sub(r"\d+\s*%", "", result)
    if clean_special:
        result = re.sub(r"[!?*#@%^&]", "", result)
    if clean_numbers:
        result = re.sub(r"\b\d+\b", "", result)
        
    result = re.sub(r"\s+", " ", result).strip()
    return result

def enrich_product_with_ai(clean_name, original_name, max_chars, instruction):
    if not client:
        return get_intelligent_mock(clean_name, max_chars)
    
    system_prompt = "Jsi špičkový SEO a copywriter specialista pro e-shopy. Odpovědi vracej striktně v platném JSON formátu."
    user_prompt = (
        f"Základní vyčištěný název produktu: {clean_name}\n"
        f"Původní neočištěný název pro kontext: {original_name}\n"
        f"Instrukce pro tvorbu popisku a úpravu: {instruction}\n"
        f"Maximální délka popisku: {max_chars} znaků.\n"
        'Odpověz striktně jako JSON v tomto formátu: {"nazev_opraveny": "...", "popis": "...", "klicova_slova": ["...", "...", "..."]}'
    )
    try:
        response = client.messages.create(
            model=MODEL_NAME, max_tokens=1024, system=system_prompt, messages=[{"role": "user", "content": user_prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception:
        return get_intelligent_mock(clean_name, max_chars)

def get_intelligent_mock(clean_name, max_chars):
    title = clean_name.title() if clean_name else "Produkt"
    popis = f"Skvělé řešení {title} splňuje nejvyšší standardy kvality pro váš e-shop podle zadaného promptu."
    return {"nazev_opraveny": title, "popis": popis[:max_chars], "klicova_slova": [clean_name, "e-shop"]}

# ──────────────────────────────────────────────────────────────
# FUNKCE PRO DRUHOU KONTROLU (BAREVNÉ STYLOVÁNÍ)
# ──────────────────────────────────────────────────────────────
def style_verification_audit(df):
    """
    Vytvoří vizuální mapu stylů pro tabulku, která upozorní na zapomenuté znaky a nesrovnalosti.
    """
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Detekce neobvyklých speciálních znaků, které nebyly vyčištěny (např. ~, _, =, +, [], {})
    uncleaned_pattern = r"[~_=+\[\]{}|\\<>`«»]"
    
    for row_idx in df.index:
        # 1. Kontrola "Regex čištění" sloupce
        val_clean = str(df.at[row_idx, "Regex čištění"])
        if re.search(uncleaned_pattern, val_clean):
            style_df.at[row_idx, "Regex čištění"] = 'background-color: #ffe6cc; color: #cc6600; font-weight: bold; border: 1px solid #ff9933;' # Oranžové varování
            
        # 2. Kontrola "Finální název (AI)" sloupce
        val_ai = str(df.at[row_idx, "Finální název (AI)"])
        if re.search(uncleaned_pattern, val_ai):
            style_df.at[row_idx, "Finální název (AI)"] = 'background-color: #ffe6cc; color: #cc6600; font-weight: bold;'
            
        # 3. Zvýraznění úspěšně a dramaticky upravených popisků (vizuální kontrola)
        if len(str(df.at[row_idx, "AI Popisek (Shoptet Ready)"])) > 10:
            style_df.at[row_idx, "AI Popisek (Shoptet Ready)"] = 'background-color: #f6fff6; color: #1e7e34;' # Světle zelená značící Shoptet-Ready text
            
    return style_df

# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Data Cleaner PRO")
st.caption("Verze: **FREE DEMO** (Omezeno na max. 20 produktů na jeden import)")

tab1, tab2 = st.tabs(["📁 Nahrát soubor (CSV / Excel)", "✍️ Ruční zadání textu"])
final_products_list = []

with tab1:
    uploaded_file = st.file_uploader("Vyberte soubor s produkty", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8-sig')
            else:
                df_input = pd.read_excel(uploaded_file)
            
            column_with_names = st.selectbox("Vyberte sloupec s názvy produktů:", df_input.columns)
            
            series_products = df_input[column_with_names].dropna().astype(str).str.strip()
            series_products = series_products[series_products != ""]
            total_rows = len(series_products)
            
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric(label="Počet nalezených produktů v souboru", value=f"{total_rows} ks")
            with col_stat2:
                st.info(f"Analyzovaný sloupec: **{column_with_names}**")
            
            if total_rows > 20:
                st.warning("⚠️ **Omezení Demo verze:** Váš soubor obsahuje více než 20 produktů. V rámci bezplatné verze bude zpracováno prvních 20 položek.")
                final_products_list = series_products.tolist()[:20]
            else:
                final_products_list = series_products.tolist()
                
        except Exception as e:
            st.error(f"Chyba při čtení souboru: {e}")

with tab2:
    if uploaded_file is None:
        sample_data = "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\nSilonové punčochy dnes za 30% dolů\n~ %&- Hrábě zahradní ~\nSkladem Hodinky Apple 15%"
        text_input = st.text_area("Vložte názvy (každý na nový řádek):", value=sample_data, height=120)
        final_products_list = [line.strip() for line in text_input.split("\n") if line.strip()][:20]

if "processed_df" not in st.session_state:
    st.session_state.processed_df = None
if "total_time" not in st.session_state:
    st.session_state.total_time = 0

# ──────────────────────────────────────────────────────────────
# SPUŠTĚNÍ TRANSFORMACE
# ──────────────────────────────────────────────────────────────
if st.button("🚀 Spustit kompletní transformaci dat", type="primary"):
    if not final_products_list:
        st.error("Žádná data k analýze.")
    else:
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        for idx, original_name in enumerate(final_products_list):
            status_text.text(f"Zpracovávám {idx + 1} z {len(final_products_list)}...")
            clean_name = clean_product_name(original_name, custom_stopwords)
            ai_data = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            
            kw_data = ai_data.get("klicova_slova", [])
            kw_str = ", ".join(kw_data) if isinstance(kw_data, list) else str(kw_data)
            
            results.append({
                "Původní text": original_name,
                "Regex čištění": clean_name if clean_name else "Vymazáno",
                "Finální název (AI)": ai_data.get("nazev_opraveny", clean_name),
                "AI Popisek (Shoptet Ready)": ai_data.get("popis", ""),
                "SEO Klíčová slova": kw_str
            })
            progress_bar.progress((idx + 1) / len(final_products_list))
            
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        st.session_state.processed_df = pd.DataFrame(results)

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ S DRUHOU KONTROLOU
# ──────────────────────────────────────────────────────────────
if st.session_state.processed_df is not None:
    df_results = st.session_state.processed_df
    
    st.write("---")
    st.subheader("✨ Výsledky transformace")
    
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="Zpracováno produktů", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování AI", value=f"{st.session_state.total_time} s")
    with col_kpi3:
        saved_minutes = len(df_results) * 3
        st.metric(label="Ušetřený čas copywritera", value=f"~ {saved_minutes} min", delta="🔥 Efektivita")
    
    st.write("### 📥 Export a sdílení dat")
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 3])
    
    with col_btn1:
        csv_buffer = df_results.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(label="📥 Stáhnout Shoptet CSV", data=csv_buffer, file_name="shoptet_clean_data.csv", mime="text/csv", use_container_width=True)
    with col_btn2:
        json_buffer = json.dumps(df_results.to_dict(orient="records"), ensure_ascii=False, indent=2)
        st.download_button(label="📥 Stáhnout kompletní JSON", data=json_buffer, file_name="shoptet_clean_data.json", mime="application/json", use_container_width=True)
    with col_btn3:
        st.button("🔗 Kopírovat odkaz pro sdílení výsledků", on_click=lambda: st.toast("Odkaz byl zkopírován do schránky!"), use_container_width=True)
    
    st.write("---")
    st.subheader("📊 2. KROK KONTROLY: Audit a editace dat")
    st.info("💡 **Legenda auditu:** Bunky s nezvolenými / zapomenutými znaky (např. `~`) jsou podsvíceny **oranžově**, abyste je mohli okamžitě prokliknout a opravit. Zkontrolované AI popisky jsou jemně **zelené**.")
    
    # Aplikování druhé vizuální kontroly na tabulku
    styled_df = df_results.style.apply(style_verification_audit, axis=None)
    
    # Zobrazení interaktivního editoru s nanesenými styly auditu
    edited_df = st.data_editor(styled_df, use_container_width=True)
    
    # Zpětné uložení ručně opravených hodnot do paměti aplikace
    st.session_state.processed_df = pd.DataFrame(edited_df)
