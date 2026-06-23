# ============================================================
# PROJECT:  AI E-Commerce Enricher
# POPIS:    Načte špinavé názvy produktů z CSV, vyčistí je
#           Pythonem, obohacuje Claude AI o popisky a SEO
#           klíčová slova. Výstup ukládá jako JSON i CSV.
# MODEL:    Anthropic Claude (claude-opus-4-8)
# URČENO:   Portfolio projekt | AI Vibecoder pozice
# ============================================================

# Importujeme modul "re" pro práci s regulárními výrazy (hledání vzorů v textu)
import re

# Importujeme modul "json" pro ukládání výsledků ve formátu JSON pro vývojáře
import json

# Importujeme modul "csv" pro čtení vstupního souboru a zápis výstupu pro Excel
import csv

# Importujeme modul "os" pro kontrolu existence souborů a přístup k API klíči
import os

# Importujeme modul "time" pro měření doby zpracování každého produktu
import time

# Importujeme officiální knihovnu Anthropic pro komunikaci s Claude AI modelem
import anthropic

# Importujeme třídu datetime pro přidání časového razítka k uloženým výsledkům
from datetime import datetime


# ──────────────────────────────────────────────────────────────
# KROK 0: SPRÁVA CSV VSTUPNÍHO SOUBORU
# Pokud vstupní soubor neexistuje, vytvoří ho s ukázkovými daty.
# ──────────────────────────────────────────────────────────────

# Definujeme konstantu s cestou ke vstupnímu CSV souboru
INPUT_CSV = "products_input.csv"

# Definujeme konstantu s cestou k výstupnímu CSV souboru
OUTPUT_CSV = "products_output.csv"

# Definujeme konstantu s cestou k výstupnímu JSON souboru
OUTPUT_JSON = "ai_enricher_output.json"


def ensure_input_csv_exists():
    # Zkontrolujeme, zda vstupní soubor již existuje (os.path.exists vrací True/False)
    if os.path.exists(INPUT_CSV):
        # Soubor existuje – není co tvořit, vrátíme se zpět
        return

    # Soubor neexistuje – oznámíme uživateli, že ho vytváříme
    print(f"  Soubor '{INPUT_CSV}' nenalezen – vytvářím ukázkový vstupní soubor...")

    # Definujeme ukázkové špinavé produkty, které zapíšeme jako demo data
    sample_products = [
        # Produkt s mezerami, vykřičníky a frází "doprava zdarma"
        "   !!! BOTY ADIDAS TERREX - DOPRAVA ZDARMA !!!   ",
        # Produkt s hvězdičkami, klíčovým slovem "akce" a procentuální slevou
        "NIKE AIR MAX 90 ** AKCE!! ** SLEVA 30%",
        # Produkt s otazníky a frází "hit sezóny"
        "  ???  Samsung Galaxy S24 - HIT SEZÓNY  ???  ",
        # Čistý produkt bez balastu – ověříme, že čistění dobrá data nepoškodí
        "Sluchátka Sony WH-1000XM5",
    ]

    # Otevřeme nový soubor pro zápis s UTF-8 kódováním pro podporu české diakritiky
    # newline="" zabraňuje Pythonu přidávat prázdné řádky navíc na Windows
    with open(INPUT_CSV, "w", encoding="utf-8", newline="") as csv_file:
        # Vytvoříme zapisovač CSV – oddělovač je čárka (standardní CSV formát)
        writer = csv.writer(csv_file)

        # Zapíšeme záhlaví sloupce jako první řádek souboru
        writer.writerow(["product_name"])

        # Projdeme každý ukázkový produkt a zapíšeme ho na vlastní řádek
        for product in sample_products:
            # writerow() zapíše jeden řádek; seznam s jedním prvkem = jeden sloupec
            writer.writerow([product])

    # Potvrdíme uživateli, že soubor byl úspěšně vytvořen
    print(f"  ✓ Soubor '{INPUT_CSV}' vytvořen se {len(sample_products)} ukázkovými produkty.\n")


