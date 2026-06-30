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
# INICIALIZACE SKUTEČNÉHO ANTHROPIC CLIENTA (BEZ TESTOVACÍCH PODMÍNEK)
# ──────────────────────────────────────────────────────────────
try:
    # Načtení klíče přesně podle formátu Streamlit Secrets [anthropic] api_key
    api_key = st.secrets["anthropic"]["api_key"]
    client = anthropic.Anthropic(api_key=api_key)
except Exception as e:
    st.error(f"❌ Chyba při načítání API klíče ze Streamlit Secrets: {e}")
    client = None

MODEL_NAME = "claude-3-haiku-20240307"

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
# LOGIKA ČIŠTĚNÍ
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
        
    result = re.sub(r"\s+", " ", result).strip()
    return result

# OSTRÉ VOLÁNÍ AI SE ZABEZPEČENÍM PROTI CHYBĚ 400
def enrich_product_with_ai(clean_name, original_name, max_chars, instruction):
    if not client:
        return {"nazev_opraveny": clean_name, "popis": "Chyba: API klient není inicializován.", "klicova_slova": []}
    
    # Sloučili jsme instrukce do jednoho balíku, aby API neházelo chybu "System prompts are not supported"
    ujednoceny_prompt = (
        "Jsi špičkový SEO a copywriter specialista pro e-shopy. Odpovědi vracej striktně v platném JSON formátu.\n\n"
        f"Základní vyčištěný název produktu: {clean_name}\n"
        f"Původní neočištěný název pro kontext: {original_name}\n"
        f"Instrukce pro tvorbu popisku a úpravu: {instruction}\n"
        f"Maximální délka popisku: {max_chars} znaků.\n"
        'Odpověz striktně jako JSON v tomto formátu: {"nazev_opraveny": "...", "popis": "...", "klicova_slova": ["...", "...", "..."]}'
    )
    
    try:
        response = client.messages.create(
            model=MODEL_NAME, 
            max_tokens=1024, 
            messages=[{"role": "user", "content": ujednoceny_prompt}]
        )
        return json.loads(response.content[0].text)
    except Exception as e:
        # Pokud AI přesto selže, vypíšeme skutečnou chybu do tabulky
        return {"nazev_opraveny": clean_name, "popis": f"AI Chyba: {str(e)}", "klicova_slova": ["chyba"]}
# ──────────────────────────────────────────────────────────────
# HLAVNÍ ROZHRANÍ
# ──────────────────────────────────────────────────────────────
st.title("🛍️ AI E-commerce Enricher & Data Cleaner PRO")
st.caption("Verze: **ENTERPRISE DEMO**")

tab1, tab2 = st.tabs(["📁 Nahrát soubor (CSV / Excel)", "✍️ Ruční zadání textu"])
full_products_count = 0
final_products_list = []
demo_selection_strategy = "Prvních 20 produktů"

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
            
            full_products_count = len(series_products)
            final_products_list = series_products.tolist()
            
            st.write("---")
            st.subheader("📊 Statistiky nahraného souboru")
            
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric(label="Celkový počet nalezených produktů v souboru", value=f"{full_products_count} ks")
            with col_stat2:
                st.info(f"Analyzovaný sloupec: **{column_with_names}**")
            
            if full_products_count > 20:
                st.warning(f"💡 **Omezení bezplatné verze:** V souboru bylo úspěšně nalezeno všech **{full_products_count}** produktů. V rámci Demo režimu však můžete jednorázově otestovat transformaci maximálně na **20 produktech**.")
                demo_selection_strategy = st.radio(
                    "Vyberte, jakých 20 vzorků chcete z nahrávky vyzkoušet:",
                    ["Prvních 20 produktů", "Náhodný výběr 20 produktů"]
                )
                
        except Exception as e:
            st.error(f"Chyba při čtení souboru: {e}")

