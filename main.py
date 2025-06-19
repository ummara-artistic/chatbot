import streamlit as st
import json
import re
from difflib import get_close_matches
import os
from dotenv import load_dotenv
import os
import random
from dotenv import load_dotenv
from groq import Groq
from collections import Counter

# ----------------- File Path -----------------
file_path = os.path.join(os.getcwd(),'cust_stock.json')
if not os.path.exists(file_path):
    st.error("❌ JSON file not found!")
    st.stop()

st.set_page_config(layout="wide")

load_dotenv()
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
# ----------------- Load JSON Data -----------------
@st.cache_data
def load_data(path):
    with open(path, 'r') as file:
        data = json.load(file)
    return data['items']

data = load_data(file_path)

# ----------------- Inventory Statistics -----------------
def get_inventory_statistics(data):
    total_items = len(data)
    majors = [item.get('major', 'Unknown') for item in data]
    major_counts = Counter(majors)
    return total_items, major_counts

def get_top_items(data, top_n=5):
    desc_counts = Counter([item.get('description', 'Unknown') for item in data])
    return desc_counts.most_common(top_n)

total_items, major_counts = get_inventory_statistics(data)
top_items = get_top_items(data)

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



# ----------------- Streamlit App -----------------

# ----------- Session State --------------
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'user_input' not in st.session_state:
    st.session_state.user_input = ""

# ----------- Sidebar --------------
st.sidebar.title("💬 Chat History")
for idx, hist in enumerate(st.session_state.chat_history):
    st.sidebar.write(f"{idx+1}. {hist['query']}")

st.title("📦 Stock Inventory Chatbot ")
st.write("---")

# ----------- Main Layout: Chat Above (Scrollable), Input Fixed Below --------------

input_container = st.container()



for chat in reversed(st.session_state.chat_history):
        # User message (right bubble)
        st.markdown(
            f"<div style='text-align: right; background-color: #D1E7DD; padding:10px; border-radius:10px; "
            f"margin:5px 0 5px auto; width: fit-content; max-width: 80%;'>{chat['query']}</div>",
            unsafe_allow_html=True
        )
        # Bot message (left bubble)
        st.markdown(
            f"<div style='text-align: left; background-color: #F0F0F0; padding:10px; border-radius:10px; "
            f"margin:5px auto 5px 0; width: fit-content; max-width: 80%; overflow-x: auto;'>{chat['response']}</div>",
            unsafe_allow_html=True
        )

st.markdown("</div>", unsafe_allow_html=True)



def groq_response(query, json_data):
    try:
        client = Groq(api_key=GROQ_API_KEY)

        all_items = json_data.get('items', [])

        # Randomly pick up to 100 unique items
        sampled_items = random.sample(all_items, min(len(all_items), 100))

        json_text = json.dumps(sampled_items, indent=2)

        system_prompt = f"""
You are an Inventory Assistant.

Using ONLY this JSON data:

{json_text}

Rules:

When the user asks about any stock, description, quantity, inventory ID, or similar, search the 'description' field and other relevant fields.

Example: If the user asks "What is Sulphur Olive Green like?", search the description field and provide the matching item details accordingly.

Support user typos, misspellings, plurals, and slang to find the closest match (use fuzzy matching if needed).

If the user asks about categories or total categories (e.g., "How many categories are there?", "Tell me the categories", "Total categories?"), reply with:

There are two categories: Chemicals and Dyes.
If the user asks about the number of items in each category (e.g., "How many items in chemicals and dyes?", "Number of items in each category?"), reply with:


There are 3145 items in Chemicals and 1255 items in Dyes. just write this no other info
When matching inventory items are found, return results in this exact format — one item at a time — each field on a SEPARATE line:

Example Response:

Sure! Here are the matching inventory items I found:

• Inventory Item ID: 1234  
• Description: Bleach White  
• Quantity: 200  
• Stock Value: 5000  
• secqty: 50  
(Repeat this for each matching item, up to 50 items max.)

If no match is found, reply strictly with:

⚠️ No matching records found.
Do not guess, assume, or fabricate any data not explicitly present. Only respond based on the above instructions.
"""

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.2,
            max_completion_tokens=2048,
            top_p=1,
            stream=False,
        )
        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ Groq API Error: {e}"