def load_products_from_csv():
    # Otevřeme vstupní CSV soubor pro čtení s UTF-8 kódováním
    with open(INPUT_CSV, "r", encoding="utf-8") as csv_file:
        # Vytvoříme čtenáře CSV, který automaticky mapuje sloupce na klíče dle záhlaví
        reader = csv.DictReader(csv_file)

        # Načteme všechny řádky do seznamu; každý řádek je slovník {"product_name": "..."}
        # Ořežeme okraje každého názvu hned při načítání, aby čistění bylo přesné
        products = [row["product_name"].strip() for row in reader if row["product_name"].strip()]

    # Vrátíme seznam názvů produktů připravených ke zpracování
    return products


# ──────────────────────────────────────────────────────────────
# KROK 1: ČISTIČ NÁZVŮ PRODUKTŮ
# Odstraňuje marketingový balast a normalizuje text před odesláním do AI.
# ──────────────────────────────────────────────────────────────

def clean_product_name(name):
    # Ověříme, zda vstup vůbec existuje (není None ani prázdný řetězec)
    if not name:
        # Vrátíme prázdný řetězec – není co čistit
        return ""

    # Zkopírujeme vstup do nové proměnné, abychom neměnili originální data
    result = name

    # Ořežeme bílé znaky (mezery, tabulátory) na začátku a konci textu
    result = result.strip()

    # Sestavíme seznam regex vzorů pro marketingové fráze, které chceme smazat
    marketing_phrases = [
        # Vzor pro "doprava zdarma" – \s+ znamená jedna nebo více mezer uprostřed
        r"doprava\s+zdarma",
        # Vzor pro "akce" s libovolným počtem vykřičníků za ní ([!]* = nula a více !)
        r"akce[!]*",
        # Vzor pro "sleva" s libovolným počtem vykřičníků
        r"sleva[!]*",
        # Vzor pro "výprodej" s libovolným počtem vykřičníků
        r"výprodej[!]*",
        # Vzor pro "hit sezóny" – \s+ zachytí různé počty mezer mezi slovy
        r"hit\s+sezóny",
        # Vzor pro "novinka" s libovolným počtem vykřičníků
        r"novinka[!]*",
    ]

    # Projdeme každý vzor v seznamu a smažeme ho z textu
    for phrase in marketing_phrases:
        # re.sub nahradí výskyt vzoru prázdným řetězcem; IGNORECASE ignoruje velikost písmen
        result = re.sub(phrase, "", result, flags=re.IGNORECASE)

    # Smažeme procentuální výrazy i s číslem před nimi (např. "30%", "50 %")
    # \d+ = jedna nebo více číslic, \s* = nula nebo více mezer, % = znak procenta
    result = re.sub(r"\d+\s*%", "", result)

    # Smažeme zbývající nežádoucí speciální znaky (vykřičníky, hvězdičky, otazníky…)
    result = re.sub(r"[!?*#@%^&]", "", result)

    # Normalizujeme pomlčky – každou skupinu pomlček nahradíme jednou čistou " - "
    # \s*[-–]+\s* zachytí pomlčky obklopené libovolnými mezerami
    result = re.sub(r"\s*[-–]+\s*", " - ", result)

    # Smažeme zdvojené " - - " vzory vzniklé po odebrání marketingových frází
    # (\s*-\s*){2,} = sekvence "pomlčka s mezerami" opakující se alespoň dvakrát
    result = re.sub(r"(\s*-\s*){2,}", " - ", result)

    # Nahradíme více mezer za sebou jednou jedinou mezerou
    result = re.sub(r"\s+", " ", result)

    # Ořežeme okraje textu po všech předchozích nahrazeních
    result = result.strip()

    # Odstraníme osamělou pomlčku na úplném začátku textu (^- = začátek řetězce)
    result = re.sub(r"^-\s*", "", result)

    # Odstraníme osamělou pomlčku na úplném konci textu (-$ = konec řetězce)
    result = re.sub(r"\s*-$", "", result)

    # Ořežeme okraje naposledy, pro jistotu po odebrání krajních pomlček
    result = result.strip()

    # Pokud po všem čištění zbyde jen osamělá pomlčka, vrátíme prázdný řetězec
    if result == "-":
        # Přepíšeme na prázdný řetězec – samotná pomlčka není platný název
        result = ""

    # Převedeme na malá písmena pro konzistentní výstup vhodný do databáze
    result = result.lower()

    # Vrátíme hotový vyčištěný název
    return result


