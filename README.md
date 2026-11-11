# Recipe Box Conversational AI Chatbot (Task 1, Task 2 & Task 3)

A production-grade, grounded conversational AI assistant that searches, analyzes, matches, and adapts recipes from the **Recipe Box** dataset (~125,000 recipes) with **strict data grounding**, reproducible statistical calculations, explainable ingredient matching, evidence-based ingredient substitution, and multi-turn conversational context.

---

## 🌟 Capabilities & Requirements Addressed

### Task 1: Recipe Search & Factual Q&A
1. **Zero Hallucination / Programmatic Calculations:**
   - Statistical queries (counts, percentages, medians, averages) are calculated programmatically on the verified dataset rather than guessed by an LLM.
   - Denominator transparently reported: **124,595** validated recipes (569 empty/unparseable raw entries cleanly excluded).
   - Co-occurrence example: Recipes containing both garlic & onion = **20,245 / 124,595 (16.25%)**.
2. **Full-Text & Constraint Search:**
   - Sub-15ms search across titles and ingredients powered by SQLite FTS5 (Full-Text Search with Porter stemming).
   - Retains stable recipe IDs (e.g. `fn_lbdoJWX6HAMrTwmYjkFPyxu/lqR/lLO`).
   - Dietary restriction filtering (e.g. "no dairy", "no gluten", "no nuts").
3. **Multi-Turn Context & Refinement:**
   - Active search query and active restrictions persist across turns (e.g. 495 penne pasta recipes $\to$ 101 dairy-free penne pasta recipes).
4. **Transparent Attribute Grounding:**
   - Explicitly refuses to fabricate unavailable attributes such as cooking times or caloric/nutritional data, explaining the dataset schema boundaries to the user.
5. **Instruction Step-Counting Rule:**
   - Defined rule: splits on substantive paragraph breaks and sentence ending punctuation followed by capital letters/numbers.
   - Tomato fewest-steps ranking: provides exact recipe IDs, titles, step counts, and text previews.

### Task 2: Ingredient-Based Recipe Matching
1. **Explainable Pantry Matching & Scoring:**
   - Matches candidate recipes against user-provided ingredients (e.g. `eggs, onions, tomatoes, rice`).
   - Deterministic, explainable scoring:
     $$\text{Score} = (\text{Matched Count} \times 100) - (\text{Missing Ingredients} \times 5) - (\text{Steps} \times 2)$$
   - Transparently displays for every recipe:
     - **Matched ingredients** (which user ingredients are used)
     - **Additional / missing ingredients needed**
     - **Step count**
     - **Explainable ranking reason**
2. **Strict Hard Constraints:**
   - Evaluates hard constraints strictly (e.g. `exclude peanuts`, `max_steps <= 6`). Never relaxes constraints silently.
   - If no recipes qualify, reports zero matches and surfaces closest near-matches explicitly labeled with their violation (e.g. *Violation: Exceeds max steps (4 > 0)*).
3. **Multi-Turn Ingredient Refinement:**
   - Seamlessly handles follow-ups like *"Exclude eggs too"*, recalculating eligible recipes and re-ranking immediately.
4. **Quantity Handling Disclosure:**
   - When quantities are supplied (e.g. `2 eggs, 1 cup rice`), states clearly that matching is performed at the ingredient name level because the dataset contains free-form text without standardized unit conversion.

### Task 3: Evidence-Based Ingredient Substitution
1. **Culinary Role-Based Adaptation:**
   - Evaluates the structural and culinary role of the ingredient to be replaced (e.g. eggs for binding/leavening; heavy cream for fat/viscosity/richness; butter for fat/flakiness).
2. **Local Dataset Evidence & Recipe ID Citations:**
   - Searches the local 124,595 recipe database for similar dishes using the substitute without the excluded ingredient (e.g. finding vegan zucchini banana bread recipes that use applesauce without egg).
   - Cites exact Recipe IDs (e.g. `ar_.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy`) as local proof.
   - Explicitly distinguishes **Direct Evidence** (same dish type) from **Indirect Evidence** (cross-recipe patterns).
3. **Complete Recipe Rewriting:**
   - Generates an **updated ingredient list** with calculated replacement ratios (e.g. *1/4 cup unsweetened applesauce per egg*).
   - Generates **revised cooking instructions** adjusting preparation steps.
4. **Predicted Trade-offs & Safety Disclaimers:**
   - Clearly explains expected impacts on crumb density, moisture retention, and flavor.
   - Distinguishes predicted trade-offs from verified outcomes.
   - Always attaches an **allergen & medical safety disclaimer**: recipe title matching in a dataset does not constitute certified clinical allergen safety.
5. **Handling Inadequate Evidence & Honest Refusal:**
   - If an ingredient lacks grounded substitution precedent in the dataset (e.g. *saffron*), the system refuses to fabricate an ungrounded guess, upholding strict grounding principles.

---

## 📂 Project Architecture

```
├── dataset/                    # Original Recipe Box JSON files (ar, epi, fn)
├── ingest.py                   # Ingestion script: cleans noise, indexes into SQLite FTS5
├── recipes.db                  # Pre-indexed SQLite database (124,595 recipes)
├── engine.py                   # Task 1: Grounded search & analytical statistics engine
├── matcher.py                  # Task 2: Ingredient matching, hard constraints & scoring
├── adapter.py                  # Task 3: Evidence-based substitution, role mapping & recipe rewriting
├── chat.py                     # Unified conversational state manager & intent router
├── cli.py                      # Interactive terminal chatbot
├── app.py                      # Streamlit visual web UI
├── test_suite.py               # Automated unit test suite (11 comprehensive tests)
├── evaluate.py                 # Reproducible 5-conversation benchmark & evaluation set
└── README.md                   # Documentation & Interview Guide
```

