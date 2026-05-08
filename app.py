import streamlit as st
import pandas as pd
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- 1. CONFIG & AUTH ---
CLIENT_ID = st.secrets["TWITCH_CLIENT_ID"]
CLIENT_SECRET = st.secrets["TWITCH_CLIENT_SECRET"]
ADMIN_PIN = st.secrets["ADMIN_PIN"]

st.set_page_config(page_title="Game Hub Pro", layout="wide", initial_sidebar_state="expanded")

# --- 2. THE ULTIMATE "ZERO-STREAMLIT-BORDER" CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
            font-family: 'Inter', sans-serif;
        }
        
        /* Custom Game Tile - Replaces st.container */
        .game-tile {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(12px);
            border-radius: 10px;
            padding: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 280px; /* Locked Height */
            margin-bottom: 15px;
            transition: transform 0.2s ease;
        }
        .game-tile:hover {
            background: rgba(255, 255, 255, 0.05);
            transform: translateY(-3px);
        }

        .tile-img {
            width: 100%;
            height: 180px;
            object-fit: cover;
            border-radius: 5px;
            margin-bottom: 8px;
        }

        .tile-title {
            font-size: 0.75rem;
            font-weight: 700;
            text-align: center;
            color: #FFFFFF;
            line-height: 1.2;
            height: 34px;
            overflow: hidden;
        }

        .tile-score {
            font-size: 1.1rem;
            font-weight: 800;
            color: #9146FF;
            margin-top: 5px;
        }

        /* Inspector Styling */
        .inspector-panel {
            background: rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }

        h2 { font-weight: 800 !important; letter-spacing: -1.5px !important; }
        h5 { font-size: 0.7rem !important; font-weight: 800 !important; color: #94A3B8 !important; letter-spacing: 2px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-bottom: 15px !important;}

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
df = pd.DataFrame(records) if records else pd.DataFrame(columns=['Title', 'Status', 'ReleaseDate', 'Platform', 'Cover_URL', 'Base_Score', 'OpenCritic', 'Genre'])
numeric_cols = ['Base_Score', 'OpenCritic', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'S_Bonus_1', 'S_Bonus_2']
for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

# --- 4. DASHBOARD HELPER ---
def render_game_tile(row, show_score=False, admin=False, key_prefix=""):
    score_html = f"<div class='tile-score'>{row['Base_Score']}</div>" if show_score else ""
    st.markdown(f"""
        <div class="game-tile">
            <img src="{row['Cover_URL']}" class="tile-img">
            <div class="tile-title">{row['Title']}</div>
            {score_html}
        </div>
    """, unsafe_allow_html=True)
    
    if admin:
        label = "FINISH" if row['Status'] == "Playing" else "PLAY"
        if st.button(label, key=f"{key_prefix}_{row['Title']}", use_container_width=True):
            return True
    return False

# --- 5. NAVIGATION ---
page = st.sidebar.radio("Navigation", ["Dashboard", "Rankings", "Add Game", "Edit Database"])

# --- 6. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    col_l, col_r = st.columns([2.1, 0.9], gap="large")
    
    with col_l:
        st.markdown("<h5>Currently Playing</h5>", unsafe_allow_html=True)
        playing = df[df['Status'] == 'Playing']
        if not playing.empty:
            cols = st.columns(5)
            for i, (idx, row) in enumerate(playing.iterrows()):
                with cols[i % 5]:
                    if render_game_tile(row, admin=(st.session_state.admin_pin_input == ADMIN_PIN), key_prefix="dash"):
                        st.session_state.scoring_game = row['Title']; st.rerun()
        
        st.write("<br>", unsafe_allow_html=True)
        st.markdown("<h5>The Backlog</h5>", unsafe_allow_html=True)
        backlog = df[df['Status'] == 'Backlog']
        if not backlog.empty:
            cols = st.columns(6)
            for i, (idx, row) in enumerate(backlog.iterrows()):
                with cols[i % 6]:
                    if render_game_tile(row, admin=(st.session_state.admin_pin_input == ADMIN_PIN), key_prefix="back"):
                        df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                        # save_database(df) logic here
                        st.rerun()

    with col_r:
        st.markdown("<h5>Upcoming</h5>", unsafe_allow_html=True)
        upcoming = df[df['Status'] == 'Upcoming'].copy()
        if not upcoming.empty:
            u_cols = st.columns(2)
            for i, (idx, row) in enumerate(upcoming.head(8).iterrows()):
                with u_cols[i % 2]:
                    render_game_tile(row)

# --- 7. PAGE: RANKINGS ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played_sorted = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    
    col_rank, col_inspect = st.columns([2.1, 0.9], gap="large")
    
    with col_rank:
        st.markdown("<h5>The Top Ten</h5>", unsafe_allow_html=True)
        top_10 = played_sorted.head(10)
        cols = st.columns(5)
        for i, (idx, row) in enumerate(top_10.iterrows()):
            with cols[i % 5]:
                render_game_tile(row, show_score=True)
        
        if len(played_sorted) > 10:
            st.write("<br>", unsafe_allow_html=True)
            st.markdown("<h5>The Rest</h5>", unsafe_allow_html=True)
            st.dataframe(played_sorted.iloc[10:][['Title', 'Platform', 'Base_Score', 'Genre']], use_container_width=True, hide_index=True)

    with col_inspect:
        st.markdown("<h5>Deep Dive Inspector</h5>", unsafe_allow_html=True)
        selection = st.selectbox("Select Game:", ["-- Choose --"] + played_sorted['Title'].tolist(), label_visibility="collapsed")
        
        if selection != "-- Choose --":
            gd = played_sorted[played_sorted['Title'] == selection].iloc[0]
            st.markdown(f"""
                <div class="inspector-panel">
                    <img src="{gd['Cover_URL']}" style="width:100%; border-radius:8px; margin-bottom:15px;">
                    <h3 style="margin:0;">{selection}</h3>
                    <p style="color:#94A3B8; font-size:0.8rem;">{gd['Genre']} | {gd['Platform']}</p>
                    <hr style="opacity:0.1;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>Final Score: <b style="color:#9146FF;">{gd['Base_Score']}</b></span>
                        <span>Critic: <b>{gd['OpenCritic']}</b></span>
                    </div>
                    <p style="margin-top:15px; font-size:0.7rem; color:#94A3B8; letter-spacing:1px;">BREAKDOWN</p>
                    <div style="font-size:0.85rem;">
                        Gameplay: {gd['S_Gameplay']} | Visuals: {gd['S_Visuals']}<br>
                        Audio: {gd['S_Audio']} | Fun: {gd['S_Fun']}
                    </div>
                </div>
            """, unsafe_allow_html=True)

# Admin footer logic
st.sidebar.divider()
st.sidebar.text_input("Admin PIN", type="password", key="admin_pin_input")
