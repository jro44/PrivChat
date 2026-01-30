import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os
import random
import json
from datetime import datetime

# --- 1. KONFIGURACJA FIREBASE ---
if not firebase_admin._apps:
    if "FIREBASE_KEY" in st.secrets:
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    elif os.path.exists("key.json"):
        cred = credentials.Certificate("key.json")
        firebase_admin.initialize_app(cred)
    else:
        st.error("Błąd: Brak konfiguracji Firebase.")
        st.stop()

db = firestore.client()

# Zmieniamy ikonę na Gołębia i tytuł
st.set_page_config(page_title="Niebiański Czat", page_icon="🕊️", layout="centered")

# --- 2. CSS (MOTYW ANIELSKI / NIEBO) ---
st.markdown("""
    <style>
    /* TŁO APLIKACJI - Gradient Nieba */
    .stApp {
        background: linear-gradient(180deg, #E3F2FD 0%, #FFFFFF 100%);
        color: #2c3e50; /* Ciemny granatowy tekst dla kontrastu */
    }
    
    /* Ukrycie elementów Streamlit */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* NAGŁÓWKI */
    h1, h2, h3 {
        color: #1565C0 !important; /* Mocny niebieski */
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* POLA TEKSTOWE (Inputy) */
    .stTextInput input, .stNumberInput input {
        background-color: #FFFFFF !important; 
        color: #1565C0 !important; /* Niebieski tekst */
        border: 2px solid #90CAF9 !important; /* Jasnoniebieska ramka */
        border-radius: 10px;
        font-size: 1.1rem !important; /* Powiększona czcionka */
        padding: 10px;
    }
    .stTextInput input:focus {
        border-color: #1E88E5 !important;
        box-shadow: 0 0 10px rgba(33, 150, 243, 0.3);
    }
    
    /* PRZYCISKI - Niebiański Błękit */
    .stButton > button {
        background: linear-gradient(to right, #4FC3F7, #29B6F6);
        color: white; 
        border: none; 
        font-weight: bold; 
        width: 100%;
        border-radius: 20px;
        font-size: 1.1rem !important; /* Duża czcionka na guzikach */
        padding: 0.5rem 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s;
    }
    .stButton > button:hover { 
        background: linear-gradient(to right, #29B6F6, #039BE5);
        transform: scale(1.02);
        color: white;
    }
    
    /* DYMKI WIADOMOŚCI */
    .stChatMessage[data-testid="stChatMessage"] { background-color: transparent; }
    
    /* Nagłówki wiadomości */
    .msg-header-me { 
        color: #1E88E5; /* Niebieski */
        font-weight: bold; font-size: 0.9rem; 
        text-transform: uppercase; margin-bottom: 2px; 
        display: flex; justify-content: flex-end; 
    }
    .msg-header-other { 
        color: #FBC02D; /* Złoty dla innych (anielski) */
        font-weight: bold; font-size: 0.9rem; 
        text-transform: uppercase; margin-bottom: 2px; 
        display: flex; justify-content: flex-start; 
    }
    .msg-time { color: #90A4AE; font-size: 0.75rem; margin-left: 8px; font-weight: normal;}
    
    /* Treść wiadomości - Błękitne i Białe chmurki */
    .content-me { 
        background-color: #BBDEFB; /* Jasny błękit */
        color: #0D47A1; /* Ciemny tekst */
        border: 1px solid #90CAF9; 
        padding: 12px 18px; 
        border-radius: 15px; border-bottom-right-radius: 2px; 
        float: right; display: inline-block;
        font-size: 1.1rem; /* DUŻA CZCIONKA */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .content-other { 
        background-color: #FFFFFF; /* Biała chmurka */
        color: #37474F; 
        border: 1px solid #CFD8DC; 
        padding: 12px 18px; 
        border-radius: 15px; border-bottom-left-radius: 2px; 
        float: left; display: inline-block;
        font-size: 1.1rem; /* DUŻA CZCIONKA */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .clearfix::after { content: ""; clear: both; display: table; }
    
    /* Panel PIN - Złoty i Biały */
    .pin-box {
        background-color: #FFF9C4; /* Jasny złoty/kremowy */
        border: 2px dashed #FBC02D; /* Złota ramka */
        padding: 15px;
        text-align: center; border-radius: 15px; margin: 10px 0;
    }
    .pin-val { font-size: 2.2rem; font-weight: bold; color: #F57F17; letter-spacing: 3px; }
    .nick-val { font-size: 1.6rem; font-weight: bold; color: #1565C0; }
    
    /* Komunikaty błędów i sukcesów */
    .stAlert { border-radius: 10px; }
    
    </style>
    """, unsafe_allow_html=True)

# --- 3. ZMIENNE SESJI ---
if 'verified' not in st.session_state: st.session_state['verified'] = False
if 'user_uid' not in st.session_state: st.session_state['user_uid'] = "" 
if 'user_nick' not in st.session_state: st.session_state['user_nick'] = ""
if 'user_pin' not in st.session_state: st.session_state['user_pin'] = ""
if 'chat_target_uid' not in st.session_state: st.session_state['chat_target_uid'] = "" 
if 'chat_target_name' not in st.session_state: st.session_state['chat_target_name'] = "" 

if 'login_stage' not in st.session_state: st.session_state['login_stage'] = "check_nick"
if 'temp_nick' not in st.session_state: st.session_state['temp_nick'] = ""
if 'captcha_a' not in st.session_state: st.session_state['captcha_a'] = random.randint(1, 10)
if 'captcha_b' not in st.session_state: st.session_state['captcha_b'] = random.randint(1, 10)

# --- 4. LOGIKA BAZY DANYCH ---

def check_if_nick_exists(nick):
    docs = db.collection('users').where('nick', '==', nick).limit(1).stream()
    for _ in docs: return True
    return False

def login_with_nick_and_pin(nick, pin):
    docs = db.collection('users').where('nick', '==', nick).where('pin', '==', pin).stream()
    for doc in docs: return doc.id, doc.to_dict()
    return None, None

def create_new_user(nick):
    new_pin = str(random.randint(1000, 9999))
    doc_ref = db.collection('users').document() 
    doc_ref.set({ 'nick': nick, 'pin': new_pin, 'created_at': time.time() })
    return doc_ref.id, new_pin

def get_chat_id(uid1, uid2):
    users = sorted([uid1, uid2])
    return f"{users[0]}_{users[1]}"

def send_message(from_uid, from_nick, to_uid, content):
    chat_id = get_chat_id(from_uid, to_uid)
    timestamp = time.time()
    db.collection('private_messages').add({
        'chat_id': chat_id, 'from_uid': from_uid, 'from_nick': from_nick,
        'to_uid': to_uid, 'content': content, 'timestamp': timestamp
    })
    
    if to_uid == "PASTERZ_ADMIN_ID":
        pin_display = "????"
        if from_nick != "Pasterz":
            user_doc = db.collection('users').document(from_uid).get()
            if user_doc.exists: pin_display = user_doc.to_dict().get('pin')

        db.collection('contacts').document(from_uid).set({
            'last_msg': timestamp, 'nick': from_nick, 'pin': pin_display, 'uid': from_uid
        }, merge=True)

def get_messages(uid1, uid2):
    chat_id = get_chat_id(uid1, uid2)
    docs = db.collection('private_messages').where('chat_id', '==', chat_id).order_by('timestamp').stream()
    return [doc.to_dict() for doc in docs]

def get_all_contacts():
    docs = db.collection('contacts').order_by('last_msg', direction=firestore.Query.DESCENDING).stream()
    return [doc.to_dict() for doc in docs]

# --- 5.