---

## 🚀 How to Run

### 1. Run the Interactive CLI (Fastest & Simplest)
```bash
python cli.py
```

### 2. Run the Streamlit Web UI (Visual Presentation)
```bash
streamlit run app.py
```

### 3. Run the Automated Test Suite (All 11 Unit Tests)
```bash
python test_suite.py
```

### 4. Run the Reproducible Evaluation Suite (5 Benchmark Conversations)
```bash
python evaluate.py
```

---

## 📊 Evaluation & Edge Cases Benchmark

| Test Conversation | Tested Domain | Expected Grounded Output | Ungrounded One-Shot LLM Failure Mode |
|---|---|---|---|
| **Conv 1: Search & Refinement** | Task 1 Multi-turn | Searches `penne pasta` (495 hits) $\to$ refines with `I cannot have dairy` (101 hits). | Hallucinates recipes or drops search query context across turns. |
| **Conv 2: Aggregate Statistics** | Task 1 Reproducible Math | Garlic + Onion co-occurrence: **20,245 / 124,595 recipes (16.25%)**. | Guesses random percentages (~15-30%) and invents fake dataset totals. |
| **Conv 3: Pantry Matching** | Task 2 Explainable Scoring | Eggs, onions, tomatoes, rice $\to$ top ranked by matched ingredients $\to$ follow-up *"Exclude eggs too"* updates results. | Recommends recipes requiring 10+ unmentioned ingredients without explainable ranking. |
| **Conv 4: Impossible Constraint** | Task 2 Hard Strictness | Request with `max_steps <= 0` returns **0 eligible matches** and shows closest violated alternatives labeled with violation reason. | Silently ignores the hard step limit or invents raw non-existent recipes. |
| **Conv 5A: Grounded Substitution** | Task 3 Recipe Adaptation | Removes eggs from banana bread $\to$ replaces with applesauce, cites local Recipe IDs (`ar_.GLWQH0bkiU3fRzwc68PqTCqGHJj2fy`), rewrites instructions and ingredients. | Suggests replacements without local database evidence or Recipe ID citations. |
| **Conv 5B: Inadequate Evidence** | Task 3 Honest Refusal | Replaces unsupported ingredient (`saffron`) $\to$ refuses to fabricate ungrounded advice. | Hallucinates arbitrary chemical or spice substitutions without dataset grounding. |
| **Unavailable Attributes** | Task 1 Boundaries | Querying calories/cook time returns clear disclaimer that dataset lacks nutrition/time fields. | Confidently fabricates fake calories (e.g. "350 kcal") and cooking times ("30 mins"). |

---

## 💬 Interview Walkthrough & Defense

### Q1: Why integrate Task 1, Task 2, and Task 3 into a single unified architecture?
> *"The objective of the assignment was to build a single conversational assistant that can search, analyze, match, and adapt recipes while retaining context across turns. A user starts by searching for recipes, refines by dietary constraints, switches to pantry matching based on available ingredients ('I have eggs, onions, tomatoes, and rice'), and adapts an existing recipe by substituting restricted ingredients ('Take this banana bread recipe and remove eggs'). A single unified session manager backed by a shared SQLite FTS5 database enables seamless context retention across all tasks without duplicate data storage."*

### Q2: How does the ingredient-matching scoring algorithm work in Task 2?
> *"Matching is grounded and explainable: We use SQLite FTS5 to retrieve candidates containing at least one user ingredient. Then we perform set intersection and difference against normalized ingredient lists:
> 1. Hard constraints (exclusions like peanuts, max steps $\le 6$) are applied strictly; violated recipes are filtered out immediately.
> 2. Remaining eligible candidates are scored by prioritizing maximum matched ingredients first, then minimizing extra/missing ingredients needed from the store, and finally minimizing instruction steps.
> Every returned recipe explicitly shows its matched ingredients, missing ingredients, step count, and ranking justification."*

### Q3: How do you handle ingredient quantities in Task 2?
> *"The Recipe Box dataset records ingredients as unstructured natural language lines (e.g., '1 pinch salt', '2 (10.75 ounce) cans soup'). Because the dataset lacks standardized volume-to-weight conversions, claiming exact quantity sufficiency would be a hallucination. In compliance with the prompt requirements, the matcher performs a name-level match and outputs a transparent disclosure notice stating that quantity sufficiency was not verified."*

### Q4: How does Task 3 satisfy the requirement for local evidence and recipe citations?
> *"Instead of relying on an LLM to hallucinate substitutions, `adapter.py` identifies the ingredient's culinary role (e.g. egg is a binder/leavener, cream provides fat and viscosity). It then executes a targeted SQL query against our 124,595 recipe database to find real peer recipes in the dataset that use the substitute without the excluded item (e.g. banana breads using applesauce without eggs) and cites their exact `Recipe ID`s. It rewrites both the ingredient list and the instructions, details taste/texture trade-offs, and adds an explicit allergen safety disclaimer."*
