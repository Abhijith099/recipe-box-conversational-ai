from matcher import RecipeMatcher

matcher = RecipeMatcher()

print("=== TEST 1: User has eggs, onions, tomatoes, rice | no peanuts | max 6 steps ===")
res1 = matcher.match_recipes(
    user_ingredients=["eggs", "onions", "tomatoes", "rice"],
    hard_exclusions=["peanuts", "peanut"],
    max_steps=6,
    limit=5
)

print(f"Eligible matches: {res1['eligible_matches_found']}")
for r in res1["results"]:
    print(f"\n[{r['id']}] {r['title']}")
    print(f"  Matched ({r['matched_count']}): {r['matched_ingredients']}")
    print(f"  Missing / Extra needed ({r['missing_count']}): {r['missing_ingredients'][:3]}...")
    print(f"  Steps: {r['step_count']}")
    print(f"  Explanation: {r['explanation']}")

print("\n\n=== TEST 2: Follow-up: Exclude eggs too ===")
res2 = matcher.match_recipes(
    user_ingredients=["eggs", "onions", "tomatoes", "rice"],
    hard_exclusions=["peanuts", "peanut", "eggs", "egg"],
    max_steps=6,
    limit=5
)

print(f"Eligible matches after excluding eggs: {res2['eligible_matches_found']}")
for r in res2["results"]:
    print(f"\n[{r['id']}] {r['title']}")
    print(f"  Matched ({r['matched_count']}): {r['matched_ingredients']}")
    print(f"  Missing / Extra needed ({r['missing_count']}): {r['missing_ingredients'][:3]}...")
    print(f"  Steps: {r['step_count']}")
    print(f"  Explanation: {r['explanation']}")

