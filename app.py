import streamlit as st
import pandas as pd
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- 1. AUTH & CONFIG ---
CLIENT_ID = st.secrets["TWITCH_CLIENT_ID"]
CLIENT_SECRET = st.secrets["TWITCH_CLIENT_SECRET"]
ADMIN_PIN = st.secrets["ADMIN_PIN"]

st.set_page_config(page_title="Game Hub Pro", layout="wide", initial_sidebar_state="expanded")

# --- 2. THE STABLE UI ENGINE (CSS) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
            font-family: 'Inter', sans-serif;
        }
        
        .game-tile {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(12px);
            border-radius: 10px;
            padding: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 330px; /* Increased height to fit all data */
            margin-bottom: 20px;
            transition: transform 0.2s ease;
        }

        .tile-img {
            width: 100%;
            height: 180px;
            object-fit: cover;
            border-radius: 5px;
            margin-bottom: 10px;
        }

        .tile-title {
            font-size: 0.85rem;
            font-weight: 700;
            text-align: center;
            color: #FFFFFF;
            line-height: 1.2;
            height: 40px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .tile-info {
            font-size: 0.7rem;
            color: #94A3B8;
            margin-top: 4px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .tile-score {
            font-size: 1.2rem;
            font-weight: 800;
            color: #9146FF;
            margin-top: 8px;
        }

        /* Inspector Refinement */
        .inspector-box {
            background: rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .score-pill {
            background: rgba(145, 70, 255, 0.1);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid rgba(145, 70, 255, 0.2);
        }

        h2 { font-weight: 800 !important; letter-spacing: -1.5px !important; margin-bottom: 2rem !important; }
        h5 { 
            font-size: 0.75rem !important; font-weight: 800 !important; color: #94A3B8 !important; 
            letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1.5rem !important;
            border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 8px;
        }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA & API ENGINES ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

def load_data():
    records = sheet.get_all_records()
    if records:
        data = pd.DataFrame(records)
        num_cols = ['Base_Score', 'OpenCritic', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'S_Bonus_1', 'S_Bonus_2']
        for col in num_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
        return data
    return pd.DataFrame(columns=['Title', 'Status', 'ReleaseDate', 'Platform', 'Cover_URL', 'Base_Score', 'OpenCritic', 'Genre'])

df = load_data()

def save_database(dataframe):
    dataframe = dataframe.fillna("")
    data_to_write = [dataframe.columns.values.tolist()] + dataframe.values.tolist()
    sheet.clear()
    sheet.update(data_to_write)

def fetch_cover_art(title):
    try:
        auth_res = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials")
        access_token = auth_res.json().get('access_token')
        headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
        data = f'search "{title}"; fields cover.url; limit 1;'
        res = requests.post("https://api.igdb.com/v4/games", headers=headers, data=data)
        game_data = res.json()
        if game_data and 'cover' in game_data[0]:
            return "https:" + game_data[0]['cover']['url'].replace("t_thumb", "t_cover_big")
        return ""
    except: return ""

# --- 4. TILE RENDERER ---
def draw_tile(row, extra_info=None, show_score=False):
    score_html = f"<div class='tile-score'>{row['Base_Score']}</div>" if show_score else ""
    # We always show Platform unless extra_info overrides it (like for Release Date)
    display_info = extra_info if extra_info else row['Platform']
    
    st.markdown(f"""
        <div class="game-tile">
            <img src="{row['Cover_URL']}" class="tile-img">
            <div class="tile-title">{row['Title']}</div>
            <div class="tile-info">{display_info}</div>
            {score_html}
        </div>
    """, unsafe_allow_html=True)

# --- 5. NAVIGATION ---
if "admin_pin_input" not in st.session_state: st.session_state.admin_pin_input = ""
pages = ["Dashboard", "Rankings"]
if st.session_state.admin_pin_input == ADMIN_PIN:
    pages.extend(["Add Game", "Edit Database"])
page = st.sidebar.radio("Navigation", pages)

# --- 6. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    col_l, col_r = st.columns([2.2, 0.8], gap="large") # Restored size hierarchy
    
    with col_l:
        st.markdown("<h5>Currently Playing</h5>", unsafe_allow_html=True)
        playing = df[df['Status'] == 'Playing']
        if not playing.empty:
            p_cols = st.columns(5)
            for i, (idx, row) in enumerate(playing.iterrows()):
                with p_cols[i % 5]:
                    draw_tile(row)
                    if st.session_state.admin_pin_input == ADMIN_PIN:
                        if st.button("FINISH", key=f"f_{idx}", use_container_width=True):
                            st.session_state.scoring_game = row['Title']; st.rerun()
        
        st.write("<br>", unsafe_allow_html=True)
        st.markdown("<h5>The Backlog</h5>", unsafe_allow_html=True)
        backlog = df[df['Status'] == 'Backlog']
        if not backlog.empty:
            b_cols = st.columns(6)
            for i, (idx, row) in enumerate(backlog.iterrows()):
                with b_cols[i % 6]:
                    draw_tile(row)
                    if st.session_state.admin_pin_input == ADMIN_PIN:
                        if st.button("PLAY", key=f"p_{idx}", use_container_width=True):
                            df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                            save_database(df); st.rerun()

    with col_r:
        st.markdown("<h5>Upcoming</h5>", unsafe_allow_html=True)
        upcoming = df[df['Status'] == 'Upcoming'].copy()
        if not upcoming.empty:
            upcoming['DateObj'] = pd.to_datetime(upcoming['ReleaseDate'], errors='coerce')
            upcoming = upcoming.sort_values('DateObj')
            u_cols = st.columns(2)
            for i, (_, row) in enumerate(upcoming.head(10).iterrows()):
                with u_cols[i % 2]:
                    # For upcoming, we show Release Date instead of Platform in the 'info' slot
                    draw_tile(row, extra_info=row['ReleaseDate'])

# --- 7. PAGE: RANKINGS ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played_sorted = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    
    if not played_sorted.empty:
        col_rank, col_inspect = st.columns([2.1, 0.9], gap="large")
        
        with col_rank:
            st.markdown("<h5>The Top Ten</h5>", unsafe_allow_html=True)
            top_10 = played_sorted.head(10)
            r_cols = st.columns(5)
            for i, (_, row) in enumerate(top_10.iterrows()):
                with r_cols[i % 5]:
                    draw_tile(row, show_score=True)
            
            st.write("<br>", unsafe_allow_html=True)
            if len(played_sorted) > 10:
                st.markdown("<h5>The Library</h5>", unsafe_allow_html=True)
                st.dataframe(played_sorted.iloc[10:][['Title', 'Platform', 'Base_Score', 'Genre']], use_container_width=True, hide_index=True)

        with col_inspect:
            st.markdown("<h5>Deep Dive Inspector</h5>", unsafe_allow_html=True)
            selection = st.selectbox("Select Game:", ["-- Choose --"] + played_sorted['Title'].tolist(), label_visibility="collapsed")
            
            if selection != "-- Choose --":
                gd = played_sorted[played_sorted['Title'] == selection].iloc[0]
                st.markdown(f"""
                    <div class="inspector-box">
                        <img src="{gd['Cover_URL']}" style="width:100%; border-radius:8px; margin-bottom:20px;">
                        <h3 style="margin:0; font-size: 1.5rem;">{selection}</h3>
                        <p style="color:#94A3B8; font-size:0.9rem; margin-bottom:20px;">{gd['Genre']} | {gd['Platform']}</p>
                        
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px;">
                            <div class="score-pill"><small style="color:#94A3B8;">SCORE</small><br><b style="font-size:1.6rem; color:#9146FF;">{gd['Base_Score']}</b></div>
                            <div class="score-pill"><small style="color:#94A3B8;">CRITIC</small><br><b style="font-size:1.6rem;">{gd['OpenCritic']}</b></div>
                        </div>

                        <p style="font-size:0.8rem; color:#94A3B8; letter-spacing:2px; font-weight:800; margin-bottom:15px;">FULL BREAKDOWN</p>
                        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size:1rem; font-weight:600;">
                            <div>Gameplay: <span style="color:#9146FF;">{gd['S_Gameplay']}</span></div>
                            <div>Visuals: <span style="color:#9146FF;">{gd['S_Visuals']}</span></div>
                            <div>Audio: <span style="color:#9146FF;">{gd['S_Audio']}</span></div>
                            <div>Fun: <span style="color:#9146FF;">{gd['S_Fun']}</span></div>
                        </div>
                        <hr style="opacity:0.1; margin: 20px 0;">
                        <p style="font-size:0.8rem; color:#94A3B8; letter-spacing:2px; font-weight:800; margin-bottom:10px;">GENRE SPECIALTY</p>
                        <div style="font-size:1rem; font-weight:600;">
                            <div>{gd['Bonus_1_Name']}: <span style="color:#9146FF;">{gd['S_Bonus_1']}</span></div>
                            <div>{gd['Bonus_2_Name']}: <span style="color:#9146FF;">{gd['S_Bonus_2']}</span></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
