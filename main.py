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

Rules:

1. For Inventory Item Descriptions (e.g., "What is Sulphur Olive Green like?"):
Use fuzzy search in 'description' and reply like this (natural GPT chat form):

Sure! Here are the matching inventory items I found:

• Sulphur Olive Green with a quantity of 120, stock value 3000, and secqty 20.

• Olive Green Dye with a quantity of 80, stock value 2000, and secqty 10.

If ask for bleech list or kind of any listing show 10 records

(Up to 50 results like this.)

If no match:

⚠️ No matching records found.

2. For Category Questions (e.g., "How many categories are there?"):
There are two categories: Chemicals and Dyes.

3. For Item Count in Categories (e.g., "How many items in chemicals and dyes?"):
There are 3145 items in Chemicals and 1255 items in Dyes.

4. For Item Costing/High Value (e.g., "What is the high cost stock?"):
Use stock_value as cost and reply like:

The highest cost item is Sulphur Blue with a stock value of 50,000.

5. For Aging Queries (e.g., "What has aging 60?"):
If asked "Show items with aging 60", reply GPT-like:

There are some items that have aging 60. A few are given below:

Bleach White has aging 60 and quantity 45.

Olive Green Dye has aging 60 and quantity 120.

Sulphur Blue has aging 60 and quantity 75.

(Max 50 such records)

If none:

⚠️ No matching records found.

6. Strict No Guessing Rule:
If nothing matches, reply exactly:

⚠️ No matching records found.

7. Fuzzy Handling:
Supports misspelling, plurals, slang, typos via fuzzy matching.

8. Always GPT-style (conversational), never show labels like:
yaml
Copy
Edit
Inventory Item ID: 1234  
Description: Bleach White  
Quantity: 200
Instead, say:

