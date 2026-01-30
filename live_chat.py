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

st.set_page_config(page_title="Pasterz Chat", page_icon="🙏", layout="centered")

# --- 2. CSS (STYL I CZYTELNOŚĆ) ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    #MainMenu, footer, header {visibility: hidden;}
    
    .stTextInput input, .stNumberInput input {
        background-color: #1F242D !important; color: white !important;
        border: 1px solid #4A4A4A; border-radius: 6px;
    }
    .stButton > button {
        background-color: #800020; color: white; border: none; font-weight: bold;
    }
    .stButton > button:hover { background-color: #A00030; }
    
    /* WIADOMOŚCI */
    .stChatMessage[data-testid="stChatMessage"] { background-color: transparent; }
    
    .msg-header-me {
        color: #FF6B6B; font-weight: 900; font-size: 0.8rem; text-transform: uppercase;
        margin-bottom: 2px; display: flex; justify-content: flex-end;
    }
    .msg-header-other {
        color: #4ECDC4; font-weight: 900; font-size: 0.8rem; text-transform: uppercase;
        margin-bottom: 2px; display: flex; justify-content: flex-start;
    }
    .msg-time { color: #888; font-size: 0.7rem; margin-left: 8px; font-weight: normal;}
    
    .content-me {
        background-color: rgba(128, 0, 32, 0.5); border: 1px solid #800020;
        padding: 10px 15px; border-radius: 12px; border-bottom-right-radius: 0;
        float: right; display: inline-block;
    }
    .content-other {
        background-color: rgba(255, 255, 255, 0.1); border: 1px solid #444;
        padding: 10px 15px; border-radius: 12px; border-bottom-left-radius: 0;
        float: left; display: inline-block;
    }
    .clearfix::after { content: ""; clear: both; display: table; }
    
    /* Lista użytkowników (dla Pasterza) */
    .user-select-btn { width: 100%; text-align: left; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ZMIENNE SESJI ---
if 'verified' not in st.session_state: st.session_state['verified'] = False
if 'user_nick' not in st.session_state: st.session_state['user_nick'] = ""
if 'chat_target' not in st.session_state: st.session_state['chat_target'] = "" 
if 'captcha_a' not in st.session_state: st.session_state['captcha_a'] = random.randint(1, 10)
if 'captcha_b' not in st.session_state: st.session_state['captcha_b'] = random.randint(1, 10)

# --- 4. LOGIKA BAZY DANYCH ---

def get_chat_id(user1, user2):
    """Tworzy unikalne ID rozmowy dla pary użytkowników (alfabetycznie)."""
    users = sorted([user1, user2])
    return f"{users[0]}_{users[1]}"

def send_message(from_nick, to_nick, content):
    """Wysyła wiadomość do konkretnej rozmowy."""
    chat_id = get_chat_id(from_nick, to_nick)
    timestamp = time.time()
    
    # 1. Zapisujemy wiadomość
    db.collection('private_messages').add({
        'chat_id': chat_id,
        'from': from_nick,
        'to': to_nick,
        'content': content,
        'timestamp': timestamp
    })
    
    # 2. Aktualizujemy listę kontaktów
    if to_nick == "Pasterz":
        user_ref = db.collection('contacts').document(from_nick)
        user_ref.set({
            'last_msg': timestamp,
            'nick': from_nick
        }, merge=True)

def get_messages(user1, user2):
    """Pobiera historię tylko dla tej pary."""
    chat_id = get_chat_id(user1, user2)
    docs = db.collection('private_messages')\
        .where('chat_id', '==', chat_id)\
        .order_by('timestamp')\
        .stream()
    return [doc.to_dict() for doc in docs]

def get_all_contacts():
    """Pobiera listę osób, które pisały do Pasterza."""
    docs = db.collection('contacts').order_by('last_msg', direction=firestore.Query.DESCENDING).stream()
    return [doc.to_dict()['nick'] for doc in docs]

# --- 5. INTERFEJS CZATU (FRAGMENT) ---
@st.fragment(run_every=2)
def render_chat_area():
    me = st.session_state['user_nick']
    
    # Ustalanie rozmówcy
    if me == "Pasterz":
        if not st.session_state['chat_target']:
            st.info("👈 Wybierz owieczkę z panelu bocznego, aby rozpocząć.")
            return
        other = st.session_state['chat_target']
    else:
        other = "Pasterz" 

    # Pobieranie wiadomości
    messages = get_messages(me, other)
    
    if not messages:
        st.write(f"To początek rozmowy z: **{other}**")
    
    # Wyświetlanie
    for msg in messages:
        is_me = (msg['from'] == me)
        msg_time = datetime.fromtimestamp(msg['timestamp']).strftime('%H:%M')
        
        with st.container():
            if is_me:
                st.markdown(f"""
                    <div class='msg-header-me'><span class='msg-time'>{msg_time}</span> TY</div>
                    <div class='clearfix'><div class='content-me'>{msg['content']}</div></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class='msg-header-other'>{msg['from']} <span class='msg-time'>{msg_time}</span></div>
                    <div class='clearfix'><div class='content-other'>{msg['content']}</div></div>
                """, unsafe_allow_html=True)
            st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

# --- 6. GŁÓWNA LOGIKA APLIKACJI ---

# A. EKRAN LOGOWANIA
if not st.session_state['verified']:
    st.title("🙏 Konfesjonał")
    st.markdown("---")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        nick_input = st.text_input("PODAJ SWÓJ NICK", placeholder="Np. ZbłąkanaOwieczka")
        
        # Specjalna obsługa dla Pasterza (PIN)
        pin = ""
        if nick_input == "Pasterz":
            pin = st.text_input("PIN DOSTĘPU", type="password")
        
        a, b = st.session_state['captcha_a'], st.session_state['captcha_b']
        ans = st.number_input(f"WERYFIKACJA: {a} + {b} =", step=1)
        
        if st.button("ROZPOCZNIJ ROZMOWĘ >>"):
            if not nick_input: st.error("Musisz podać nick.")
            elif ans != (a+b): 
                st.error("Błąd anty-bota."); st.session_state['captcha_a'] = random.randint(1,10); st.rerun()
            else:
                # Weryfikacja Pasterza - TERAZ POBIERA PIN Z SEKRETÓW!
                # Jeśli w sekretach nie ma PINu, domyślnie zadziała "0000" (dla bezpieczeństwa, żeby 1234 nie działało)
                secret_pin = st.secrets.get("PASTERZ_PIN", "0000")
                
                if nick_input == "Pasterz" and pin != secret_pin:
                    st.error("Zły PIN!")
                else:
                    st.session_state['user_nick'] = nick_input
                    st.session_state['verified'] = True
                    st.rerun()

# B. EKRAN CZATU
else:
    me = st.session_state['user_nick']
    
    # 1. WIDOK PASTERZA (ADMINA)
    if me == "Pasterz":
        with st.sidebar:
            st.header("🐑 Lista Owieczek")
            if st.button("Odśwież listę"): st.rerun()
            st.markdown("---")
            
            contacts = get_all_contacts()
            if not contacts:
                st.write("Jeszcze nikt nie napisał.")
            
            for contact in contacts:
                if st.button(f"👤 {contact}", key=f"btn_{contact}"):
                    st.session_state['chat_target'] = contact
                    st.rerun()
            
            st.markdown("---")
            if st.button("Wyloguj"): st.session_state['verified'] = False; st.rerun()

        st.markdown(f"### 🛡️ Panel Pasterza | Rozmowa z: **{st.session_state['chat_target'] if st.session_state['chat_target'] else '...'}**")
        st.markdown("---")
        
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state['chat_target']:
            if prompt := st.chat_input(f"Odpisz do {st.session_state['chat_target']}..."):
                send_message("Pasterz", st.session_state['chat_target'], prompt)
                st.rerun()

    # 2. WIDOK UŻYTKOWNIKA (OWIECZKI)
    else:
        c1, c2 = st.columns([3,1])
        with c1: st.markdown(f"### 👋 Witaj, **{me}**")
        with c2: 
            if st.button("Wyloguj"): st.session_state['verified'] = False; st.rerun()
        st.info("Twoja rozmowa jest prywatna. Tylko Pasterz ją widzi.")
        
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        
        if prompt := st.chat_input("Napisz do Pasterza..."):
            send_message(me, "Pasterz", prompt)
            st.rerun()