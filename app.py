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

# --- 2. PREMIUM AESTHETICS (CSS) ---
st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
        }
        
        /* Glassmorphism Containers */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            padding: 15px;
        }

        /* Metrics Styling */
        div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; color: #9146FF; }
        
        /* Image Styling */
        img {
            border-radius: 6px;
            transition: 0.3s ease;
        }
        img:hover {
            transform: scale(1.05);
        }

        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. MASTER CONFIG ---
GENRE_CONFIG = {
    "Action": [{"name": "Level Design"}, {"name": "Combat Feel"}],
    "RPG": [{"name": "Narrative"}, {"name": "Characters"}],
    "Roguelite": [{"name": "Replayability"}, {"name": "Clarity"}],
    "Online Multiplayer": [{"name": "Balance"}, {"name": "Community"}],
    "Horror": [{"name": "Atmosphere"}, {"name": "Tension"}],
    "Puzzle": [{"name": "Ingenuity"}, {"name": "Clarity"}],
    "Adventure": [{"name": "Exploration"}, {"name": "World-Building"}],
    "Strategy": [{"name": "Tactical Depth"}, {"name": "UI / UX"}]
}

MASTER_COLUMNS = [
    'Title', 'Status', 'ReleaseDate', 'Platform', 'Hype', 'Genre', 'Base_Score', 'OpenCritic', 'Elo_Rating', 'Cover_URL',
    'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'Bonus_1_Name', 'S_Bonus_1', 'Bonus_2_Name', 'S_Bonus_2'
]

# --- 4. DATA ENGINES ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    df['ReleaseDate'] = df['ReleaseDate'].astype(str)
else:
    df = pd.DataFrame(columns=MASTER_COLUMNS)

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

# --- 5. SIDEBAR ---
if "admin_pin_input" not in st.session_state: st.session_state.admin_pin_input = ""
available_pages = ["Dashboard", "Rankings"]
if st.session_state.admin_pin_input == ADMIN_PIN:
    available_pages.extend(["Add Game", "The Arena", "Edit Database"])

page = st.sidebar.radio("Navigation", available_pages)

