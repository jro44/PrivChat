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

# --- 5. INTERFEJS CZATU ---
@st.fragment(run_every=2)
def render_chat_area():
    my_uid = st.session_state['user_uid']
    my_nick = st.session_state['user_nick']
    
    if my_nick == "Pasterz":
        if not st.session_state['chat_target_uid']:
            st.info("👈 Wybierz duszę z listy po lewej stronie.")
            return
        target_uid = st.session_state['chat_target_uid']
        target_name = st.session_state['chat_target_name']
    else:
        target_uid = "PASTERZ_ADMIN_ID"
        target_name = "Pasterz"

    messages = get_messages(my_uid, target_uid)
    if not messages: st.write(f"Tu zaczyna się rozmowa z: **{target_name}**")
    
    for msg in messages:
        is_me = (msg['from_uid'] == my_uid)
        msg_time = datetime.fromtimestamp(msg['timestamp']).strftime('%H:%M')
        sender_label = "TY" if is_me else msg['from_nick']
        
        with st.container():
            if is_me:
                # Avatar dla mnie (Aniołek jeśli Pasterz, lub zwykły User)
                avatar_icon = "😇" if my_nick == "Pasterz" else "👤"
                with st.chat_message("user", avatar=avatar_icon):
                    st.markdown(f"<div class='msg-header-me'><span class='msg-time'>{msg_time}</span> {sender_label}</div><div class='clearfix'><div class='content-me'>{msg['content']}</div></div>", unsafe_allow_html=True)
            else:
                # Avatar dla rozmówcy
                avatar_icon = "😇" if target_name == "Pasterz" else "🕊️"
                with st.chat_message("assistant", avatar=avatar_icon):
                    st.markdown(f"<div class='msg-header-other'>{sender_label} <span class='msg-time'>{msg_time}</span></div><div class='clearfix'><div class='content-other'>{msg['content']}</div></div>", unsafe_allow_html=True)
            st.markdown("<div style='height: 5px'></div>", unsafe_allow_html=True)

# --- 6. LOGIKA GŁÓWNA ---

if not st.session_state['verified']:
    st.markdown("<h1 style='text-align: center; color: #1565C0;'>🕊️ Niebiański Czat</h1>", unsafe_allow_html=True)
    st.markdown("---")
    c1, c2, c3 = st.columns([1,2,1])
    
    with c2:
        # KROK 1: Nick
        if st.session_state['login_stage'] == "check_nick":
            st.markdown("<h3 style='text-align: center;'>Jak masz na imię?</h3>", unsafe_allow_html=True)
            nick_input = st.text_input("Wpisz swoje imię / nick", placeholder="Np. Anna")
            
            a, b = st.session_state['captcha_a'], st.session_state['captcha_b']
            ans = st.number_input(f"Potwierdź, że jesteś człowiekiem: {a} + {b} =", step=1)

            if st.button("DALEJ 🕊️"):
                if not nick_input: st.error("Proszę wpisać imię.")
                elif ans != (a+b): st.error("Błąd obliczeń."); st.rerun()
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
            st.info(f"Witaj! Ktoś o imieniu '{nick}' już tu jest.")
            if st.button(f"🔑 To ja! Mam swój PIN i wracam"):
                st.session_state['login_stage'] = "verify_pin"; st.rerun()
            st.markdown("<p style='text-align:center'>--- LUB ---</p>", unsafe_allow_html=True)
            if st.button(f"✨ Jestem nową osobą o imieniu '{nick}'"):
                uid, pin = create_new_user(nick)
                st.session_state['user_uid'] = uid
                st.session_state['user_pin'] = pin
                st.session_state['login_stage'] = "new_user_info"
                st.rerun()

        # KROK 2a: Logowanie PINem
        elif st.session_state['login_stage'] == "verify_pin":
            nick = st.session_state['temp_nick']
            st.markdown(f"<h3 style='text-align: center;'>Witaj ponownie, {nick}</h3>", unsafe_allow_html=True)
            st.info("Aby otworzyć Twoją rozmowę, podaj PIN.")
            pin_input = st.text_input("Twój kod PIN (4 cyfry)", type="password", max_chars=4)
            if st.button("OTWÓRZ CZAT 🔓"):
                uid, user_data = login_with_nick_and_pin(nick, pin_input)
                if uid:
                    st.session_state['user_uid'] = uid
                    st.session_state['user_nick'] = nick
                    st.session_state['verified'] = True
                    st.rerun()
                else: st.error("Niestety, PIN jest nieprawidłowy.")
            if st.button("Wróć"): st.session_state['login_stage'] = "check_nick"; st.rerun()

        # KROK 2b: Pasterz
        elif st.session_state['login_stage'] == "verify_pasterz":
            st.markdown("### Witaj Pasterzu")
            pin_input = st.text_input("PIN ADMINA", type="password")
            if st.button("WEJDŹ"):
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
            
            st.success("✨ Twoje bezpieczne miejsce zostało utworzone.")
            st.markdown("<h4 style='text-align:center; color:#1565C0'>Ważna informacja</h4>", unsafe_allow_html=True)
            st.info("Aby wrócić do tej rozmowy w przyszłości, będziesz potrzebować tych danych. Zapisz je proszę.")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"""
                <div class='pin-box'>
                    <div style='color:#F9A825; font-size:0.9rem'>TWOJE IMIĘ</div>
                    <div class='nick-val'>{nick}</div>
                </div>
                """, unsafe_allow_html=True)
            with col_b:
                st.markdown(f"""
                <div class='pin-box'>
                    <div style='color:#F9A825; font-size:0.9rem'>TWÓJ PIN</div>
                    <div class='pin-val'>{pin}</div>
                </div>
                """, unsafe_allow_html=True)
                
            st.warning("Bez PIN-u powrót do rozmowy nie będzie możliwy.")
            
            if st.button("ZAPISAŁEM DANE - WEJDŹ 🕊️"):
                st.session_state['user_nick'] = nick
                st.session_state['verified'] = True
                st.rerun()

# B. CZAT WŁAŚCIWY
else:
    me_nick = st.session_state['user_nick']
    me_uid = st.session_state['user_uid']
    
    if me_nick == "Pasterz":
        with st.sidebar:
            st.header("🕊️ Duszyczki")
            if st.button("Odśwież listę"): st.rerun()
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
        st.markdown(f"### 😇 Rozmowa z: **{target_label}**")
        st.markdown("---")
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        if st.session_state['chat_target_uid']:
            if prompt := st.chat_input(f"Odpisz..."):
                send_message("PASTERZ_ADMIN_ID", "Pasterz", st.session_state['chat_target_uid'], prompt)
                st.rerun()
    else:
        c1, c2 = st.columns([3,1])
        with c1: st.markdown(f"### 🕊️ Witaj, **{me_nick}**")
        with c2: 
            if st.button("Wyloguj"): st.session_state['verified'] = False; st.session_state['login_stage'] = "check_nick"; st.rerun()
        
        st.info("To bezpieczna przestrzeń. Tylko Pasterz widzi Twoje wiadomości.")
        render_chat_area()
        st.markdown("<br>", unsafe_allow_html=True)
        if prompt := st.chat_input("Napisz wiadomość..."):
            send_message(me_uid, me_nick, "PASTERZ_ADMIN_ID", prompt)
            st.rerun()