Bleach White with a quantity of 200, stock value 5000, and secqty 50.

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

    # === Calculated Variables ===
    total_items = len(data)
    stock_value = sum(float(item.get('stockvalue', 0)) for item in data if item.get('stockvalue'))

    # --- Keyword Buckets ---
    stock_value_keywords = [
    "stock value", "stock val", "stockval", "stok value", "stck value", "inventory value", "invntory value", "inv value", "stock worth",
    "inventory worth", "worth of stock", "inventory money", "stock money", "stok mony", "total stock value", "total value", "tot value", "inv value",
    "stck val", "Stock Value", "STOCK VALUE", "inv val", "inven val", "value of stock", "cost of stock", "stck worth", "whats my stock worth",
    "valuation", "stock valuation", "inventory valuation", "stockprice", "stock price", "inventoryprice", "inventory price", "stock price value",
    "stock money value", "total inven value", "invntry value", "stockworth", "what stock worth", "stock rate", "inventory rate", "stok rate", "inv rate",
    "rate of stock", "inventory rate value", "asset value", "inventory asset value", "stock asset value", "total asset", "stock total value",
    "inventory total value", "stok total val", "stock total worth", "inventory total worth", "stok total worth", "stock price list", "inventory price list",
    "inven price", "list of inventory price", "inventory listing value", "stock listing value", "stock net value", "inventory net value", "net stock worth",
    "net inven worth", "stock gross value", "inventory gross value", "gross stock worth", "gross inven worth", "market value", "stock market value",
    "inv market value", "market stock worth", "market inven worth", "valuation stock", "valuation inventory", "worth stock", "worth inven", "stock total money",
    "inventory total money", "stock funds", "inventory funds", "inventory financials", "stock financials", "stock mony", "inven mony", "valuation mony",
    "val mony", "asset mony", "valuation fund", "invntry funds", "invntry mony", "stockfund", "inventoryfund", "stockfunds", "inventoryfunds", "stock price check",
    "inventory price check"
]

    stock_count_keywords = [
    "stock count", "stk count", "inventory count", "inv count", "total items", "total itm", "tot items", "how many items", "hw many items",
    "items count", "item count", "itm count", "number of items", "no of items", "how many itms", "items quantity", "items qty", "total qty",
    "inventory qty", "stock qty", "no. of items", "no items", "stock number", "inventory number", "num of stock", "number stock", "item stock count",
    "stock item count", "inv item count", "inv stock count", "how many stk", "stk itm count", "items total", "total inv items", "inv total items",
    "total stock items", "total inv stock", "inv stock itm", "count of items", "item counts", "itemscounts", "itmcounts", "stockcounts", "stock counts",
    "inv counts", "inventory counts", "total itm count", "how much items", "how mch items", "quantity of items", "qty items", "item qty", "inventoryqty",
    "stockqty", "totalstockcount", "invstockcount", "itmstockcount", "itmstockqty", "inventoryquantity", "stockquantity", "qtyofstock", "totalnumofitems",
    "totalnumberofitems", "stockitemqty", "invitemqty", "stockitmqty", "inventoryitmqty", "stock itms count", "inv itms count", "how many stock",
    "how many inventory", "stocknum", "inventorynum", "numstock", "numinventory", "totinvitems", "invqty", "stkqty", "stknum", "stkitmnum", "itmnum",
    "itmqty", "itmval", "totalitmqty", "inventoryitmcount", "stockitmcount", "itmcount", "countstock", "countinventory", "inventoryitm", "stockitm",
    "howmanyitms", "howmanystk", "howmanyinventory", "numitms", "numstk", "totalitms", "stkcount", "invcount", "itmcounts"
]

    top_items_keywords = [
    "top items", "top itm", "top 5", "top five", "top5", "best items", "bset items", "top 10", "top ten", "top 3", "top three", "most used items",
    "mostused items", "top-used items", "frequent items", "frequently used items", "most popular items", "popular items", "hot items", "best selling items",
    "hot selling items", "most common items", "trending items", "trend items", "best in stock", "top in stock", "most in stock", "highest stock",
    "top rated items", "top ranking items", "top ranking", "best ranking", "most selling", "top products", "top prod", "best products", "most used products",
    "top performing items", "high demand items", "top demanded", "high sale items", "top sale", "top sales", "top sale items", "high in demand",
    "fast selling", "fast moving items", "fast move items", "bestsellers", "top sellers", "best sellers", "best-selling", "most wanted items",
    "most searched items", "top search items", "frequently bought items", "fast buy items", "quick sale items", "hotstock", "topstock", "toplisting",
    "hotlisting", "top stocks", "in-demand items", "top preferred", "fav items", "favorite items", "top fav", "top preference", "preferred items",
    "faststock", "trendy items", "trendstock", "trenditems", "most required", "best picks", "hot picks", "most liked items", "liked items", "loved items",
    "most chosen", "chosen items", "chosenstock", "hit items", "top hit", "hottest items", "topfivestock", "topfivethings", "bestinlist", "mostpurchased",
    "most bought items", "popularstock", "popstock", "topselling", "mostpurchaseditems", "mostbuy", "top10stock", "mostdemanded"
]

    category_keywords = ["category", "major", "all majors", "types of items", "item types"]
    chemical_keywords = ["chemical", "chemicals", "chemical items","checmi","Chem","Chechi"]
    bleach_keywords = ["bleach", "bleaching agents","bleech","bleech list","bleach listing"]
    fabric_keywords = ["fabric", "fabrics", "fabric types", "textiles", "cloth types"]
    costing_keywords = ["costing", "cost", "amount", "total cost", "high cost", "high costing", "expensive item", "pricey item"]
    top_costing_keywords = ["top cost", "top costing", "top 5 cost", "top 5 costing", "high costing items", "expensive items", "top expensive", "high stock value", "high amount"]
    dye_keywords = ["dye", "dyes"]

    full_response = None  # default response

    # ----- Specific handling for Chemicals only -----
    if any(keyword in user_input_lower for keyword in chemical_keywords) and not any(keyword in user_input_lower for keyword in dye_keywords):
        chemical_items = [item for item in data if 'chemical' in item.get('major', '').lower() or 'chemical' in item.get('description', '').lower()]

        if chemical_items:
            top_chemical = max(chemical_items, key=lambda x: float(x.get('stockvalue', 0)))
            desc = top_chemical.get('description', 'Unknown')
            stock_val = top_chemical.get('stockvalue', '0')
            qty = top_chemical.get('qty', '0')
            major = top_chemical.get('major', 'Unknown')

            full_response = (
                f"🧪 The highest stock value chemical is {desc} with a stock value of {stock_val}, "
                f"quantity {qty}, categorized under {major}."
            )
        else:
            full_response = "❌ No chemical items found."

    # ----- Specific handling for Dyes only -----
    elif any(keyword in user_input_lower for keyword in dye_keywords) and not any(keyword in user_input_lower for keyword in chemical_keywords):
        dye_items = [item for item in data if 'dye' in item.get('major', '').lower() or 'dye' in item.get('description', '').lower()]

        if dye_items:
            top_dye = max(dye_items, key=lambda x: float(x.get('stockvalue', 0)))
            desc = top_dye.get('description', 'Unknown')
            stock_val = top_dye.get('stockvalue', '0')
            qty = top_dye.get('qty', '0')
            major = top_dye.get('major', 'Unknown')

            full_response = (
                f"🎨 The highest stock value dye is {desc} with a stock value of {stock_val}, "
                f"quantity {qty}, categorized under {major}."
            )
        else:
            full_response = "❌ No dye items found."

    # ----- Other Existing Handlers -----
    elif any(keyword in user_input_lower for keyword in stock_count_keywords):
        full_response = f"📦 There are currently **{total_items} items** in the inventory."

    elif any(keyword in user_input_lower for keyword in stock_value_keywords):
        full_response = f"💰 The total value of the entire inventory is **{stock_value}**."

    elif any(keyword in user_input_lower for keyword in top_costing_keywords):
        costly_items = sorted(
            [item for item in data if item.get('stockvalue')],
            key=lambda x: float(x.get('stockvalue', 0)), reverse=True
        )[:5]
        if costly_items:
            full_response = "🏆 Top 5 expensive items:\n\n"
            for idx, item in enumerate(costly_items, start=1):
                desc = item.get('description', 'Unknown')
                stock_val = item.get('stockvalue', '0')
                qty = item.get('qty', '0')
                major = item.get('major', 'Unknown')
                full_response += (
                    f"{idx}. {desc} has stock value {stock_val}, quantity {qty}, category {major}.\n"
                )
        else:
            full_response = "❌ No costly items found."

    elif any(keyword in user_input_lower for keyword in costing_keywords):
        costly_items = [item for item in data if item.get('stockvalue')]
        if costly_items:
            highest = max(costly_items, key=lambda x: float(x.get('stockvalue', 0)))
            desc = highest.get('description', 'Unknown')
            stock_val = highest.get('stockvalue', '0')
            qty = highest.get('qty', '0')
            major = highest.get('major', 'Unknown')
            full_response = (
                f"💎 The most expensive item is {desc} with a stock value of {stock_val}, quantity {qty}, categorized under {major}."
            )
        else:
            full_response = "❌ No costing data found."

    elif any(keyword in user_input_lower for keyword in top_items_keywords):
        full_response = "🏆 The following are the top 5 most frequently used items:\n\n"
        for idx, (desc, count) in enumerate(top_items, start=1):
            full_response += f"{idx}. {desc} has been used {count} times.\n"

    elif any(keyword in user_input_lower for keyword in category_keywords):
        full_response = "🗂️ The inventory includes items from the following categories:\n\n"
        for major, count in major_counts.items():
            full_response += f"- {major} with {count} items.\n"

    elif any(keyword in user_input_lower for keyword in bleach_keywords):
        bleach_items = [item for item in data if 'bleach' in item.get('description', '').lower()]
        count = len(bleach_items)
        full_response = f"🧼 There are {count} bleach-related items in the inventory.\n\n"
        if count > 0:
            full_response += "Here are some examples:\n\n"
            for idx, item in enumerate(bleach_items[:10], start=1):
                desc = item.get('description', 'Unknown')
                stock_val = item.get('stockvalue', '0')
                qty = item.get('qty', '0')
                major = item.get('major', 'Unknown')
                full_response += (
                    f"{idx}. {desc} has stock value {stock_val}, quantity {qty}, category {major}.\n"
                )
        else:
            full_response += "No bleach items found."

    elif any(keyword in user_input_lower for keyword in fabric_keywords):
        fabric_items = [item for item in data if 'fabric' in item.get('major', '').lower() or 'fabric' in item.get('description', '').lower()]
        count = len(fabric_items)
        full_response = f"🧵 There are {count} fabric-related items in the inventory.\n\n"
        if count > 0:
            full_response += "Here are some examples:\n\n"
            for idx, item in enumerate(fabric_items[:5], start=1):
                desc = item.get('description', 'Unknown')
                stock_val = item.get('stockvalue', '0')
                qty = item.get('qty', '0')
                major = item.get('major', 'Unknown')
                full_response += (
                    f"{idx}. {desc} has stock value {stock_val}, quantity {qty}, category {major}.\n"
                )
        else:
            full_response += "No fabric items found."

    else:
        # Fallback: Call Groq API
        full_response = groq_response(user_input, {"items": data})

    # Append to chat history
    st.session_state.chat_history.append({"query": user_input, "response": full_response})
    st.session_state.user_input = ""  # clear input



# ----------- Input Field: Always Fixed Below the Chat Box --------------
with input_container:
    st.text_input("Ask about any inventory item:", key='user_input', on_change=handle_input)
