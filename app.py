"""
Streamlit Web UI for Recipe Box Conversational Chatbot.
Run with: streamlit run app.py
"""
#describes what is inthe file 

import streamlit as st
from chat import ChatSession

st.set_page_config(
    page_title="Recipe Box Grounded AI Chatbot",
    page_icon="🍲",
    layout="wide"
)

# Initialize session state for chatbot
if "chat_session" not in st.session_state:
    st.session_state.chat_session = ChatSession()
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar controls and dataset stats
with st.sidebar:
    st.title(" Recipe Box Chatbot")
    st.markdown("**Grounded Search, Analytics & Ingredient Matching**")
    st.markdown("---")
    
    st.markdown("###  Dataset Overview")
    st.markdown("- **Sources:** Allrecipes, Epicurious, Food Network")
    st.markdown("- **Validated Records:** 124,595 recipes")
    st.markdown("- **Storage:** SQLite FTS5 Full-Text Search")
    st.markdown("---")
    
    st.markdown("###  Active Session State")
    sess = st.session_state.chat_session
    st.markdown(f"**Mode:** `{sess.mode.upper()}`")
    if sess.mode == "matching":
        pantry = ", ".join(sess.active_pantry_ingredients) or "*None*"
        st.markdown(f"**Pantry Ingredients:** {pantry}")
        if sess.active_max_steps:
            st.markdown(f"**Max Steps:** {sess.active_max_steps}")
    else:
        st.markdown(f"**Active Query:** {sess.active_query or '*None*'}")

    exclusions = ", ".join(sess.active_exclusions) or "*None*"
    st.markdown(f"**Active Exclusions:** {exclusions}")
    st.markdown(f"**Cached Results:** {len(sess.last_results)} items")
    st.markdown("---")

    if st.button(" Reset Conversation", use_container_width=True):
        st.session_state.chat_session.reset_state()
        st.session_state.messages = []
        st.rerun()

    st.markdown("###  Example Prompts")
    st.markdown("**Task 3: Recipe Adaptation (Evidence-Based)**")
    st.markdown("- *Take this banana bread recipe and remove eggs*")
    st.markdown("- *Replace cream in this pasta recipe without dairy*")
    st.markdown("---")
    st.markdown("**Task 2: Ingredient Matching**")
    st.markdown("- *I have eggs, onions, tomatoes, and rice. Suggest five recipes using as many of these as possible, with no peanuts and at most six instruction steps.*")
    st.markdown("- *Exclude eggs too*")
    st.markdown("- *Show recipe 1*")
    st.markdown("---")
    st.markdown("**Task 1: Search & Analytics**")
    st.markdown("- *Find a penne pasta recipe*")
    st.markdown("- *I cannot have dairy*")
    st.markdown("- *How many recipes contain both garlic and onion?*")
    st.markdown("- *Among recipes with tomato, which five have fewest steps?*")
    st.markdown("- *What is the average number of ingredients?*")
    st.markdown("- *How many calories are in this recipe?*")

# Main Chat Header
st.header("Recipe Search, Analytics, Matching & Adaptation")
st.caption("Grounded in 124,595 verified recipes. Deterministic math, local dataset evidence, zero hallucination, and explainable scoring.")

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Ask a question, enter pantry ingredients, or refine your search :)..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate grounded response
    response = st.session_state.chat_session.respond(prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.markdown(response)