# --- 6. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h1 style='color: #9146FF;'>COMMAND CENTER</h1>", unsafe_allow_html=True)
    
    played_games = df[df['Status'] == 'Played']
    upcoming_all = df[df['Status'] == 'Upcoming'].copy()
    
    dash_left, dash_right = st.columns([1, 1], gap="large")
    
    with dash_left:
        st.subheader("⚡ Currently Playing")
        playing_games = df[df['Status'] == 'Playing']
        
        if 'scoring_game' in st.session_state and st.session_state.admin_pin_input == ADMIN_PIN:
            # Scoring Form
            finish_target = st.session_state.scoring_game
            st.markdown(f"**Finalizing:** {finish_target}")
            if st.button("Cancel"): del st.session_state.scoring_game; st.rerun()
            
            with st.form("score_active"):
                g_play = st.slider("Gameplay", 1.0, 10.0, 7.0)
                vis = st.slider("Visuals", 1.0, 10.0, 7.0)
                aud = st.slider("Audio", 1.0, 10.0, 7.0)
                fun = st.slider("Fun", 1.0, 10.0, 7.0)
                if st.form_submit_button("Score Game"):
                    final_score = round((g_play + vis + aud + fun) * 2.5, 1)
                    df.loc[df['Title'] == finish_target, ['Status', 'Base_Score', 'Elo_Rating']] = ['Played', final_score, final_score*15]
                    save_database(df); del st.session_state.scoring_game; st.rerun()
        else:
            if not playing_games.empty:
                for idx, row in playing_games.iterrows():
                    with st.container(border=True):
                        # Row-based layout: Thumbnail - Info - Button
                        c1, c2, c3 = st.columns([0.6, 2, 1])
                        with c1:
                            if row['Cover_URL']: st.image(row['Cover_URL'], width=60)
                        with c2:
                            st.markdown(f"**{row['Title']}**  \n`{row['Platform']}`")
                        with c3:
                            if st.session_state.admin_pin_input == ADMIN_PIN:
                                if st.button("Finish", key=f"fin_{idx}", use_container_width=True):
                                    st.session_state.scoring_game = row['Title']; st.rerun()
            else: st.info("No active games.")

        st.write("")
        st.subheader("📚 Backlog")
        backlog_games = df[df['Status'] == 'Backlog']
        if not backlog_games.empty:
            for idx, row in backlog_games.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row['Title']}** ({row['Platform']})")
                    if st.session_state.admin_pin_input == ADMIN_PIN:
                        if c2.button("Play", key=f"p_{idx}"):
                            df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                            save_database(df); st.rerun()

    with dash_right:
        st.subheader("🗓️ Upcoming Releases")
        if not upcoming_all.empty:
            upcoming_all['DateObj'] = pd.to_datetime(upcoming_all['ReleaseDate'], errors='coerce')
            upcoming_all = upcoming_all.sort_values('DateObj')
            
            # 4 columns for a tight grid
            grid_cols = st.columns(4)
            for i, (_, row) in enumerate(upcoming_all.head(8).iterrows()):
                with grid_cols[i % 4]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                        st.markdown(f"<p style='font-size:0.75rem; font-weight:bold; margin-bottom:0;'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:0.65rem; color: #9146FF; margin-top:0;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)
        else: st.info("Clear skies ahead.")

    # --- Analytics & Stats ---
    st.divider()
    if not played_games.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            fig1 = px.pie(played_games, names='Genre', hole=0.4, title="Genre Split", height=300, template="plotly_dark")
            fig1.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            played_games['Year'] = played_games['ReleaseDate'].astype(str).str[:4]
            yearly = played_games.groupby('Year')['Base_Score'].mean().reset_index()
            fig2 = px.bar(yearly, x='Year', y='Base_Score', title="Avg Score/Year", height=300, template="plotly_dark")
            fig2.update_traces(marker_color='#9146FF')
            fig2.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig2, use_container_width=True)
        with c3:
            fig3 = px.scatter(played_games, x='OpenCritic', y='Base_Score', hover_name='Title', title="Me vs Critics", height=300, template="plotly_dark")
            fig3.update_layout(margin=dict(t=30, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig3, use_container_width=True)

    st.subheader("📍 Stats")
    m1, m2, m3 = st.columns(3)
    m1.metric("Completed", len(played_games))
    m2.metric("Average Score", f"{played_games['Base_Score'].mean():.1f}" if not played_games.empty else "0")
    m3.metric("Next Up", upcoming_all.iloc[0]['Title'] if not upcoming_all.empty else "N/A")

# --- 7. PAGE: RANKINGS ---
elif page == "Rankings":
    st.markdown("<h1 style='color: #9146FF;'>THE RANKINGS</h1>", unsafe_allow_html=True)
    played = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    
    if not played.empty:
        top_3 = played.head(3)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top_3.iterrows()):
            with cols[i]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                    st.markdown(f"<p style='text-align:center; font-weight:bold;'>{row['Title']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align:center; color:#9146FF;'>{row['Base_Score']}</h3>", unsafe_allow_html=True)
        st.divider()
        st.dataframe(played[['Title', 'Platform', 'Base_Score', 'OpenCritic']], use_container_width=True, hide_index=True)

# --- 8. ADMIN TOOLS ---
elif page == "Add Game":
    st.title("Add Game")
    with st.form("add"):
        t = st.text_input("Title")
        p = st.text_input("Platform")
        if st.form_submit_button("Save"):
            art = fetch_cover_art(t)
            new_row = {col: 0 if 'Score' in col else "" for col in MASTER_COLUMNS}
            new_row.update({'Title': t, 'Platform': p, 'Status': 'Backlog', 'Cover_URL': art, 'ReleaseDate': str(datetime.date.today())})
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    st.title("Database Edit")
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("Save Changes"): save_database(ed); st.success("Saved!")

# Always keep the Admin PIN input at bottom of sidebar
st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
