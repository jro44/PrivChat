import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os
import random
import json # Dodane do obsługi klucza w chmurze
from datetime import datetime, timedelta

# --- 1. KONFIGURACJA FIREBASE (HYBRYDOWA: PLIK LUB CHMURA) ---
# Ten kod zadziała i u Ciebie na komputerze (szukając pliku),
# i w chmurze (szukając sekretów), bez zmieniania ani linijki!

if not firebase_admin._apps:
    # Opcja A: Jesteśmy w chmurze (Streamlit Cloud)
    if "FIREBASE_KEY" in st.secrets:
        # Pobieramy klucz z bezpiecznego schowka Streamlit
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    
    # Opcja B: Jesteśmy lokalnie na komputerze
    elif os.path.exists("key.json"):
        cred = credentials.Certificate("key.json")
        firebase_admin.initialize_app(cred)
    
    # Opcja C: Błąd
    else:
        st.error("Błąd: Nie znaleziono klucza ani w pliku, ani w sekretach.")
        st.stop()

db = firestore.client()

st.set_page_config(page_title="Secure Chat", page_icon="🛡️", layout="centered")

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
    .stButton > button:hover {
        background-color: #A00030;
    }
    
    /* WYGLĄD WIADOMOŚCI */
    .stChatMessage[data-testid="stChatMessage"] { background-color: transparent; }
    
    .msg-header-me {
        color: #FF6B6B; font-weight: 900; font-size: 0.85rem; text-transform: uppercase;
        margin-bottom: 4px; display: flex; justify-content: flex-end; align_items: center; gap: 10px;
    }
    .msg-header-other {
        color: #4ECDC4; font-weight: 900; font-size: 0.85rem; text-transform: uppercase;
        margin-bottom: 4px; display: flex; justify-content: flex-start; align_items: center; gap: 10px;
    }
    .msg-time { color: #888; font-size: 0.7rem; font-weight: normal; }
    
    .msg-content { padding: 10px 15px; border-radius: 12px; display: inline-block; font-size: 1rem; }
    .content-me {
        background-color: rgba(128, 0, 32, 0.4); border: 1px solid #800020;
        border-bottom-right-radius: 0; float: right;
    }
    .content-other {
        background-color: rgba(255, 255, 255, 0.1); border: 1px solid #444;
        border-bottom-left-radius: 0; float: left;
    }
    .clearfix::after { content: ""; clear: both; display: table; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. ZMIENNE SESJI ---
if 'verified' not in st.session_state: st.session_state['verified'] = False
if 'user_nick' not in st.session_state: st.session_state['user_nick'] = ""
if 'last_msg_time' not in st.session_state: st.session_state['last_msg_time'] = 0
if 'captcha_a' not in st.session_state: st.session_state['captcha_a'] = random.randint(1, 10)
if 'captcha_b' not in st.session_state: st.session_state['captcha_b'] = random.randint(1, 10)

# --- 4. MECHANIZM CZYSZCZENIA O 6:00 ---
def perform_daily_cleanup():
    now = datetime.now()
    cutoff_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if now < cutoff_time:
        cutoff_time = cutoff_time - timedelta(days=1)
    cutoff_timestamp = cutoff_time.timestamp()
    
    # Pobieranie referencji do dokumentów (bez pobierania całej treści dla oszczędności)
    old_docs = db.collection('live_chat').where('timestamp', '<', cutoff_timestamp).select([]).stream()
    
    deleted_count = 0
    batch = db.batch() # Użycie batcha dla wydajności
    for doc in old_docs:
        batch.delete(doc.reference)
        deleted_count += 1
        if deleted_count % 400 == 0: # Firestore limituje batch do 500
            batch.commit()
            batch = db.batch()
    batch.commit()
    
    return deleted_count

# --- 5. FUNKCJA WYSYŁANIA ---
def send_message_to_db(nick, content):
    now_ts = time.time()
    if now_ts - st.session_state['last_msg_time'] < 5:
        return False, "⏳ Zwolnij! (Max co 5 sek)"
    
    db.collection('live_chat').add({
        'nick': nick, 'content': content, 'timestamp': now_ts
    })
    st.session_state['last_msg_time'] = now_ts
    return True, "OK"

# --- 6. OKNO CZATU (AUTO-ODŚWIEŻANIE) ---
@st.fragment(run_every=2)
def render_chat_window():
    docs = db.collection('live_chat').order_by('timestamp').stream()
    messages = [doc.to_dict() for doc in docs]
    
    if not messages:
        st.info("Tablica jest czysta (automatyczne czyszczenie o 6:00).")
        return

    for msg in messages:
        is_me = (msg['nick'] == st.session_state['user_nick'])
        msg_time = datetime.fromtimestamp(msg['timestamp']).strftime('%H:%M')
        
        with st.container():
            if is_me:
                st.markdown(f"""
                    <div class='msg-header-me'><span class='msg-time'>{msg_time}</span> {msg['nick']}</div>
                    <div class='clearfix'><div class='msg-content content-me'>{msg['content']}</div></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class='msg-header-other'>{msg['nick']} <span class='msg-time'>{msg_time}</span></div>
                    <div class='clearfix'><div class='msg-content content-other'>{msg['content']}</div></div>
                """, unsafe_allow_html=True)
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)

# --- 7. LOGIKA GŁÓWNA ---
if not st.session_state['verified']:
    st.title("🛡️ Secure Gate")
    st.markdown("---")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        nick = st.text_input("TWÓJ NICK", placeholder="Kto tam?")
        a, b = st.session_state['captcha_a'], st.session_state['captcha_b']
        ans = st.number_input(f"ANTY-BOT: {a} + {b} =", step=1)
        if st.button("WEJDŹ"):
            if not nick: st.error("Nick wymagany")
            elif ans != (a+b): 
                st.error("Błąd bota"); st.session_state['captcha_a'] = random.randint(1,10); st.rerun()
            else:
                st.session_state['user_nick'] = nick
                st.session_state['verified'] = True
                try:
                    cleaned = perform_daily_cleanup()
                    if cleaned > 0: st.toast(f"🧹 Wyczyszczono stare wiadomości: {cleaned}")
                except: pass
                st.rerun()
else:
    col1, col2 = st.columns([4, 1])
    with col1: st.markdown(f"### 👤 {st.session_state['user_nick']}")
    with col2:
        if st.button("WYLOGUJ"): st.session_state['verified'] = False; st.rerun()
    st.markdown("---")
    
    render_chat_window()
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.expander("😀 EMOTIKONY"):
        emojis = ["😀", "😂", "😎", "🥰", "😭", "😡", "👍", "👎", "❤️", "🍷", "🔥", "💩", "👀", "🚀"]
        cols = st.columns(7)
        for i, emo in enumerate(emojis):
            if cols[i%7].button(emo, key=f"emo_{i}"): send_message_to_db(st.session_state['user_nick'], emo); st.rerun()

    if prompt := st.chat_input("Napisz coś..."):
        ok, msg = send_message_to_db(st.session_state['user_nick'], prompt)
        if ok: st.toast("Wysłano!", icon="✉️"); st.rerun()
        else: st.error(msg)