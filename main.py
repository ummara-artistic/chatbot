import streamlit as st
import json
import re
import os
import requests
from datetime import datetime
from difflib import get_close_matches
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go



import os

from groq import Groq

# ----------------- Groq API Config -----------------

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'


import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')



def groq_fallback(query):
    try:
        client = Groq(api_key=GROQ_API_KEY)  # Correctly pass API key here

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "You are a helpful stock inventory assistant."},
                {"role": "user", "content": query}
            ],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,  # For fallback, stream=False is better in Streamlit
            stop=None,
        )

        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ Groq API Error: {e}"



# ----------------- JSON Loading -----------------
file_path = os.path.join(os.getcwd(),'cust_stock.json')
if not os.path.exists(file_path):
    st.error("❌ JSON file not found!")
    st.stop()

with open(file_path, 'r') as file:
    data = json.load(file)

qa_file_path = os.path.join(os.getcwd(),'new_qa_dataset.json')
qa_data = []
if os.path.exists(qa_file_path):
    with open(qa_file_path, 'r') as qa_file:
        loaded_qa = json.load(qa_file)
        if isinstance(loaded_qa, dict):
            qa_data = loaded_qa.get('qa_pairs', [])
        elif isinstance(loaded_qa, list):
            qa_data = loaded_qa
else:
    st.warning("⚠️ Q&A file not found.")

field_keywords = {
    'organization_id': ['organization', 'org', 'orgid', 'org id'],
    'prefix': ['prefix', 'code', 'prfx', 'prefixx'],
    'txndate': ['date', 'transaction', 'txn', 'dat', 'dt'],
    'major': ['major', 'category', 'major cat', 'cat', 'catgry'],
    'inventory_item_id': ['item', 'itemid', 'inventory', 'inv', 'invitem', 'id', 'iid'],
    'description': ['description', 'desc', 'descrip', 'desp', 'des', 'des kya'],
    'uom': ['unit', 'uom', 'measure', 'unit?', 'uom pls'],
    'qty': ['quantity', 'qty', 'amount', 'qnt', 'qnty', 'stck'],
    'stockvalue': ['value', 'stockvalue', 'worth', 'vlue', 'val'],
    'aging_60': ['aging60', '60days'],
    'aging_90': ['aging90', '90days'],
    'aging_180': ['aging180', '180days'],
    'aging_180plus': ['aging180plus', 'morethan180'],
    'fabtype': ['fabtype', 'fabric', 'fabric type', 'fab', 'fabtyp'],
    'salesperson': ['sales', 'salesperson', 'rep', 'salesman'],
    'brand': ['brand'],
    'moi': ['moi', 'mo', 'mo?'],
    'io': ['io'],
    'lottype': ['lottype', 'lot', 'type'],
    'secqty': ['secqty', 'secondqty', 'sec qty']
}

common_queries = [
    'qty', 'stock', 'val', 'fab', 'aging', 'uom', 'inv id', 'prefix', 'local', 'imported',
    'fabtype', 'salesman', 'org id', 'major cat', 'inventory', 'bleach', 'value', 'desc',
    'date', 'txndate', 'sec qty', 'mo', 'moi', 'io', 'available', 'position', 'lot', 'type',
    'story', 'highlights', 'brand', 'top', 'best', 'max', 'highest', 'list', 'top selling',
    'top item', 'inven', 'descrip', 'description', 'invntory', 'major', 'catgry', 'aging60'
]