# ──────────────────────────────────────────────────────────────
# KROK 2: AI OBOHACENÍ – VOLÁNÍ CLAUDE API
# Pošle čistý název produktu Claudovi a získá zpět popisek + klíčová slova.
# ──────────────────────────────────────────────────────────────

def enrich_product_with_ai(client, clean_name):
    # Definujeme systémový prompt – říkáme Claudovi, jakou roli má hrát
    system_prompt = (
        # Claude bude hrát roli zkušeného copywritera pro e-commerce na českém trhu
        "Jsi profesionální e-commerce copywriter specializující se na český trh. "
        # Vytváří krátké popisky, které motivují zákazníka ke koupi
        "Vytváříš krátké, prodejní popisky produktů a vybíráš přesná SEO klíčová slova. "
        # Instrukce k formátu výstupu – musí být čisté JSON bez přídavného textu
        "Vždy odpovídáš POUZE ve validním JSON formátu bez jakéhokoli dalšího textu."
    )

    # Sestavíme uživatelský prompt – konkrétní zadání pro tento produkt
    user_prompt = (
        # Sdělíme Claudovi název produktu, který má zpracovat
        f"Název produktu: {clean_name}\n\n"
        # Popíšeme, co přesně chceme vygenerovat
        "Vytvoř prosím:\n"
        # Požadujeme lákavý popisek délky 2–3 věty motivující zákazníka ke koupi
        "1. Lákavý a stručný e-commerce popisek (2-3 věty), který motivuje zákazníka ke koupi.\n"
        # Požadujeme přesně 3 klíčová slova pro SEO optimalizaci stránky produktu
        "2. Přesně 3 klíčová slova vhodná pro SEO optimalizaci produktové stránky.\n\n"
        # Předepíšeme přesný formát odpovědi – Claude musí vrátit JSON bez ničeho navíc
        "Odpověz VÝHRADNĚ v tomto JSON formátu (bez markdown, bez dalšího textu):\n"
        # Ukázka přesné JSON struktury, kterou očekáváme
        '{"popis": "...", "klicova_slova": ["slovo1", "slovo2", "slovo3"]}'
    )

    # Zavoláme Claude API – pošleme žádost a počkáme na odpověď
    response = client.messages.create(
        # Použijeme nejschopnější dostupný model Anthropic
        model="claude-opus-4-8",
        # Maximální délka odpovědi v tokenech (token ≈ část slova nebo interpunkce)
        max_tokens=1024,
        # Předáme systémový prompt definující roli a chování AI
        system=system_prompt,
        # Předáme historii konverzace – zde jen jedna uživatelská zpráva
        messages=[
            # Jeden slovník s rolí "user" a obsahem zprávy – role: user = zpráva od nás
            {"role": "user", "content": user_prompt}
        ]
    )

    # Vytáhneme textový obsah z prvního bloku odpovědi (content je seznam bloků)
    response_text = response.content[0].text

    # Parsujeme JSON text do Python slovníku – json.loads() převede text na dict
    data = json.loads(response_text)

    # Vrátíme slovník obsahující klíče "popis" a "klicova_slova"
    return data


# ──────────────────────────────────────────────────────────────
# KROK 3: PIPELINE – ČIŠTĚNÍ + AI OBOHACENÍ DOHROMADY
# Zpracuje jeden produkt od špinavého názvu až po hotový AI výstup.
# ──────────────────────────────────────────────────────────────

