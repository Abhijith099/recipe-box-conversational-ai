from engine import RecipeEngine

engine = RecipeEngine()

print("--- 1. Search Penne Pasta ---")
recipes, total = engine.search_recipes("penne pasta", limit=3)
print(f"Total penne pasta matches: {total}")
for r in recipes:
    print(f"  [{r['id']}] {r['title']}")

print("\n--- 2. Search Penne Pasta with Dairy Exclusion ---")
recipes_no_dairy, total_no_dairy = engine.search_recipes("penne pasta", exclusions=["dairy"], limit=3)
print(f"Total dairy-free penne pasta matches: {total_no_dairy}")
for r in recipes_no_dairy:
    print(f"  [{r['id']}] {r['title']} | Ingredients: {r['ingredients'][:2]}")

print("\n--- 3. Garlic & Onion Co-occurrence ---")
cooc = engine.analyze_ingredient_cooccurrence(["garlic", "onion"])
print(f"Count: {cooc['matching_count']} / {cooc['denominator']} ({cooc['percentage']}%)")

print("\n--- 4. Tomato Fewest Steps Ranking ---")
ranked = engine.rank_by_instruction_steps("tomato", order="ASC", limit=3)
print(f"Pool size: {ranked['pool_size']}")
for r in ranked['recipes']:
    print(f"  [{r['id']}] {r['title']} - Steps: {r['step_count']}")

print("\n--- 5. Dataset Ingredient Stats ---")
stats = engine.compute_ingredient_statistics()
print(f"Analyzed: {stats['analyzed_count']} | Avg: {stats['average_ingredients']} | Median: {stats['median_ingredients']}")

