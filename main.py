import streamlit as st
import json
import re
from difflib import get_close_matches

# ----------------- File Path -----------------
file_path = os.path.join(os.getcwd(),'cust_stock.json')

@st.cache_data
if not os.path.exists(file_path):
    st.error("❌ JSON file not found!")
    st.stop()

with open(file_path, 'r') as file:
    data = json.load(file)
st.set_page_config(layout="wide")
# ----------------- Load JSON Data -----------------



# ----------------- NLP Functions -----------------
def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.split()

def fuzzy_token_match(query_tokens, item_tokens):
    score = 0
    for q_token in query_tokens:
        match = get_close_matches(q_token, item_tokens, n=1, cutoff=0.7)
        if match:
            score += 1
    return score

def search_all_matching_items(query, data, min_score=1):
    query_tokens = preprocess(query)
    matched_items = []

    for item in data:
        combined_text = f"{item.get('description', '')} {item.get('major', '')} {item.get('fabtype', '')}"
        item_tokens = preprocess(combined_text)

        score = fuzzy_token_match(query_tokens, item_tokens)
        if score >= min_score:
            matched_items.append((item, score))

    matched_items.sort(key=lambda x: x[1], reverse=True)
    return matched_items

def detect_requested_fields(query):
    possible_fields = {
        "inventory id": "inventory_item_id",
        "description": "description",
        "major": "major",
        "fab type": "fabtype",
        "qty": "qty",
        "quantity": "qty",
        "stock value": "stockvalue",
        "aging": ["aging_60", "aging_90", "aging_180", "aging_180plus"]
    }
    detected = []

    for key, val in possible_fields.items():
        if key in query.lower():
            detected.append(val)
    return detected

def format_gpt_style_response(item, requested_fields):
    response = "Here are the details:\n\n"

    if requested_fields:
        for field in requested_fields:
            if isinstance(field, list):
                response += "**Aging Info:**\n"
                for subfield in field:
                    response += f"- {subfield.replace('_', ' ').title()}: {item.get(subfield, 'N/A')}\n"
            else:
                response += f"- **{field.replace('_', ' ').title()}**: {item.get(field, 'N/A')}\n"
    else:
        response += f"- **Inventory ID**: {item.get('inventory_item_id', 'N/A')}\n"
        response += f"- **Description**: {item.get('description', 'N/A')}\n"
        response += f"- **Major**: {item.get('major', 'N/A')}\n"
        response += f"- **Fab Type**: {item.get('fabtype', 'N/A')}\n"
        response += f"- **Qty**: {item.get('qty', 'N/A')}\n"
        response += f"- **Stock Value**: {item.get('stockvalue', 'N/A')}\n"

    return response

# ----------------- Streamlit Frontend -----------------


if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

st.sidebar.title("💬 Chat History")
for idx, hist in enumerate(st.session_state.chat_history):
    st.sidebar.write(f"{idx+1}. {hist['query']}")

st.title("📦 Stock Inventory Chatbot (GPT-Style)")
st.write("---")

for hist in st.session_state.chat_history:
    st.markdown(f"**You:** {hist['query']}")
    st.markdown(hist['response'])

user_input = st.text_input("Ask about any inventory item:")

if user_input:
    matched_results = search_all_matching_items(user_input, data)
    requested_fields = detect_requested_fields(user_input)

    if matched_results:
        items_per_page = 10
        total_pages = len(matched_results) // items_per_page + (1 if len(matched_results) % items_per_page > 0 else 0)
        page = st.session_state.get('page', 1)

        

        st.session_state.page = page

        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = matched_results[start_idx:end_idx]

        full_response = ""
        for item, _ in page_items:
            full_response += format_gpt_style_response(item, requested_fields) + "\n"

        st.markdown(full_response)
        page_nums = ' '.join([f"{i+1}" for i in range(total_pages)])
        col1, col2, col3 = st.columns([1,2,1])

        with col1:
            if st.button('⬅️ Prev') and page > 1:
                page -= 1

        with col3:
            if st.button('Next ➡️') and page < total_pages:
                page += 1

        st.session_state.chat_history.append({"query": user_input, "response": full_response})
    else:
        st.error("❌ No matching items found.")