def process_product(client, original_name):
    # Vytiskneme informaci, který produkt právě zpracováváme
    print(f"  → Zpracovávám: '{original_name}'")

    # Zaznamenáme čas začátku zpracování – time.time() vrací sekundy od epochy (1970)
    start_time = time.time()

    # KROK A: Zavoláme čistící funkci a uložíme výsledek
    clean_name = clean_product_name(original_name)

    # Pokud je čistý název prázdný, produkt přeskočíme – nemá smysl ho posílat do AI
    if not clean_name:
        # Oznámíme uživateli, že produkt byl přeskočen
        print("  ✗ Přeskočeno – název je po vyčištění prázdný.\n")
        # Vrátíme None jako signál, že výsledek neexistuje
        return None

    # KROK B: Zavoláme AI funkci pro generování popisku a klíčových slov
    ai_data = enrich_product_with_ai(client, clean_name)

    # Vypočítáme dobu zpracování: aktuální čas mínus čas startu = elapsed čas v sekundách
    # round(..., 2) zaokrouhlí na dvě desetinná místa pro přehledný výstup
    processing_seconds = round(time.time() - start_time, 2)

    # Sestavíme výsledný slovník se všemi informacemi o produktu
    result = {
        # Původní špinavý název tak, jak přišel na vstup
        "original_name": original_name.strip(),
        # Vyčištěný název po odstranění marketingového balastu
        "clean_name": clean_name,
        # Lákavý prodejní popisek vygenerovaný Claude AI
        "ai_description": ai_data["popis"],
        # Seznam tří SEO klíčových slov vygenerovaných Claude AI
        "keywords": ai_data["klicova_slova"],
        # Doba zpracování tohoto produktu v sekundách (čištění + AI volání dohromady)
        "processing_speed_seconds": processing_seconds,
    }

    # Vypíšeme výsledky do konzole pro průběžnou vizuální kontrolu
    print(f"  ✓ Čistý název:   {clean_name}")
    # Zkrátíme popisek na 75 znaků, aby se vešel na jeden řádek terminálu
    print(f"  ✓ AI popisek:    {ai_data['popis'][:75]}...")
    # Klíčová slova vypíšeme oddělená čárkami pro přehlednost
    print(f"  ✓ Klíč. slova:   {', '.join(ai_data['klicova_slova'])}")
    # Vypíšeme dobu zpracování s jednotkou sekund
    print(f"  ✓ Čas:           {processing_seconds}s\n")

    # Vrátíme kompletní slovník s výsledky zpracování
    return result


# ──────────────────────────────────────────────────────────────
# KROK 4A: ULOŽENÍ DO JSON (pro vývojáře)
# Zapíše strukturovaná data s metadaty do JSON souboru.
# ──────────────────────────────────────────────────────────────

def save_results_json(results):
    # Sečteme celkový čas zpracování všech produktů pomocí funkce sum()
    total_seconds = round(sum(r["processing_speed_seconds"] for r in results), 2)

    # Sestavíme výstupní datovou strukturu s metadaty a samotnými produkty
    output_data = {
        # Přidáme časové razítko zpracování ve formátu RRRR-MM-DD HH:MM:SS
        "processing_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # Uložíme celkový počet úspěšně zpracovaných produktů
        "product_count": len(results),
        # Uložíme celkový čas zpracování všech produktů dohromady v sekundách
        "total_processing_seconds": total_seconds,
        # Uložíme seznam všech produktů s jejich výsledky
        "products": results,
    }

    # Otevřeme výstupní soubor pro zápis s explicitně nastaveným kódováním UTF-8
    with open(OUTPUT_JSON, "w", encoding="utf-8") as file:
        # ensure_ascii=False zachová českou diakritiku místo \uXXXX escape sekvencí
        # indent=2 přidá odsazení 2 mezerami pro čitelnost souboru v textovém editoru
        json.dump(output_data, file, ensure_ascii=False, indent=2)

    # Vrátíme název souboru pro potvrzující výpis v hlavním bloku
    return OUTPUT_JSON


# ──────────────────────────────────────────────────────────────
# KROK 4B: ULOŽENÍ DO CSV (pro manažery a Excel)
# Zapíše výsledky do tabulkového CSV souboru čitelného v Excelu.
# ──────────────────────────────────────────────────────────────

def save_results_csv(results):
    # Otevřeme výstupní CSV soubor pro zápis s UTF-8 kódováním
    # newline="" zabraňuje Pythonu přidávat prázdné řádky navíc na Windows
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as csv_file:
        # Definujeme názvy sloupců přesně tak, jak je chceme vidět v záhlaví Excelu
        fieldnames = ["Original Name", "Clean Name", "AI Description", "Keywords"]

        # Vytvoříme zapisovač CSV s pojmenovanými sloupci (DictWriter mapuje dict na řádek)
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        # Zapíšeme záhlaví jako první řádek souboru
        writer.writeheader()

        # Projdeme každý výsledek a zapíšeme ho jako jeden řádek CSV tabulky
        for result in results:
            # Klíčová slova jsou v Pythonu seznam – pro CSV je spojíme čárkami do jednoho řetězce
            keywords_str = ", ".join(result["keywords"])

            # Zapíšeme jeden řádek; klíče slovníku musí přesně odpovídat fieldnames
            writer.writerow({
                # Původní špinavý název produktu
                "Original Name": result["original_name"],
                # Vyčištěný název po odstranění marketingového balastu
                "Clean Name": result["clean_name"],
                # AI popisek – celý text bez zkracování
                "AI Description": result["ai_description"],
                # Klíčová slova jako jeden řetězec oddělený čárkami (Excel-friendly)
                "Keywords": keywords_str,
            })

    # Vrátíme název souboru pro potvrzující výpis v hlavním bloku
    return OUTPUT_CSV