with tab2:
    if uploaded_file is None:
        sample_data = "!!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!\nSilonové punčochy dnes za 30% dolů\n~ %&- Hrábě zahradní ~\nKyselina hyaluronová 5%\n^^ Pracovní rukavice ^^\nSkladem Hodinky Apple 15%"
        text_input = st.text_area("Vložte názvy (každý na nový řádek):", value=sample_data, height=120)
        final_products_list = [line.strip() for line in text_input.split("\n") if line.strip()]
        full_products_count = len(final_products_list)

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
if run_main or run_sidebar:
    if not final_products_list:
        st.error("Žádná data k analýze.")
    elif not client:
        st.error("Nemohu spustit transformaci, protože API klíč Anthropic není správně nakonfigurován ve Streamlit Secrets.")
    else:
        if len(final_products_list) > 20:
            st.session_state.was_truncated = True
            if demo_selection_strategy == "Náhodný výběr 20 produktů":
                processing_list = random.sample(final_products_list, 20)
            else:
                processing_list = final_products_list[:20]
        else:
            processing_list = final_products_list
            st.session_state.was_truncated = False
            
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        start_bulk_time = time.time()
        
        for idx, original_name in enumerate(processing_list):
            status_text.text(f"Zpracovávám {idx + 1} z {len(processing_list)}...")
            
            clean_name = clean_product_name(original_name, custom_stopwords, all_selected_chars)
            ai_data = enrich_product_with_ai(clean_name, original_name, max_char_length, ai_instruction)
            
            final_title = ai_data.get("nazev_opraveny", clean_name)
            kw_data = ai_data.get("klicova_slova", [])
            kw_str = ", ".join(kw_data) if isinstance(kw_data, list) else str(kw_data)
            
            suspicious_chars = re.findall(r"[^\w\s.,%\-\u00C0-\u017F]", str(clean_name))
            
            if suspicious_chars:
                unique_chars = "".join(sorted(list(set(suspicious_chars))))
                audit_status = f"⚠️ Opravit znaky ({unique_chars})"
            elif not clean_name or clean_name == "Vymazáno":
                audit_status = "❌ Prázdný název"
            else:
                audit_status = "✅ V pořádku"
            
            results.append({
                "🔍 Stav auditu": audit_status,
                "Původní text": original_name,
                "Regex čištění": clean_name if clean_name else "Vymazáno",
                "Finální název (AI)": final_title,
                "AI Popisek (Shoptet Ready)": ai_data.get("popis", ""),
                "SEO Klíčová slova": kw_str
            })
            progress_bar.progress((idx + 1) / len(processing_list))
            
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.total_time = round(time.time() - start_bulk_time, 1)
        st.session_state.processed_df = pd.DataFrame(results)

# ──────────────────────────────────────────────────────────────
# ZOBRAZENÍ VÝSLEDKŮ S FILTREM SLOUPCŮ PRO EXPORT
# ──────────────────────────────────────────────────────────────
if st.session_state.processed_df is not None:
    df_results = st.session_state.processed_df
    
    st.write("---")
    st.subheader("✨ Výsledky transformace")
    
    if st.session_state.was_truncated:
        st.warning(f"⚠️ **Ukázka zpracování dat dokončena:** Ze souboru o celkovém počtu {full_products_count} položek bylo na základě vaší volby vybráno a obohaceno 20 vzorků. Kompletní databázi vám rádi odemkneme v plné verzi.")
    else:
        st.success("✅ Všechny produkty ze souboru byly úspěšně zpracovány.")
        
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric(label="Zobrazeno v tabulce", value=f"{len(df_results)} ks")
    with col_kpi2:
        st.metric(label="Čas zpracování AI", value=f"{st.session_state.total_time} s")
    with col_kpi3:
        saved_minutes = len(df_results) * 3
        st.metric(label="Ušetřený čas copywritera", value=f"~ {saved_minutes} min", delta="🔥 Efektivita")
    
    st.write("---")
    st.write("### 📥 Export a nastavení stahovaných dat")
    
    export_columns = st.multiselect(
        "Vyberte sloupce, které chcete zahrnout do výsledného exportu (CSV / JSON):",
        options=list(df_results.columns),
        default=list(df_results.columns)
    )
    
    if not export_columns:
        st.error("⚠️ Musíte vybrat alespoň jeden sloupec pro export.")
    else:
        df_to_export = df_results[export_columns]
        
        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 3])
        with col_btn1:
            csv_buffer = df_to_export.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(label="📥 Stáhnout Shoptet CSV", data=csv_buffer, file_name="shoptet_clean_data.csv", mime="text/csv", use_container_width=True)
        with col_btn2:
            json_buffer = json.dumps(df_to_export.to_dict(orient="records"), ensure_ascii=False, indent=2)
            st.download_button(label="📥 Stáhnout kompletní JSON", data=json_buffer, file_name="shoptet_clean_data.json", mime="application/json", use_container_width=True)
        with col_btn3:
            st.button("🔗 Kopírovat odkaz pro sdílení výsledků", on_click=lambda: st.toast("Odkaz byl zkopírován do schránky!"), use_container_width=True)
    
    st.write("---")
    st.subheader("📊 2. KROK KONTROLY: Audit a rychlá editace dat")
    st.info("💡 **Tip pro audit:** Kliknutím na záhlaví sloupce **🔍 Stav auditu** seřadíte položky tak, aby se řádky označené s **⚠️** posunuly nahoru a mohli jste je bleskově ručně opravit.")
    
    edited_df = st.data_editor(df_results, use_container_width=True)
    st.session_state.processed_df = pd.DataFrame(edited_df)
