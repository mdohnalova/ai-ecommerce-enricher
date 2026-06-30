# AI E-commerce Enricher

> Automated pipeline that reads dirty product names from a CSV file, cleans them with Python regex, enriches them with AI-generated sales descriptions and SEO keywords via Anthropic Claude, and saves the results as both JSON and CSV — ready for developers and managers alike.

---

## The Problem

E-commerce product catalogs are messy. Product names imported from suppliers or scraped from various sources are often full of noise: marketing slogans, discount labels, random punctuation, and inconsistent casing. Feeding this dirty data into a product page or a search engine hurts both the customer experience and SEO performance.

**AI E-commerce Enricher** solves this in a fully automated pipeline: it reads raw product names from `products_input.csv`, cleans them with Python regex, calls Claude AI to generate compelling descriptions and targeted SEO keywords, and saves the results in two formats — structured JSON for developers and a clean CSV that any manager can open in Excel.

---

## Features

- **CSV input** — reads product names from `products_input.csv`; auto-creates the file with sample data on first run
- **Data cleaning** — strips marketing phrases (`AKCE`, `SLEVA`, `DOPRAVA ZDARMA`, etc.), percentage values, special characters, and normalizes whitespace and dashes
- **AI-powered enrichment** — generates a 2–3 sentence sales-oriented product description for each item
- **SEO keyword extraction** — produces three relevant search keywords per product, tailored for Czech e-commerce
- **Dual output** — saves results as `ai_enricher_output.json` (for developers) and `products_output.csv` (for managers / Excel)
- **Processing speed tracking** — measures and records how long each product takes to process
- **Safe input handling** — skips products whose names are empty after cleaning, preventing unnecessary API calls
- **API key guard** — exits early with a clear error message if the Anthropic API key is not configured

---

## How It Works

The pipeline runs in five sequential steps, each handled by a dedicated Python function:

```
products_input.csv
      │  (auto-created with sample data if missing)
      ▼
┌──────────────────────────────────┐
│  0. ensure_input_csv_exists()    │  Creates sample CSV on first run
│     load_products_from_csv()     │  Reads product names into a list
└──────────────────────────────────┘
      │  list of raw names
      ▼
┌──────────────────────────────────┐
│  1. clean_product_name()         │  Python regex — removes noise, normalizes text
└──────────────────────────────────┘
      │  clean name
      ▼
┌──────────────────────────────────┐
│  2. enrich_product_with_ai()     │  Claude API — generates description + keywords
└──────────────────────────────────┘
      │  AI data + processing time
      ▼
┌──────────────────────────────────┐
│  3. process_product()            │  Pipeline glue — combines steps 1 & 2
└──────────────────────────────────┘
      │  result dict per product
      ▼
┌──────────────────────────────────┐
│  4a. save_results_json()         │  → ai_enricher_output.json  (for developers)
│  4b. save_results_csv()          │  → products_output.csv      (for managers)
└──────────────────────────────────┘
```

### Example

**Input** (`products_input.csv`):
```
product_name
NIKE AIR MAX 90 ** AKCE!! ** SLEVA 30%
```

**After cleaning:**
```
nike air max 90
```

**JSON output** (`ai_enricher_output.json`):
```json
{
  "original_name": "NIKE AIR MAX 90 ** AKCE!! ** SLEVA 30%",
  "clean_name": "nike air max 90",
  "ai_description": "Nike Air Max 90 je ikonická teniskа, která spojuje legendární streetwear styl s výjimečným pohodlím...",
  "keywords": ["nike air max 90", "tenisky nike", "sneakers klasika"],
  "processing_speed_seconds": 1.97
}
```

**CSV output** (`products_output.csv`) — opens directly in Excel:
```
Original Name             | Clean Name      | AI Description          | Keywords
NIKE AIR MAX 90 ** AKC... | nike air max 90 | Nike Air Max 90 je ...  | nike air max 90, tenisky nike, sneakers klasika
```

---

## Output Format

### ai_enricher_output.json

```json
{
  "processing_date": "2026-06-19 21:58:14",
  "product_count": 4,
  "total_processing_seconds": 7.43,
  "products": [
    {
      "original_name": "NIKE AIR MAX 90 ** AKCE!! ** SLEVA 30%",
      "clean_name": "nike air max 90",
      "ai_description": "Nike Air Max 90 je ikonická ...",
      "keywords": ["nike air max 90", "tenisky nike", "sneakers klasika"],
      "processing_speed_seconds": 1.97
    }
  ]
}
```

### products_output.csv

| Original Name | Clean Name | AI Description | Keywords |
|---|---|---|---|
| NIKE AIR MAX 90 \*\* AKCE!! \*\* SLEVA 30% | nike air max 90 | Nike Air Max 90 je ikonická ... | nike air max 90, tenisky nike, sneakers klasika |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3 |
| AI model | Anthropic Claude (`claude-opus-4-8`) |
| AI SDK | `anthropic` (official Python SDK) |
| Text processing | `re` (Python standard library — regex) |
| Data I/O | `csv` (Python standard library) |
| Data serialization | `json` (Python standard library) |
| Performance tracking | `time` (Python standard library) |
| Output formats | JSON + CSV, both UTF-8 encoded |

---

## Setup & Usage

**1. Install the dependency:**
```bash
pip3 install anthropic
```

**2. Set your Anthropic API key:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```
Get your key at [console.anthropic.com](https://console.anthropic.com) under **API Keys**.

**3. Run the script:**
```bash
python3 cistic_dat.py
```

On the **first run**, the script automatically creates `products_input.csv` with four sample dirty product names. On every subsequent run, it reads whatever product names are in that file.

**To process your own products:** open `products_input.csv`, keep the `product_name` header, and replace or add product names — one per line. Then run the script again.

---

## Project Structure

```
Python-studium/
├── cistic_dat.py              # Main script — full pipeline
├── products_input.csv         # Input: dirty product names (one per line)
├── ai_enricher_output.json    # Output: structured results for developers
├── products_output.csv        # Output: clean table for managers / Excel
└── README.md                  # This file
```

---

## About

Built as a portfolio project demonstrating practical Python data cleaning, Anthropic Claude API integration, CSV/JSON data handling, and structured AI output for real-world e-commerce use cases.
