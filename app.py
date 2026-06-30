import streamlit as st
import anthropic
import csv
import json
import re
import time
from datetime import datetime

# ============================================================
# CONFIGURATION & STREAMLIT SECRETS
# ============================================================
st.set_page_config(page_title="AI E-commerce Enricher", page_icon="🛍️", layout="wide")

# Inicializace Claude API klienta pomocí Streamlit Secrets
# Náborář hned uvidí bezpečné řešení bez hardcodování klíčů
try:
    api_key = st.secrets["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)
except Exception:
    client = None

# Použijeme aktuální doporučený model (Claude 3.5 Sonnet)
MODEL_NAME = "claude-3-5-sonnet-latest"

# ──────────────────────────────────────────────────────────────
# CORE LOGIC (Regex cleaning & AI Enrichment)
# ──────────────────────────────────────────────────────────────

def clean_product_name(name):
    if not name:
        return ""
    result = name.strip()
    
    marketing_phrases = [
        r"doprava\s+zdarma", r"akce[!]*", r"sleva[!]*", 
        r"výprodej[!]*", r"hit\s+sezóny", r"novinka[!]*"
    ]
    for phrase in marketing_phrases:
        result = re.sub(phrase, "", result, flags=re.IGNORECASE)

    result = re.sub(r"\d+\s*%", "", result)
    result = re.sub(r"[!?*#@%^&]", "", result)
    result = re.sub(r"\s*[-–]+\s*", " - ", result)
    result = re.sub(r"(\s*-\s*){2,}", " - ", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"^-\s*", "", result)
    result = re.sub(r"\s*-$", "", result).strip()
    
    return result.lower() if result != "-" else ""

def enrich_product_with_ai(clean_name):
    if not client:
        return {"popis": "Ukázkový popisek (API klíč není nastaven).", "klicova_slova": ["tag1", "tag2", "tag3"]}
        
    system_prompt = (
        "Jsi profesionální e-commerce copywriter specializující se na český trh. "
        "Vytváříš krátké, prodejní popisky produktů a vybíráš přesná SEO klíčová slova. "
        "Vždy odpovídáš POUZE ve validním JSON formátu bez jakéhokoli dalšího textu."
    )

    user_prompt = (
        f"Název produktu: {clean_name}\n\n"
        "Vytvoř prosím:\n"
        "1. Lákavý a stručný e-commerce popisek (2-3 věty), který motivuje zákazníka ke koupi.\n"
        "2. Přesně 3 klíčová slova vhodná pro SEO optimalizaci produktové stránky.\n\n"
        "Odpověz VÝHRADNĚ v tomto JSON formátu (bez markdown, bez dalšího textu):\n"
        '{"popis": "...", "klicova_slova": ["slovo1", "slovo2", "slovo3"]}'
    )

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return json.loads(response.content[0].text)

# ──────────────────────────────────────────────────────────────
# STREAMLIT USER INTERFACE
# ──────────────────────────────────────────────────────────────

st.title("🛍️ AI E-commerce Enricher")
st.write("Automatizované čištění produktových názvů pomocí **Regexu** a obohacení textů přes **Claude AI**.")

if not client:
    st.warning("⚠️ **Anthropic API klíč není nastaven v Streamlit Secrets.** Aplikace nyní běží v ukázkovém režimu simulace.")

# Ukázková data pro rychlé otestování náborářem
sample_data = (
    "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\n"
    "NIKE AIR MAX 90 ** AKCE!! ** SLEVA 30%\n"
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
        
        st.subheader("⚙️ Průběh zpracování")
        
        for idx, original_name in enumerate(raw_products):
            clean_name = clean_product_name(original_name)
            
            if not clean_name:
                st.text(f"❌ {original_name} -> Přeskočeno (po vyčištění prázdné)")
                continue
                
            start_time = time.time()
            try:
                ai_data = enrich_product_with_ai(clean_name)
                runtime = round(time.time() - start_time, 2)
                
                res_dict = {
                    "Původní název": original_name,
                    "Vyčištěný název": clean_name,
                    "AI Popis": ai_data.get("popis", ""),
                    "Klíčová slova": ", ".join(ai_data.get("klicova_slova", [])),
                    "Čas (s)": runtime
                }
                results.append(res_dict)
                st.success(f"✔️ {clean_name} zpracováno za {runtime}s")
            except Exception as e:
                st.error(f"Chyba u produktu {clean_name}: {e}")
                
            progress_bar.progress((idx + 1) / len(raw_products))
            
        if results:
            st.write("---")
            st.subheader("📊 Výsledná data")
            st.dataframe(results, use_container_width=True)
            
            # Možnost stažení výsledků jako CSV přímo z webu
            csv_buffer = io = json.dumps(results, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 Stáhnout JSON výsledky",
                data=csv_buffer,
                file_name="ai_enricher_output.json",
                mime="application/json"
            )