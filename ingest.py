"""
Ingestion script for Recipe Box dataset.
Reads the three JSON files, normalizes/cleans noise (e.g. 'ADVERTISEMENT'),
computes step count and ingredient count, and stores records in SQLite with FTS5 search index.
"""

import json
import os
import re
import sqlite3
import time

DB_PATH = "recipes.db"
DATASET_FILES = [
    ("ar", "dataset/recipes_raw_nosource_ar.json"),
    ("epi", "dataset/recipes_raw_nosource_epi.json"),
    ("fn", "dataset/recipes_raw_nosource_fn.json"),
]

def clean_ingredient(item: str) -> str:
    """Removes 'ADVERTISEMENT' and trailing whitespace from ingredient strings."""
    if not isinstance(item, str):
        return ""
    # Remove 'ADVERTISEMENT' (case-insensitive) and normalize spaces
    cleaned = re.sub(r'\bADVERTISEMENT\b', '', item, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def count_steps(instructions: str) -> int:
    """
    Transparent step-counting rule:
    1. If newlines exist separating substantive lines, count non-empty lines.
    2. Otherwise, split by punctuation boundaries followed by capital letters or numbers.
    3. Minimum 1 if text is non-empty, 0 if empty.
    """
    if not instructions or not isinstance(instructions, str):
        return 0
    text = instructions.strip()
    if not text:
        return 0
    lines = [line.strip() for line in text.split('\n') if len(line.strip()) > 3]
    if len(lines) > 1:
        return len(lines)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text) if len(s.strip()) > 3]
    return max(1, len(sentences))

def init_db(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS recipes")
    cur.execute("DROP TABLE IF EXISTS recipes_fts")
    
    cur.execute("""
        CREATE TABLE recipes (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            raw_id TEXT NOT NULL,
            title TEXT NOT NULL,
            ingredients_json TEXT NOT NULL,
            instructions TEXT NOT NULL,
            picture_link TEXT,
            ingredient_count INTEGER NOT NULL,
            step_count INTEGER NOT NULL,
            ingredients_clean TEXT NOT NULL
        )
    """)
    
    # Indexes for fast aggregations and analytical queries
    cur.execute("CREATE INDEX idx_ingredient_count ON recipes(ingredient_count)")
    cur.execute("CREATE INDEX idx_step_count ON recipes(step_count)")
    cur.execute("CREATE INDEX idx_title ON recipes(title)")

    # FTS5 full-text search index for fast keyword matching
    cur.execute("""
        CREATE VIRTUAL TABLE recipes_fts USING fts5(
            id UNINDEXED,
            title,
            ingredients,
            tokenize = 'porter unicode61'
        )
    """)
    conn.commit()

def ingest():
    start_time = time.time()
    print("Initializing database...")
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cur = conn.cursor()

    total_records = 0
    skipped_records = 0
    batch_recipes = []
    batch_fts = []
    batch_size = 5000

    for source_key, file_path in DATASET_FILES:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
        print(f"Processing {file_path}...")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for raw_id, recipe in data.items():
            total_records += 1
            if not recipe or not isinstance(recipe, dict):
                skipped_records += 1
                continue

            title = recipe.get("title")
            raw_ingredients = recipe.get("ingredients")
            instructions = recipe.get("instructions")
            picture_link = recipe.get("picture_link", "")

            # Filter out entries that lack even a title or instructions/ingredients completely
            if not title or not title.strip():  #only rows with reall title survives
                skipped_records += 1
                continue

            title_clean = title.strip()
            instructions_clean = (instructions or "").strip()

            # Clean and filter ingredient list
            cleaned_ingredients = []
            if isinstance(raw_ingredients, list):
                for ing in raw_ingredients:
                    c = clean_ingredient(ing)
                    if c:
                        cleaned_ingredients.append(c)

            # Precomputed metrics
            ing_count = len(cleaned_ingredients)
            s_count = count_steps(instructions_clean)
            ingredients_combined = " ".join(cleaned_ingredients)

            # Preserve stable ID: source prefix + raw_id ensures global uniqueness
            stable_id = f"{source_key}_{raw_id}"

            batch_recipes.append((
                stable_id,
                source_key,
                raw_id,
                title_clean,
                json.dumps(cleaned_ingredients, ensure_ascii=False),
                instructions_clean,
                picture_link,
                ing_count,
                s_count,
                ingredients_combined
            ))

            batch_fts.append((
                stable_id,
                title_clean,
                ingredients_combined
            ))

            if len(batch_recipes) >= batch_size:
                cur.executemany("""
                    INSERT INTO recipes (id, source, raw_id, title, ingredients_json, instructions, picture_link, ingredient_count, step_count, ingredients_clean)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_recipes)
                cur.executemany("""
                    INSERT INTO recipes_fts (id, title, ingredients)
                    VALUES (?, ?, ?)
                """, batch_fts)
                conn.commit()
                batch_recipes.clear()
                batch_fts.clear()
                print(f"  Inserted {total_records} records...")

    if batch_recipes:
        cur.executemany("""
            INSERT INTO recipes (id, source, raw_id, title, ingredients_json, instructions, picture_link, ingredient_count, step_count, ingredients_clean)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_recipes)
        cur.executemany("""
            INSERT INTO recipes_fts (id, title, ingredients)
            VALUES (?, ?, ?)
        """, batch_fts)
        conn.commit()

    # Get final count
    cur.execute("SELECT count(*) FROM recipes")
    inserted_count = cur.fetchone()[0]
    conn.close()

    elapsed = time.time() - start_time
    print("\n--- Ingestion Complete ---")
    print(f"Total raw entries scanned: {total_records}")
    print(f"Skipped invalid/empty entries: {skipped_records}")
    print(f"Successfully indexed valid recipes: {inserted_count}")
    print(f"Database saved to {DB_PATH} in {elapsed:.2f} seconds.")

if __name__ == "__main__":
    ingest()
