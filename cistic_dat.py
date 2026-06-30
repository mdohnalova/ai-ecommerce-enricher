import streamlit as st
import anthropic
import json
import re
import time
from datetime import datetime

# ============================================================
# PROJECT:  AI E-Commerce Enricher (Pro Version)
# ============================================================

st.set_page_config(page_title="AI E-commerce Enricher", page_icon="🛍️", layout="wide")

# Inicializace Claude API klienta
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    if api_key and "sk-ant-" in api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = None
except Exception:
    client = None

# Použijeme nejstabilnější model řady 3.5 Sonnet
MODEL_NAME = "claude-3-5-sonnet-20240620"

# ──────────────────────────────────────────────────────────────
# BOČNÍ PANEL (NASTAVENÍ NA MÍRU PRO UŽIVATELE)
# ──────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Nastavení filtrů na míru")

st.sidebar.markdown("""
**Výchozí automatické čištění:**
- Odstranění speciálních znaků (`!`, `?`, `*`, `#`, `@`, `%`)
- Odstranění slev v procentech (např. `30%`, `15 %`)
- Odstranění marketingových frází (`akce`, `sleva`, `výprodej`, `doprava zdarma`, `novinka`)
""")

# Interaktivní správa dalších zakázaných slov
custom_stopwords_input = st.sidebar.text_area(
    "Vlastní zakázaná slova / balast (oddělte čárkou):",
    value="dnes za dolů, skladem, ihned, super cena",
    help="Slova, která chcete z názvů produktů automaticky vymazat."
)

# Rozsekání zadaných slov na seznam
custom_stopwords = [word.strip() for word in custom_stopwords_input.split(",") if word.strip()]

# ──────────────────────────────────────────────────────────────
# ČISTIČ NÁZVŮ PRODUKTŮ (Regex s dynamickými stop-slovy)
# ──────────────────────────────────────────────────────────────
def clean_product_name(name, user_stopwords):
    if not name:
        return ""
    result = name.strip()
    
    # 1. Základní marketingové fráze
    marketing_phrases = [
        r"doprava\s+zdarma", r"akce[!]*", r"sleva[!]*", 
        r"výprodej[!]*", r"hit\s+sezóny", r"novinka[!]*"
    ]
    for phrase in marketing_phrases:
        result = re.sub(phrase, "", result, flags=re.IGNORECASE)

    # 2. Odstranění vlastních slov zadaných uživatelem v aplikaci
    for word in user_stopwords:
        # Vytvoří bezpečný regex pro celé slovo bez ohledu na velikost písmen
        word_pattern = r"\b" + re.escape(word) + r"\b"
        result = re.sub(word_pattern, "", result, flags=re.IGNORECASE)

    # 3. Odstranění procent, speciálních znaků a úprava mezer
    result = re.sub(r"\d+\s*%", "", result)
    result = re.sub(r"[!?*#@%^&]", "", result)
    result = re.sub(r"\s*[-–]+\s*", " - ", result)
    result = re.sub(r"(\s*-\s*){2,}", " - ", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"^-\s*", "", result)
    result = re.sub(r"\s*-$", "", result).strip()
    
    return result.strip()

# ──────────────────────────────────────────────────────────────
# AI OBOHACENÍ & STRUKTUROVÁNÍ VÝSTUPU
# ──────────────────────────────────────────────────────────────
def enrich_product_with_ai(clean_name, original_name):
    if not client:
        return get_mock_data(clean_name)
        
    system_prompt = (
        "Jsi špičkový e-commerce manažer a copywriter. Tvým úkolem je vzít očištěný název produktu, "
        "vytvořit pro něj profesionální, lákavý popisek pro e-shop a vybrat 3 SEO klíčová slova. "
        "Odpovídej VŽDY pouze validním JSONem bez jakýchkoliv keců okolo."
    )

    user_prompt = (
        f"Původní špinavý název: {original_name}\n"
        f"Očištěný základ: {clean_name}\n\n"
        "Úkol:\n"
        "1. Zkontroluj očištěný základ. Pokud v něm zůstal logický nesmysl (např. nedočištěné spojky), oprav ho na pěkný název produktu.\n"
        "2. Napiš čtivý e-commerce popisek (2-3 věty) pro zákazníky.\n"
        "3. Vyber 3 relevantní klíčová slova oddělená čárkami.\n\n"
        "Odpověz výhradně v tomto formátu:\n"
        '{"nazev_opraveny": "Finální Krásný Název", "popis": "Text popisku...", "klicova_slova": ["slovo1", "slovo2", "slovo3"]}'
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
        return get_mock_data(clean_name)

def get_mock_data(clean_name):
    """Záložní plán, pokud API klíč stále nefunguje - nyní s využitím zadaného názvu"""
    title = clean_name.title() if clean_name else "Produkt"
    return {
        "nazev_opraveny": title,
        "popis": f"Tento produkt {title} přináší skvělé řešení pro každodenní použití. Je navržen s ohledem na vysokou kvalitu, spolehlivost a maximální spokojenost zákazníka.",
        "klicova_slova": [clean_name, "e-commerce", "kvalita"]
    }

# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ (UI)
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Cleaner")
st.write("Profesionální nástroj pro automatické čištění databází a generování obsahu pomocí AI.")

# Ukázková data
sample_data = (
    "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\n"
    "silonové punčochy dnes za 30% dolů\n"
    "modré autíčko Hotwheels skladem\n"
    "?? Samsung Galaxy S24 - HIT SEZÓNY ??"
)

text_input = st.text_area(
    "Vložte špinavé názvy produktů (každý produkt na nový řádek):",
    value=sample_data,
    height=150
)

if st.button("Spustit AI transformaci", type="primary"):
    raw_products = [line.strip() for line in text_input.split("\n") if line.strip()]
    
    if not raw_products:
        st.error("Zadejte prosím alespoň jeden produkt.")
    else:
        results = []
        progress_bar = st.progress(0)
        
        for idx, original_name in enumerate(raw_products):
            # Čištění s využitím uživatelských zakázaných slov z bočního panelu
            clean_name = clean_product_name(original_name, custom_stopwords)
            
            start_time = time.time()
            ai_data = enrich_product_with_ai(clean_name, original_name)
            runtime = round(time.time() - start_time, 2)
            
            kw_data = ai_data.get("klicova_slova", [])
            kw_str = ", ".join(kw_data) if isinstance(kw_data, list) else str(kw_data)
            
            res_dict = {
                "Původní text": original_name,
                "Regex čištění": clean_name if clean_name else "Smazáno jako balast",
                "Finální název (AI)": ai_data.get("nazev_opraveny", clean_name),
                "AI Marketingový Popis": ai_data.get("popis", ""),
                "Klíčová slova (SEO)": kw_str,
                "Čas zpracování (s)": runtime
            }
            results.append(res_dict)
            progress_bar.progress((idx + 1) / len(raw_products))
            
        if results:
            st.write("---")
            st.subheader("📊 Výsledná strukturovaná data")
            st.dataframe(results, use_container_width=True)
            
            # Možnost stažení výsledků
            output_data = {
                "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "product_count": len(results),
                "custom_stopwords_used": custom_stopwords,
                "products": results
            }
            json_buffer = json.dumps(output_data, ensure_ascii=False, indent=2)
            
            st.download_button(
                label="📥 Stáhnout JSON výsledky",
                data=json_buffer,
                file_name="ai_enricher_clean_data.json",
                mime="application/json"
            )
