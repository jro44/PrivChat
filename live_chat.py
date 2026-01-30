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

# --- 2. CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    #MainMenu, footer, header {visibility: hidden;}
    
    .stTextInput input, .stNumberInput input {
        background-color: #1F242D !important; color: white !important;
        border: 1px solid #4A4A4A; border-radius: 6px;
    }
    .stButton > button {
        background-color: #800020; color: white; border: none; font-weight: bold; width: 100%;
    }
    .stButton > button:hover { background-color: #A00030; }
    
    /* WIADOMOŚCI */
    .stChatMessage[data-testid="stChatMessage"] { background-color: transparent; }
    .msg-header-me { color: #FF6B6B; font-weight: 900; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 2px; display: flex; justify-content: flex-end; }
    .msg-header-other { color: #4ECDC4; font-weight: 900; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 2px; display: flex; justify-content: flex-start; }
    .msg-time { color: #888; font-size: 0.7rem; margin-left: 8px; font-weight: normal;}
    .content-me { background-color: rgba(128, 0, 32, 0.5); border: 1px solid #800020; padding: 10px 15px; border-radius: 12px; border-bottom-right-radius: 0; float: right; display: inline-block; }
    .content-other { background-color: rgba(255, 255, 255, 0.1); border: 1px solid #444; padding: 10px 15px; border-radius: 12px; border-bottom-left-radius: 0; float: left; display: inline-block; }
    .clearfix::after { content: ""; clear: both; display: table; }
    
    /* Wygląd PINu */
    .pin-box {
        background-color: #112211; border: 2px dashed #00FF00; padding: 15px;
        text-align: center; border-radius: 10px; margin: 10px 0;
    }
    .pin-val { font-size: 2rem; font-weight: bold; color: #00FF00; letter-spacing: 3px; }
    .nick-val { font-size: 1.5rem; font-weight: bold; color: #FFA500; }
    
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

# --- 5. INTERFEJS CZATU ---
@st.fragment(run_every=2)
def render_chat_area():
    my_uid = st.session_state['user_uid']
    my_nick = st.session_state['user_nick']
    
    if my_nick == "Pasterz":
        if not st.session_state['chat_target_uid']:
            st.info("👈 Wybierz owieczkę z listy.")
            return
        target_uid = st.session_state['chat_target_uid']
        target_name = st.session_state['chat_target_name']
    else:
        target_uid = "PASTERZ_ADMIN_ID"
        target_name = "Pasterz"

    messages = get_messages(my_uid, target_uid)
    if not messages: st.write(f"Początek rozmowy z: **{target_name}**")
    
    for msg in messages:
        is_me = (msg['from_uid'] == my_uid)
        msg_time = datetime.fromtimestamp(msg['timestamp']).strftime('%H:%M')
        sender_label = "TY" if is_me else msg['from_nick']
        
        with st.container():
            if is_me:
                st.markdown(f"<div class='msg-header-me'><span class='msg-time'>{msg_time}</span> {sender_label}</div><div class='clearfix'><div class='content-me'>{msg['content']}</div></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='msg-header-other'>{sender_label} <span class='msg-time'>{msg_time}</span></div><div class='clearfix'><div class='content-other'>{msg['content']}</div></div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

# --- 6. LOGIKA GŁÓWNA ---

if not st.session_state['verified']:
    st.title("🙏 Konfesjonał")
    st.markdown("---")
    c1, c2, c3 = st.columns([1,2,1])
    
    with c2:
        # KROK 1: Nick
        if st.session_state['login_stage'] == "check_nick":
            nick_input = st.text_input("PODAJ SWÓJ NICK", placeholder="Np. Ania")
            a, b = st.session_state['captcha_a'], st.session_state['captcha_b']
            ans = st.number_input(f"WERYFIKACJA: {a} + {b} =", step=1)

            if st.button("DALEJ >>"):
                if not nick_input: st.error("Nick wymagany")
                elif ans != (a+b): st.error("Błąd bota"); st.rerun()
                else:
                    st.session_state['temp_nick'] = nick_input
                    if nick_input == "Pasterz":
                        st.session_state['login_stage'] = "verify_pasterz"
                    else:
                        exists = check_if_nick_exists(nick_input)
                        if exists: st.session_state['login_stage'] = "choice_existing_user"
                        else:
                            uid, pin = create_new_user(nick_input)
                            st.session_state['user_uid'] = uid
                            st.session_state['user_pin'] = pin
                            st.session_state['login_stage'] = "new_user_info"
                    st.rerun()

        # KROK 1b: Wybór (Nowy czy Stary)
        elif st.session_state['login_stage'] == "choice_existing_user":
            nick = st.session_state['temp_nick']
            st.info(f"Osoba o nicku '{nick}' już tu była.")
            if st.button(f"🔐 To ja! Chcę się zalogować"):
                st.session_state['login_stage'] = "verify_pin"; st.rerun()
            st.write("--- LUB ---")
            if st.button(f"🆕 Jestem nową osobą o imieniu '{nick}'"):
                uid, pin = create_new_user(nick)
                st.session_state['user_uid'] = uid
                st.session_state['user_pin'] = pin
                st.session_state['login_stage'] = "new_user_info"
                st.rerun()

        # KROK 2a: Logowanie PINem
        elif st.session_state['login_stage'] == "verify_pin":
            nick = st.session_state['temp_nick']
            st.markdown(f"### Logowanie: {nick}")
            st.info("Aby wrócić do SWOJEJ rozmowy, podaj swój PIN.")
            pin_input = st.text_input("TWÓJ PIN (4 cyfry)", type="password", max_chars=4)
            if st.button("WEJDŹ"):
                uid, user_data = login_with_nick_and_pin(nick, pin_input)
                if uid:
                    st.session_state['user_uid'] = uid
                    st.session_state['user_nick'] = nick
                    st.session_state['verified'] = True
                    st.rerun()
                else: st.error("Błędny PIN! Nie odnaleziono takiej rozmowy.")
            if st.button("Wróć"): st.session_state['login_stage'] = "check_nick"; st.rerun()

        # KROK 2b: Pasterz
        elif st.session_state['login_stage'] == "verify_pasterz":
            st.markdown("### Witaj Pasterzu")
            pin_input = st.text_input("PIN ADMINA", type="password")
            if st.button("ZALOGUJ"):
                secret = st.secrets.get("PASTERZ_PIN", "0000")
                if pin_input == secret:
                    st.session_state['user_nick'] = "Pasterz"
                    st.session_state['user_uid'] = "PASTERZ_ADMIN_ID"
                    st.session_state['verified'] = True
                    st.rerun()
                else: st.error("Zły PIN")
            if st.button("Wróć"): st.session_state['login_stage'] = "check_nick"; st.rerun()

        # KROK 3: Nowe konto (OSTRZEŻENIE O DANYCH)
        elif st.session_state['login_stage'] == "new_user_info":
            nick = st.session_state['temp_nick']
            pin = st.session_state['user_pin']
            
            st.success("✅ NOWA ROZMOWA ROZPOCZĘTA!")
            
            # --- SEKCJA OSTRZEGAWCZA ---
            st.error("🛑 BARDZO WAŻNE: ZAPISZ DANE LOGOWANIA!")
            st.info("Aby wrócić do tej konkretnej rozmowy w przyszłości, będziesz potrzebować DWÓCH rzeczy:")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
                <div class='pin-box'>
                    <div style='color:#aaa; font-size:0.8rem'>TWÓJ NICK</div>
                    <div class='nick-val'>{nick}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
                <div class='pin-box'>
                    <div style='color:#aaa; font-size:0.8rem'>TWÓJ PIN</div>
                    <div class='pin-val'>{pin}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.warning("⚠️ Bez tego PINu utracisz dostęp do tej rozmowy bezpowrotnie!")
            
            if st.button("ROZUMIEM I ZAPISAŁEM - WEJDŹ >>"):
                st.session_state['user_nick'] = nick
                st.session_state['verified'] = True
                st.rerun()

# B. CZAT WŁAŚCIWY
else:
    me_nick = st.session_state['user_nick']
    me_uid = st.session_state['user_uid']
    
    if me_nick == "Pasterz":
        with st.sidebar:
            st.header("🐑 Owieczki")
            if st.button("Odśwież"): st.rerun()
            contacts = get_all_contacts()
            for c in contacts:
                display_label = f"{c['nick']} (PIN: {c.get('pin', '????')})"
                if st.button(f"👤 {display_label}", key=c['uid']):
                    st.session_state['chat_target_uid'] = c['uid']
                    st.session_state['chat_target_name'] = display_label
                    st.rerun()
            st.markdown("---")
            if st.button("Wyloguj"): st.session_state['verified'] = False; st.session_state['login_stage'] = "check_nick"; st.rerun()

        target_label = st.session_state['chat_target_name'] if st.session_state['chat_target_name'] else "..."
        st.markdown(f"### 🛡️ Panel Pasterza | Rozmowa z: **{target_label}**")
        st.markdown("---")
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state['chat_target_uid']:
            if prompt := st.chat_input(f"Odpisz..."):
                send_message("PASTERZ_ADMIN_ID", "Pasterz", st.session_state['chat_target_uid'], prompt)
                st.rerun()
    else:
        c1, c2 = st.columns([3,1])
        with c1: st.markdown(f"### 👋 Witaj, **{me_nick}**")
        with c2: 
            if st.button("Wyloguj"): st.session_state['verified'] = False; st.session_state['login_stage'] = "check_nick"; st.rerun()
        st.info("Prywatna rozmowa z Pasterzem.")
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        if prompt := st.chat_input("Napisz do Pasterza..."):
            send_message(me_uid, me_nick, "PASTERZ_ADMIN_ID", prompt)
            st.rerun()