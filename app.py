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

# --- 2. THE PRECISION UI (FIXED GRID & INSPECTOR) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
            font-family: 'Inter', sans-serif;
        }
        
        /* Glass Containers: Unified Height Logic */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.02) !important;
            backdrop-filter: blur(12px);
            border-radius: 10px;
            border: none !important;
            padding: 12px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            height: 310px !important; /* Fixed total tile height */
            overflow: hidden;
        }

        /* Standardized Box Art Ratio & Size */
        [data-testid="stImage"] img {
            border-radius: 4px;
            aspect-ratio: 3 / 4;
            object-fit: cover;
            width: 100%;
            height: 180px !important; /* Fixed image height */
        }

        /* Typography */
        h2 { font-weight: 800 !important; letter-spacing: -1.5px !important; color: #FFFFFF !important; margin-bottom: 1.5rem !important; }
        h5 { 
            font-size: 0.7rem !important; font-weight: 800 !important; color: #94A3B8 !important; 
            letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1rem !important;
            border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;
        }
        
        .game-title { font-size: 0.7rem !important; font-weight: 600; text-align: center; margin-top: 8px; color: #F8FAFC; line-height: 1.2; height: 32px; overflow: hidden; }
        .game-score { font-size: 1rem !important; font-weight: 800; text-align: center; color: #9146FF; margin-top: 2px; }
        .inspector-stat { font-size: 0.8rem; font-weight: 600; color: #94A3B8; margin-bottom: -5px; }

        #MainMenu, footer, header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    cols_to_fix = ['Base_Score', 'OpenCritic', 'Elo_Rating', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'S_Bonus_1', 'S_Bonus_2']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
else:
    df = pd.DataFrame(columns=['Title', 'Status', 'ReleaseDate', 'Platform', 'Cover_URL', 'Base_Score', 'OpenCritic', 'Genre'])

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

# --- 4. NAVIGATION ---
if "admin_pin_input" not in st.session_state: st.session_state.admin_pin_input = ""
pages = ["Dashboard", "Rankings"]
if st.session_state.admin_pin_input == ADMIN_PIN:
    pages.extend(["Add Game", "Edit Database"])
page = st.sidebar.radio("Navigation", pages)

# --- 5. PAGE: DASHBOARD (Syncing Tile Logic) ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    playing = df[df['Status'] == 'Playing']
    backlog = df[df['Status'] == 'Backlog']
    upcoming = df[df['Status'] == 'Upcoming'].copy()
    played = df[df['Status'] == 'Played']

    col_left, col_right = st.columns([2.1, 0.9], gap="large")

    with col_left:
        st.markdown("<h5>Currently Playing</h5>", unsafe_allow_html=True)
        if not playing.empty:
            p_grid = st.columns(5)
            for i, (idx, row) in enumerate(playing.iterrows()):
                with p_grid[i % 5]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("FINISH", key=f"fin_{idx}", use_container_width=True):
                                st.session_state.scoring_game = row['Title']; st.rerun()

        st.markdown("<h5>The Backlog</h5>", unsafe_allow_html=True)
        if not backlog.empty:
            b_grid = st.columns(6)
            for i, (idx, row) in enumerate(backlog.iterrows()):
                with b_grid[i % 6]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("PLAY", key=f"bl_{idx}", use_container_width=True):
                                df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                                save_database(df); st.rerun()

    with col_right:
        st.markdown("<h5>Upcoming</h5>", unsafe_allow_html=True)
        if not upcoming.empty:
            upcoming['DateObj'] = pd.to_datetime(upcoming['ReleaseDate'], errors='coerce')
            upcoming = upcoming.sort_values('DateObj')
            u_grid = st.columns(2)
            for i, (_, row) in enumerate(upcoming.head(8).iterrows()):
                with u_grid[i % 2]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title' style='height:20px;'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:0.6rem; color:#9146FF; text-align:center;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)

# --- 6. PAGE: RANKINGS (SIDE-BY-SIDE INSPECTOR) ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played_sorted = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    
    if not played_sorted.empty:
        col_rank, col_inspect = st.columns([2.1, 0.9], gap="large")

        with col_rank:
            st.markdown("<h5>The Top Ten</h5>", unsafe_allow_html=True)
            top_10 = played_sorted.head(10)
            r_grid = st.columns(5) 
            for i, (_, row) in enumerate(top_10.iterrows()):
                with r_grid[i % 5]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='game-score'>{row['Base_Score']}</p>", unsafe_allow_html=True)
            
            st.write("<br>", unsafe_allow_html=True)
            if len(played_sorted) > 10:
                st.markdown("<h5>The Rest</h5>", unsafe_allow_html=True)
                st.dataframe(played_sorted.iloc[10:][['Title', 'Platform', 'Base_Score', 'OpenCritic', 'Genre']], use_container_width=True, hide_index=True)

        with col_inspect:
            st.markdown("<h5>Deep Dive Inspector</h5>", unsafe_allow_html=True)
            sq = st.selectbox("Select Game:", ["-- Choose --"] + played_sorted['Title'].tolist(), label_visibility="collapsed")
            
            if sq != "-- Choose --":
                gd = played_sorted[played_sorted['Title'] == sq].iloc[0]
                with st.container(border=True):
                    if gd['Cover_URL']: st.image(gd['Cover_URL'], use_container_width=True)
                    st.markdown(f"<h4 style='margin-bottom:0;'>{sq}</h4>", unsafe_allow_html=True)
                    st.caption(f"{gd['Genre']} | {gd['Platform']}")
                    
                    st.divider()
                    # Breakdown
                    c1, c2 = st.columns(2)
                    c1.metric("Final", gd['Base_Score'])
                    c2.metric("Critic", gd['OpenCritic'])
                    
                    st.markdown("<p class='inspector-stat'>CORE ELEMENTS</p>", unsafe_allow_html=True)
                    st.write(f"Gameplay: **{gd['S_Gameplay']}** | Visuals: **{gd['S_Visuals']}**")
                    st.write(f"Audio: **{gd['S_Audio']}** | Fun: **{gd['S_Fun']}**")
                    
                    if gd['Bonus_1_Name'] != "TBD":
                        st.markdown("<p class='inspector-stat'>GENRE SPECIALTY</p>", unsafe_allow_html=True)
                        st.write(f"{gd['Bonus_1_Name']}: **{gd['S_Bonus_1']}**")
                        st.write(f"{gd['Bonus_2_Name']}: **{gd['S_Bonus_2']}**")

# --- 7. ADMIN ---
elif page == "Add Game":
    st.markdown("<h2>ADD GAME</h2>", unsafe_allow_html=True)
    with st.form("add_game"):
        t, p = st.text_input("Title"), st.text_input("Platform")
        st_select = st.selectbox("Status", ["Backlog", "Playing", "Upcoming"])
        if st.form_submit_button("SAVE"):
            url = fetch_cover_art(t)
            new_row = {col: 0 if 'Score' in col else "" for col in df.columns}
            new_row.update({'Title': t, 'Platform': p, 'Status': st_select, 'Cover_URL': url, 'ReleaseDate': str(datetime.date.today())})
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    st.title("Database")
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("Apply"): save_database(ed); st.success("Updated")

st.sidebar.divider()
st.sidebar.text_input("Admin PIN", type="password", key="admin_pin_input")
