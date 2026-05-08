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

# --- 2. THE PRECISION GRID CSS ---
st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
        }
        
        /* Glass Containers: No Borders, Soft Shadows */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(12px);
            border-radius: 8px;
            border: none !important;
            padding: 8px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s ease;
        }
        div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
            background: rgba(255, 255, 255, 0.05) !important;
            transform: translateY(-2px);
        }

        /* LOCKED ASPECT RATIO FOR BOX ART */
        [data-testid="stImage"] img {
            border-radius: 4px;
            aspect-ratio: 3 / 4; /* Standard Game Box Art Ratio */
            object-fit: cover;
            width: 100%;
            display: block;
            margin: 0 auto;
        }

        /* Typography */
        h2 { letter-spacing: -1px; margin-bottom: 1.5rem !important; }
        h5 { 
            font-size: 0.75rem !important; 
            color: #94A3B8 !important; 
            letter-spacing: 1.5px; 
            text-transform: uppercase;
            margin-bottom: 0.8rem !important;
            border-left: 3px solid #9146FF;
            padding-left: 10px;
        }
        
        .game-title {
            font-size: 0.7rem !important;
            font-weight: 700;
            text-align: center;
            margin-top: 6px;
            margin-bottom: 0px;
            line-height: 1.2;
            color: #FFFFFF;
        }
        .game-sub {
            font-size: 0.6rem !important;
            text-align: center;
            color: #94A3B8;
            margin-bottom: 4px;
        }

        /* Compact Buttons */
        .stButton>button {
            padding: 1px 5px;
            font-size: 0.6rem !important;
            height: 22px;
            min-height: 22px;
            border-radius: 4px;
        }

        #MainMenu, footer, header {visibility: hidden;}
        .block-container { padding-top: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINES ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    for col in ['Base_Score', 'OpenCritic', 'Elo_Rating']:
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

# --- 5. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    playing = df[df['Status'] == 'Playing']
    backlog = df[df['Status'] == 'Backlog']
    upcoming = df[df['Status'] == 'Upcoming'].copy()
    played = df[df['Status'] == 'Played']

    # CORE HIERARCHY
    col_left, col_right = st.columns([2, 1], gap="large")

    # LEFT SIDE: CURRENTLY PLAYING & BACKLOG
    with col_left:
        # A. Currently Playing (5 per row)
        st.markdown("<h5>Currently Playing</h5>", unsafe_allow_html=True)
        if not playing.empty:
            p_grid = st.columns(5)
            for i, (idx, row) in enumerate(playing.iterrows()):
                with p_grid[i % 5]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='game-sub'>{row['Platform']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("FINISH", key=f"fin_{idx}", use_container_width=True):
                                st.session_state.scoring_game = row['Title']; st.rerun()
        else: st.caption("Nothing active.")

        st.write("<br>", unsafe_allow_html=True)

        # B. Backlog (6 per row)
        st.markdown("<h5>The Backlog</h5>", unsafe_allow_html=True)
        if not backlog.empty:
            b_grid = st.columns(6)
            for i, (idx, row) in enumerate(backlog.iterrows()):
                with b_grid[i % 6]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='game-sub'>{row['Platform']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("PLAY", key=f"bl_{idx}", use_container_width=True):
                                df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                                save_database(df); st.rerun()

    # RIGHT SIDE: UPCOMING
    with col_right:
        st.markdown("<h5>Upcoming Releases</h5>", unsafe_allow_html=True)
        if not upcoming.empty:
            upcoming['DateObj'] = pd.to_datetime(upcoming['ReleaseDate'], errors='coerce')
            upcoming = upcoming.sort_values('DateObj')
            u_grid = st.columns(4) # 4 per row in the 1/3 column
            for i, (_, row) in enumerate(upcoming.iterrows()):
                with u_grid[i % 4]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='game-sub'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)
        else: st.caption("No upcoming games.")

    # --- ANALYTICS & METRICS (Footer) ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("COMPLETED", len(played))
    m2.metric("AVERAGE SCORE", f"{played['Base_Score'].mean():.1f}" if not played.empty else "0")
    m3.metric("BACKLOG SIZE", len(backlog))
    m4.metric("TARGET", upcoming.iloc[0]['Title'] if not upcoming.empty else "N/A")

# --- REMAINING PAGES ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played_sorted = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    st.dataframe(played_sorted[['Title', 'Platform', 'Base_Score', 'OpenCritic']], use_container_width=True, hide_index=True)

elif page == "Add Game":
    with st.form("add"):
        t, p = st.text_input("Title"), st.text_input("Platform")
        st_select = st.selectbox("Status", ["Backlog", "Playing", "Upcoming"])
        if st.form_submit_button("Save"):
            url = fetch_cover_art(t)
            new_row = {'Title': t, 'Platform': p, 'Status': st_select, 'Cover_URL': url, 'ReleaseDate': str(datetime.date.today()), 'Base_Score': 0}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("Save Changes"): save_database(ed); st.success("Updated")

st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
