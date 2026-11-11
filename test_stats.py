import sqlite3

conn = sqlite3.connect('recipes.db')
cur = conn.cursor()

# 1. Total valid recipes
cur.execute('SELECT COUNT(*) FROM recipes')
total = cur.fetchone()[0]

# 2. Recipes containing both garlic and onion
cur.execute("SELECT count(*) FROM recipes_fts WHERE ingredients MATCH 'garlic AND onion'")
garlic_onion_count = cur.fetchone()[0]
pct = (garlic_onion_count / total) * 100

print(f"Total recipes (denominator): {total}")
print(f"Recipes with garlic & onion: {garlic_onion_count} ({pct:.2f}%)")

# 3. Among recipes containing tomato, top 5 fewest instruction steps
cur.execute("""
    SELECT r.id, r.title, r.step_count, r.instructions
    FROM recipes r
    JOIN recipes_fts fts ON r.id = fts.id
    WHERE fts.ingredients MATCH 'tomato'
    ORDER BY r.step_count ASC, length(r.instructions) ASC
    LIMIT 5
""")
print("\nTop 5 recipes with tomato and fewest instruction steps:")
for row in cur.fetchall():
    print(f"- ID: {row[0]} | Title: {row[1]} | Steps: {row[2]}")

