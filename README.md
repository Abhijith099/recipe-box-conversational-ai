# Recipe Box Conversational AI Chatbot (Task 1, Task 2 & Task 3)

A production-grade, grounded conversational AI assistant that searches, analyzes, matches, and adapts recipes from the **Recipe Box** dataset (~125,000 recipes) with **strict data grounding**, reproducible statistical calculations, explainable ingredient matching, evidence-based ingredient substitution, and multi-turn conversational context.

---

##  Capabilities & Requirements Addressed

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

##  Project Architecture

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
## How to generate the SQLite database

The repository ships the raw recipe JSON files (≈ 200 MB total).  
The SQLite file `recipes.db` is **not** version‑controlled because it exceeds GitHub’s 100 MB limit.  

To create it locally:

```bash
# 1️⃣ Install the runtime dependencies (once)
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt   # includes any needed extras (e.g. tqdm)

# 2️⃣ Build the database
python ingest.py
```

The script will produce `recipes.db` in the project root – ready for the chatbot to use.



##  How to Run

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

##  Evaluation & Edge Cases Benchmark

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

## Architecture & Design Decisions

### 1. Unified Session & Database Architecture (Tasks 1–3)
Rather than splitting tasks into isolated scripts, the application uses a single unified session manager backed by a shared SQLite FTS5 database. This allows users to flow naturally across tasks—starting with keyword search, refining by dietary constraints, switching to pantry matching, and adapting recipes—while retaining full conversational context without duplicate data storage.

### 2. Explainable Scoring & Constraint Enforcement (Task 2)
To ensure recommendations are transparent and defensible, Task 2 avoids black-box LLM scoring in favor of deterministic set math:
- **Hard Constraints:** Dietary exclusions (e.g., peanuts) and step limits are enforced strictly before scoring. Violating recipes are filtered out immediately.
- **Deterministic Scoring Formula:** 
  $$\text{Score} = (\text{Matched Count} \times 100) - (\text{Missing Ingredients} \times 5) - (\text{Steps} \times 2)$$
- **Full Transparency:** Every returned recipe explicitly details its matched ingredients, missing items, step count, and ranking justification.

### 3. Handling Unstructured Quantity Data (Task 2)
The raw Recipe Box dataset records ingredients as free-form natural language strings (e.g., `"1 pinch salt"`, `"2 cans soup"`). Because standardized volume-to-weight conversions are absent, the matcher performs a name-level match and outputs an explicit disclosure notice confirming that exact quantity sufficiency was not mathematically verified, preventing ungrounded claims.

### 4. Grounded Substitution & Local Evidence (Task 3)
To eliminate LLM hallucination during ingredient substitution, `adapter.py` maps ingredients to structural culinary roles (e.g., eggs as binders, heavy cream for viscosity) and queries the local 124,595-recipe database. It retrieves verified peer recipes using the substitute without the excluded item, cites their exact `Recipe ID`s as **Direct** or **Indirect** evidence, rewrites instructions and ingredients, and attaches clinical safety disclaimers.


## Engineering Workflow & Tooling
This project was built leveraging a modern AI-assisted software development workflow:
* **Core Architecture & Rapid Prototyping:** Structured, modularized, and implemented using **Claude Code** and **Cursor** to accelerate full-stack iteration, database indexing logic, and component organization.
* **Debugging & Edge-Case Verification:** Complex SQLite FTS5 query constraints, ingredient matching algorithms, and unit test suites were rigorously debugged and validated with AI assistance.
* **Full Ownership & Code Review:** Every line of code, database schema decision, and algorithm was thoroughly reviewed, tested, and integrated by the author to ensure complete ownership during technical interview walkthroughs.