# ----------- Handle Input via Callback --------------
def handle_input():
    user_input = st.session_state.user_input.strip()
    if user_input == "":
        return

    user_input_lower = user_input.lower()
    full_response = ""

    # --- Keyword Buckets ---
    stock_value_keywords = ["stock value", "inventory value", "total stock value"]
    stock_count_keywords = ["stock count", "inventory count", "total items", "how many items", "items count", "number of items"]
    top_items_keywords = ["top items", "top 5", "best items", "most used items"]
    category_keywords = ["category", "major", "all majors", "types of items", "item types"]
    chemical_keywords = ["chemical", "chemicals", "chemical items"]
    bleach_keywords = ["bleach", "bleaching agents"]
    fabric_keywords = ["fabric", "fabrics", "fabric types", "textiles", "cloth types"]

    # ---------------- GPT-Style Responses ----------------

    if any(keyword in user_input_lower for keyword in stock_count_keywords):
        full_response = f"📦 **Inventory Summary:**\n\n"
        full_response += f"✅ Total items currently in inventory: **{total_items}**\n"

    elif any(keyword in user_input_lower for keyword in top_items_keywords):
        full_response = "🏆 **Top 5 Inventory Items:**\n\n"
        for desc, count in top_items:
            full_response += f"- {desc}: **{count} times used**\n"

    elif any(keyword in user_input_lower for keyword in category_keywords):
        full_response = "🗂️ **Inventory Categories (Majors):**\n\n"
        for major, count in major_counts.items():
            full_response += f"- **{major}**: {count} items\n"

    elif any(keyword in user_input_lower for keyword in chemical_keywords):
        chemical_items = [item for item in data if 'chemical' in item.get('major', '').lower() or 'chemical' in item.get('description', '').lower()]
        chemical_count = len(chemical_items)

        full_response = f"🧪 **Chemical Items Overview:**\n\n"
        full_response += f"✅ Total Chemicals in Inventory: **{chemical_count}**\n"

        if chemical_count > 0:
            example_items = chemical_items[:5]
            full_response += "\n📝 **Sample Chemical Items:**\n"
            for chem in example_items:
                full_response += f"- {chem.get('description', 'No Description')} _(Major: {chem.get('major', 'N/A')})_\n"

    elif any(keyword in user_input_lower for keyword in bleach_keywords):
        bleach_items = [item for item in data if 'bleach' in item.get('description', '').lower()]
        bleach_count = len(bleach_items)

        full_response = f"🧼 **Bleach-Related Items:**\n\n"
        full_response += f"✅ Total Bleach Items: **{bleach_count}**\n"

        if bleach_count > 0:
            example_items = bleach_items[:5]
            full_response += "\n📝 **Sample Bleach Items:**\n"
            for bleach in example_items:
                full_response += f"- {bleach.get('description', 'No Description')} _(Major: {bleach.get('major', 'N/A')})_\n"

    elif any(keyword in user_input_lower for keyword in fabric_keywords):
        fabric_items = [item for item in data if 'fabric' in item.get('major', '').lower() or 'fabric' in item.get('description', '').lower()]
        fabric_count = len(fabric_items)

        full_response = f"🧵 **Fabric-Related Items:**\n\n"
        full_response += f"✅ Total Fabric Items: **{fabric_count}**\n"

        if fabric_count > 0:
            example_items = fabric_items[:5]
            full_response += "\n📝 **Sample Fabric Items:**\n"
            for fabric in example_items:
                full_response += f"- {fabric.get('description', 'No Description')} _(Major: {fabric.get('major', 'N/A')})_\n"

    else:
        # ---- Fallback: Try internal search first ----
        matched_results = search_all_matching_items(user_input, data)
        requested_fields = detect_requested_fields(user_input)

        if matched_results:
            items_per_page = 10
            total_pages = len(matched_results) // items_per_page + (1 if len(matched_results) % items_per_page > 0 else 0)
            page = st.session_state.get('page', 1)

            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_items = matched_results[start_idx:end_idx]

            full_response = f"🔍 **I found {len(matched_results)} item(s) matching your query.**\n\n"
            full_response += "📝 **Here are some sample items from the inventory:**\n\n"

            for item, _ in page_items[:5]:  # Show only first 5
                inventory_id = item.get('inventory_item_id', 'N/A')
                description = item.get('description', 'No Description')
                major = item.get('major', 'N/A')
                fab_type = item.get('fabtype', 'N/A')
                qty = item.get('qty', 'N/A')
                stock_value = item.get('stockvalue', 'N/A')

                full_response += (
                    f"• **Inventory ID:** {inventory_id}\n"
                    f"  - **Description:** {description}\n"
                    f"  - **Major:** {major}\n"
                    f"  - **Fab Type:** {fab_type}\n"
                    f"  - **Quantity:** {qty}\n"
                    f"  - **Stock Value:** {stock_value}\n\n"
                )
        else:
            # ---- If no internal match: Call Groq ----
            full_response = "🤖 **Let me check deeper...**\n\n"
            full_response += groq_response(user_input, {"items": data})


    # Append the response to chat history
    st.session_state.chat_history.append({"query": user_input, "response": full_response})
    st.session_state.user_input = ""  # Clear input after handling


# ----------- Input Field: Always Fixed Below the Chat Box --------------
with input_container:
    st.text_input("Ask about any inventory item:", key='user_input', on_change=handle_input)
