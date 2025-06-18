import streamlit as st
import json
import os
import random
from dotenv import load_dotenv
from groq import Groq

# ----------------- Load Env & JSON -----------------
load_dotenv()
import streamlit as st
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# ------------------- PAGE CONFIG -------------------
st.set_page_config(page_title="🎨 Inventory Chatbor", layout="wide")



# ------------------- CUSTOM CSS -------------------
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
    color: white;
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div {
    color: white !important;
}
.css-1d391kg input[type="radio"]:checked + div {
    background: #ff7e5f !important;
    color: white !important;
    border-radius: 8px;
    font-weight: 700;
}
.css-1d391kg div[role="radio"]:hover {
    background-color: rgba(255, 126, 95, 0.3);
    border-radius: 8px;
}
.metric-container {
    background-color: white; 
    border-radius: 10px; 
    padding: 20px; 
    box-shadow: 0 0 10px rgb(0 0 0 / 0.1);
    margin-bottom: 15px;
}
h2, h3 {
    color: #2575fc;
}
footer {
    text-align: center;
    color: #999;
    padding: 10px;
}
header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)






# ------------------- HEADER -------------------


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
1. When the user asks about any stock, description, quantity, inventory ID, or similar, search the 'description' field and other relevant fields. If i give what is sulphur olive green like give description name, should give reponse by checking descriptions
2. Support user typos, misspellings, plurals, slang.
3. Return matching items in the following format — one item at a time — each field on a SEPARATE line, like this:

Example response:
Sure! Here are the matching inventory items I found:

• Inventory Item ID: 1234  
• Description: Bleach White  
• Quantity: 200  
• Stock Value: 5000  
• secqty: 50  

(Repeat for each matching item — max 50 items)

4. If no match is found, reply: "⚠️ No matching records found."

5. Do not guess or make up data.

Strictly follow this output format.
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
st.set_page_config(page_title="📦 JSON-Groq StockBot", layout="centered")
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
