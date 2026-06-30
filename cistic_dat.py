import streamlit as st
import anthropic
import json
import re
import time
import pandas as pd
from datetime import datetime

# ============================================================
# PROJECT:  AI E-Commerce Enricher (Ultimate Enterprise Version)
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
# BOČNÍ PANEL: NASTAVENÍ ČIŠTĚNÍ A AI PROMPTU NA MÍRU
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

st.sidebar.subheader("3. Nastavení AI textů")
ai_tone = st.sidebar.selectbox(
    "Tón e-commerce popisku:",
    ["Profesionální a důvěryhodný", "Přátelský a lidský", "Úderný a prodejní (Hard-sell)", "Eko / Udržitelný styl"]
)
desc_length = st.sidebar.slider("Délka popisku (počet vět):", min_value=1, max_value=5, value=3)

# ──────────────────────────────────────────────────────────────
# DETEKCE A ČIŠTĚNÍ TEXTU (REGEX)
# ──────────────────────────────────────────────────────────────
def clean_product_name(name, user_stopwords):
    if not name or pd.isna(name):
        return ""
    result = str(name).strip()
    
    # Odstranění vlastních stop-slov
    for word in user_stopwords:
        word_pattern = r"\b" + re.escape(word) + r"\b"
        result = re.sub(word_pattern, "", result, flags=re.IGNORECASE)

    # Volitelné čištění podle checkboxů
    if clean_percent:
        result = re.sub(r"\d+\s*%", "", result)
    if clean_special:
        result = re.sub(r"[!?*#@%^&]", "", result)
    if clean_numbers:
        result = re.sub(r"\b\d+\b", "", result)

    # Čištění přebytečných mezer a pomlček
    result = re.sub(r"\s*[-–]+\s*", " - ", result)
    result = re.sub(r"(\s*-\s*){2,}", " - ", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"^-\s*", "", result)
    result = re.sub(r"\s*-$", "", result).strip()
    
    return result

# ──────────────────────────────────────────────────────────────
# CHYTRÝ AI PROMPT & FALLBACK SIMULACE
# ──────────────────────────────────────────────────────────────
def enrich_product_with_ai(clean_name, original_name):
    if not client:
        return get_intelligent_mock(clean_name, ai_tone)
        
    system_prompt = (
        "Jsi expert na SEO a e-commerce textaci. Tvým úkolem je vzít očištěná data produktu, "
        "vytvořit dokonalý prodejní titulek, unikátní popisek a klíčová slova pro vyhledávače. "
        "Odpovídej POUZE ve validním formátu JSON."
    )

    user_prompt = (
        f"Původní text: {original_name}\n"
        f"Vyčištěný základ: {clean_name}\n\n"
        f"Požadavky na výstup:\n"
        f"1. Uprav vyčištěný základ na gramaticky správný a hezký název produktu.\n"
        f"2. Napiš e-commerce popisek o délce přesně {desc_length} vět.\n"
        f"3. Použij tento tón hlasu: {ai_tone}.\n"
        f"4. Vyber 3 vysoce hledaná SEO klíčová slova/fráze.\n\n"
        "Formát odpovědi (JSON):\n"
        '{"nazev_opraveny": "...", "popis": "...", "klicova_slova": ["...", "...", "..."]}'
    )

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception:
        return get_intelligent_mock(clean_name, ai_tone)

def get_intelligent_mock(clean_name, tone):
    """Dynamická lokální simulace pro generování chytřejších textů podle tónu"""
    title = clean_name.title() if clean_name else "Produkt"
    
    # Variace textů na základě zvoleného tónu v aplikaci
    if "Prodejní" in tone:
        popis = f"Nenechte si ujít jedinečnou šanci a pořiďte si {title} ještě dnes! Tento bestseller vyniká bezkonkurenčním výkonem a okamžitě posune vaše každodenní výsledky na novou úroveň. Nakupujte chytře!"
    elif "Přátelský" in tone:
        popis = f"Pokud hledáte parťáka, na kterého je spolehnutí, {title} vás určitě nezklame. Navrhli jsme ho tak, aby vám dělal radost každý den a skvěle zapadl do vašeho životního stylu."
    elif "Eko" in tone:
        popis = f"Udržitelná volba s ohledem na naši planetu. {title} v sobě spojuje ekologicky šetrné materiály s dlouhou životností, čímž minimalizuje ekologickou stopu bez kompromisů v kvalitě."
    else:
        popis = f"Profesionální řešení {title} splňuje nejvyšší průmyslové standardy kvality a spolehlivosti. Představuje optimální investici pro dlouhodobé a efektivní využití v e-commerce."

    return {
        "nazev_opraveny": title,
        "popis": popis,
        "klicova_slova": [clean_name, "seo-optimalizace", "e-shop-produkt"]
    }

# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ: NAHRÁVÁNÍ SOUBORŮ & TEXT BOX
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Data Cleaner PRO")
st.write("Nahrajte produktový export vašeho klienta (CSV/Excel) nebo vložte texty ručně.")

# Záložky pro flexibilní vstup dat
tab1, tab2 = st.tabs(["📁 Nahrát soubor (CSV / Excel)", "✍️ Ruční zadání textu"])

raw_products = []

with tab1:
    uploaded_file = st.file_uploader("Vyberte soubor s produkty (.csv, .xlsx)", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_input = pd.read_csv(uploaded_file)
            else:
                df_input = pd.read_excel(uploaded_file)
            
            # Výběr sloupce, kde jsou názvy schované
            column_with_names = st.selectbox("Vyberte sloupec, který obsahuje názvy produktů:", df_input.columns)
            raw_products = df_input[column_with_names].dropna().astype(str).tolist()
            st.success(f"Úspěšně načteno {len(raw_products)} produktů ze souboru.")
        except Exception as e:
            st.error(f"Chyba při čtení souboru: {e}")

with tab2:
    sample_data = "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\nsilonové punčochy dnes za 30% dolů\nmodré autíčko Hotwheels skladem"
    text_input = st.text_area("Vložte názvy (každý na nový řádek):", value=sample_data, height=120)
    if not raw_products and text_input:
        raw_products = [line.strip() for line in text_input.split("\n") if line.strip()]

# Spuštění celé transformace
if st.button("🚀 Spustit kompletní transformaci dat", type="primary"):
    if not raw_products:
        st.error("Žádná data k analýze. Nahrajte soubor nebo vložte text.")
    else:
        results = []
        progress_bar = st.progress(0)
        
        for idx, original_name in enumerate(raw_products):
            # 1. Krok: Vyčištění přes regex s ohledem na boční nastavení
            clean_name = clean_product_name(original_name, custom_stopwords)
            
            # 2. Krok: Volání AI / Chytré simulace s tónem hlasu
            start_time = time.time()
            ai_data = enrich_product_with_ai(clean_name, original_name)
            runtime = round(time.time() - start_time, 2)
            
            kw_data = ai_data.get("klicova_slova", [])
            kw_str = ", ".join(kw_data) if isinstance(kw_data, list) else str(kw_data)
            
            results.append({
                "Původní text": original_name,
                "Regex čištění": clean_name if clean_name else "Vymazáno",
                "Finální název (AI)": ai_data.get("nazev_opraveny", clean_name),
                "AI Popisek": ai_data.get("popis", ""),
                "SEO Klíčová slova": kw_str,
                "Čas (s)": runtime
            })
            progress_bar.progress((idx + 1) / len(raw_products))
            
        if results:
            st.write("---")
            st.subheader("📊 Výsledná strukturovaná data pro e-shop")
            df_results = pd.DataFrame(results)
            st.dataframe(df_results, use_container_width=True)
            
            # Tlačítka pro stažení ve dvou formátech
            col1, col2 = st.columns(2)
            with col1:
                csv_buffer = df_results.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 Stáhnout jako CSV pro Excel",
                    data=csv_buffer,
                    file_name="clean_ecommerce_data.csv",
                    mime="text/csv"
                )
            with col2:
                json_buffer = json.dumps(results, ensure_ascii=False, indent=2)
                st.download_button(
                    label="📥 Stáhnout kompletní JSON",
                    data=json_buffer,
                    file_name="clean_ecommerce_data.json",
                    mime="application/json"
                )