def preprocess(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.split()

def detect_field(tokens):
    for token in tokens:
        for field, keywords in field_keywords.items():
            if token in keywords:
                return field
    return None

def detect_condition(tokens):
    conditions = {
        'equals': ['equals', 'is', 'equal', 'match'],
        'contains': ['contains', 'has', 'with', 'include'],
        'greater': ['greater', 'more', 'above', 'over'],
        'less': ['less', 'below', 'under']
    }
    for token in tokens:
        for condition, keywords in conditions.items():
            if token in keywords:
                return condition
    return 'equals'

def extract_item_id(tokens):
    for token in tokens:
        if token.isdigit() and len(token) >= 4:
            return int(token)
    return None

def detect_common_query(tokens):
    for token in tokens:
        if token in common_queries:
            return token
    return None

def get_field_possible_values(field):
    return list(set(str(item.get(field, '')).lower().strip() for item in data['items'] if item.get(field)))

def extract_value(tokens, field):
    if field == 'inventory_item_id':
        return extract_item_id(tokens)
    possible_values = get_field_possible_values(field)
    for token in tokens:
        if token in possible_values:
            return token
        match = get_close_matches(token, possible_values, n=1, cutoff=0.7)
        if match:
            return match[0]
    for token in tokens:
        if token.isdigit():
            return int(token)
    return None

def fuzzy_match(user_value, item_value):
    if not isinstance(item_value, str):
        return False
    item_value = item_value.lower().strip()
    user_value = user_value.lower().strip()
    matches = get_close_matches(user_value, [item_value], cutoff=0.6)
    return len(matches) > 0

def qa_fallback(user_input):
    user_input_clean = user_input.lower().strip()
    possible_questions = [pair['question'] for pair in qa_data]
    matches = get_close_matches(user_input_clean, possible_questions, n=1, cutoff=0.6)
    if matches:
        for pair in qa_data:
            if pair['question'] == matches[0]:
                return pair['answer']
    return None

def chatbot_response(user_input):
    tokens = preprocess(user_input)
    field = detect_field(tokens)
    condition = detect_condition(tokens)
    inventory_id = extract_item_id(tokens)
    common_query = detect_common_query(tokens)
    value = extract_value(tokens, field)

    if common_query:
        if common_query in ['top', 'best', 'max', 'highest', 'top selling', 'top item']:
            top_item = max(data['items'], key=lambda x: x.get('qty', 0))
            return [top_item], f"🌟 **Top Item:**\nID: {top_item.get('inventory_item_id')} | Desc: {top_item.get('description')} | Qty: {top_item.get('qty')}"
        elif common_query in ['list', 'inventory', 'inven']:
            return data['items'][:5], "📋 **First 5 Inventory Items:**"
        elif common_query in ['stock']:
            total_stock = sum(item.get('qty', 0) for item in data['items'])
            return [], f"📦 **Total Stock:** {total_stock}"
        elif common_query in ['value', 'val']:
            total_value = sum(item.get('stockvalue', 0) for item in data['items'])
            return [], f"💰 **Total Value:** {total_value}"
        elif common_query in ['fab', 'fabtype']:
            fab_types = set(item.get('fabtype', 'N/A') for item in data['items'])
            return [], f"🧵 **Fabric Types:** {', '.join(fab_types)}"

    if inventory_id:
        target_item = next((item for item in data['items'] if int(item.get('inventory_item_id', 0)) == inventory_id), None)
        if target_item:
            if field:
                return [target_item], f"🔍 **{field}:** {target_item.get(field, 'N/A')}"
            return [target_item], "🔍 **Full details available.**"

    if not field:
        qa_answer = qa_fallback(user_input)
        if qa_answer:
            return [], f"💡 **Q&A Answer:** {qa_answer}"
        return [], None  # Let Groq handle this

    if value is None and field != 'txndate':
        return [], f"⚠️ Field detected: {field}, but value missing."

    results = []
    for item in data['items']:
        item_value = item.get(field)
        if item_value is None: continue
        if isinstance(item_value, str): item_value = item_value.lower().strip()
        if isinstance(value, str): value = value.lower().strip()
        try:
            if condition == 'equals' and fuzzy_match(value, item_value):
                results.append(item)
            elif condition == 'contains' and value in str(item_value):
                results.append(item)
            elif condition == 'greater' and isinstance(item_value, (int, float)) and item_value > float(value):
                results.append(item)
            elif condition == 'less' and isinstance(item_value, (int, float)) and item_value < float(value):
                results.append(item)
        except:
            continue
    if not results:
        return [], None  # Let Groq handle
    return results, None

def format_results(results, start_idx, page_size):
    paged = results[start_idx:start_idx+page_size]
    response = ""
    for idx, item in enumerate(paged, start=start_idx+1):
        response += f"\n🔸 **Result {idx}:**\n"
        response += f"- **ID:** {item.get('inventory_item_id')}\n"
        response += f"- **Desc:** {item.get('description')}\n"
        response += f"- **Major:** {item.get('major')}\n"
        response += f"- **Fabric:** {item.get('fabtype')}\n"
    return response

# ----------------- Streamlit App -----------------
st.set_page_config(page_title="🎨 Smart Chatbot & Forecasting Analysis", layout="wide")
st.markdown("<h1 style='text-align: center; color: #2575fc;'>🎨 Smart Chatbot & Forecasting Analysis</h1>", unsafe_allow_html=True)
st.markdown("<hr style='border-top: 3px solid #2575fc;'>", unsafe_allow_html=True)

user_input = st.text_input("💬 **Ask about Inventory or General Questions:**")

if user_input:
    results, message = chatbot_response(user_input)
    st.write("🤖 **Chatbot Response:**")
    if message:
        st.success(message)
    elif results:
        page_size = 5
        if 'page_number' not in st.session_state:
            st.session_state.page_number = 0
        total_pages = len(results) // page_size + int(len(results) % page_size > 0)
        start_idx = st.session_state.page_number * page_size
        st.markdown(format_results(results, start_idx, page_size))

        col1, col2, col3 = st.columns([1,2,1])
        with col1:
            if st.button("⬅️ Prev") and st.session_state.page_number > 0:
                st.session_state.page_number -= 1
        with col3:
            if st.button("Next ➡️") and st.session_state.page_number < total_pages - 1:
                st.session_state.page_number += 1
        st.write(f"📄 **Page {st.session_state.page_number+1} of {total_pages}**")
    else:
        groq_reply = groq_fallback(user_input)
        st.info(f"🤖 **Groq Answer:** {groq_reply}")