# ──────────────────────────────────────────────────────────────
# HLAVNÍ SPOUŠTĚCÍ BLOK
# Spustí se pouze při přímém spuštění souboru (ne při importu jako modul).
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Vytiskneme hlavičku aplikace pro přehledný výstup v terminálu
    print("=" * 60)
    # Vytiskneme název projektu a použitou technologii
    print("   AI E-COMMERCE ENRICHER  |  Powered by Claude AI")
    # Vytiskneme oddělovač pro vizuální přehlednost
    print("=" * 60)
    # Přidáme prázdný řádek pro oddělení hlavičky od obsahu
    print()

    # Zkontrolujeme, zda je API klíč nastaven v proměnné prostředí
    if not os.getenv("ANTHROPIC_API_KEY"):
        # Vytiskneme chybovou zprávu – skript bez klíče nemůže komunikovat s AI
        print("CHYBA: Proměnná prostředí ANTHROPIC_API_KEY není nastavena.")
        # Poskytneme uživateli instrukci, jak klíč nastavit v terminálu
        print("Nastav ho v terminálu tímto příkazem a skript spusť znovu:")
        # Ukážeme přesný příkaz pro bash/zsh (macOS, Linux)
        print('  export ANTHROPIC_API_KEY="sk-ant-..."')
        # Ukončíme program s exit kódem 1 (= chyba, ne normální ukončení)
        exit(1)

    # KROK 0: Zajistíme, že vstupní CSV soubor existuje (vytvoříme ho pokud ne)
    ensure_input_csv_exists()

    # KROK 1: Načteme seznam produktů z CSV souboru
    products = load_products_from_csv()

    # Oznámíme uživateli, kolik produktů bylo načteno z CSV
    print(f"  ✓ Načteno {len(products)} produktů ze souboru '{INPUT_CSV}'.\n")

    # Vytvoříme instanci Anthropic klienta – SDK automaticky načte klíč z prostředí
    client = anthropic.Anthropic()

    # Vytvoříme prázdný seznam pro ukládání výsledků zpracování
    all_results = []

    # Vytiskneme nadpis sekce zpracování
    print("--- ZPRACOVÁNÍ PRODUKTŮ ---\n")

    # Projdeme každý produkt; enumerate() přidá čítač od 1 pro výpis průběhu
    for index, product in enumerate(products, start=1):
        # Vytiskneme číslo aktuálního produktu z celkového počtu
        print(f"[{index}/{len(products)}]")

        # Zavoláme pipeline funkci – čištění + AI obohacení dohromady
        result = process_product(client, product)

        # Pokud funkce vrátila výsledek (ne None), přidáme ho do seznamu
        if result:
            # append() přidá slovník na konec seznamu výsledků
            all_results.append(result)

    # Zkontrolujeme, zda existují výsledky k uložení
    if all_results:
        # Vytiskneme oddělovač před informací o uložení
        print("-" * 60)

        # KROK 4A: Uložíme výsledky jako JSON pro vývojáře
        json_file = save_results_json(all_results)
        # Oznámíme uživateli, kam byl JSON uložen
        print(f"✓ JSON výstup (pro vývojáře):  {json_file}")

        # KROK 4B: Uložíme výsledky jako CSV pro manažery a Excel
        csv_file = save_results_csv(all_results)
        # Oznámíme uživateli, kam bylo CSV uloženo
        print(f"✓ CSV výstup  (pro manažery):  {csv_file}")

    # Vytiskneme závěrečný oddělovač
    print("=" * 60)
    # Vytiskneme finální zprávu s počtem zpracovaných produktů
    print(f"   Hotovo! Zpracováno {len(all_results)} produktů.")
    # Vytiskneme oddělovač pro uzavření výstupu
    print("=" * 60)
