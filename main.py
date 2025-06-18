import streamlit as st
import json
import os
import random
from dotenv import load_dotenv
from groq import Groq

# ----------------- Load Env & JSON -----------------
load_dotenv()
import streamlit as st
GROQ_API_KEY= st.secrets["GROQ_API_KEY"]

file_path = os.path.join(os.getcwd(),'cust_stock.json')
if not os.path.exists(file_path):
    st.error("❌ JSON file not found!")
    st.stop()

with open(file_path, 'r') as file:
    data = json.load(file)

# ----------------- Groq Setup -----------------
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

# ----------------- Streamlit Chat UI -----------------
st.set_page_config(page_title="📦 Chatbot", layout="centered")
st.title("🤖 Inventory Chatbot (Randomized with Groq + JSON)")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.chat_input("Ask about inventory...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    reply = groq_response(user_input, data)
    st.session_state.chat_history.append({"role": "assistant", "content": reply})

for chat in st.session_state.chat_history:
    if chat["role"] == "user":
        st.chat_message("user").markdown(chat["content"])
    else:
        st.chat_message("assistant").markdown(chat["content"])
