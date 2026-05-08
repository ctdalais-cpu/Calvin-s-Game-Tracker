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

# --- 2. MASTER UI POLISH (UNIFORM GRID & CENTERING) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
            font-family: 'Inter', sans-serif;
        }
        
        /* Force Uniform Tiles */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.02) !important;
            backdrop-filter: blur(12px);
            border-radius: 10px;
            border: none !important;
            padding: 12px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            min-height: 320px; /* Locked Height */
            max-height: 320px;
        }

        /* Standardized Box Art Ratio */
        [data-testid="stImage"] img {
            border-radius: 5px;
            aspect-ratio: 3 / 4;
            object-fit: cover;
            width: 100%;
            max-width: 160px; /* Prevents oversized images */
        }

        /* Centered Typography */
        h2 { font-weight: 800 !important; letter-spacing: -1.5px !important; color: #FFFFFF !important; text-align: left; }
        h5 { 
            font-size: 0.7rem !important; font-weight: 800 !important; color: #94A3B8 !important; 
            letter-spacing: 2px; text-transform: uppercase; margin-bottom: 1rem !important;
            border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;
        }
        
        .game-title { font-size: 0.75rem !important; font-weight: 600; text-align: center; margin-top: 10px; color: #F8FAFC; line-height: 1.2; width: 100%; }
        .game-sub { font-size: 0.65rem !important; text-align: center; color: #64748B; width: 100%; margin-bottom: 5px; }
        .game-score { font-size: 1rem !important; font-weight: 800; text-align: center; color: #9146FF; margin-top: 2px; }

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
    for col in ['Base_Score', 'OpenCritic', 'Elo_Rating', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun']:
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

    col_left, col_right = st.columns([2.1, 0.9], gap="large")

    with col_left:
        st.markdown("<h5>Currently Playing</h5>", unsafe_allow_html=True)
        if not playing.empty:
            p_grid = st.columns(5)
            for i, (idx, row) in enumerate(playing.iterrows()):
                with p_grid[i % 5]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p><p class='game-sub'>{row['Platform']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("FINISH", key=f"fin_{idx}", use_container_width=True):
                                st.session_state.scoring_game = row['Title']; st.rerun()
        else: st.caption("Nothing active.")

        st.write("<br>", unsafe_allow_html=True)

        st.markdown("<h5>The Backlog</h5>", unsafe_allow_html=True)
        if not backlog.empty:
            b_grid = st.columns(6)
            for i, (idx, row) in enumerate(backlog.iterrows()):
                with b_grid[i % 6]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title'>{row['Title']}</p><p class='game-sub'>{row['Platform']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("PLAY", key=f"bl_{idx}", use_container_width=True):
                                df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                                save_database(df); st.rerun()

    with col_right:
        st.markdown("<h5>Upcoming Releases</h5>", unsafe_allow_html=True)
        if not upcoming.empty:
            upcoming['DateObj'] = pd.to_datetime(upcoming['ReleaseDate'], errors='coerce')
            upcoming = upcoming.sort_values('DateObj')
            u_grid = st.columns(3)
            for i, (_, row) in enumerate(upcoming.head(12).iterrows()):
                with u_grid[i % 3]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                        st.markdown(f"<p class='game-title' style='font-size:0.6rem;'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p class='game-sub' style='color:#9146FF;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)

    # Analytics Section (Footer)
    st.divider()
    if not played.empty:
        st.markdown("<h5>Insights</h5>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c_layout = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white", size=10), margin=dict(t=30, b=10, l=10, r=10))
        with c1:
            fig1 = px.pie(played, names='Genre', hole=0.5, title="GENRE DISTRO", template="plotly_dark")
            fig1.update_layout(c_layout); st.plotly_chart(fig1, use_container_width=True)
        with c2:
            played['Year'] = played['ReleaseDate'].astype(str).str[:4]
            yearly = played.groupby('Year')['Base_Score'].mean().reset_index()
            fig2 = px.bar(yearly, x='Year', y='Base_Score', title="SCORE TREND", template="plotly_dark")
            fig2.update_traces(marker_color='#9146FF'); fig2.update_layout(c_layout); st.plotly_chart(fig2, use_container_width=True)
        with c3:
            fig3 = px.scatter(played, x='OpenCritic', y='Base_Score', hover_name='Title', title="ME VS CRITICS", template="plotly_dark")
            fig3.update_traces(marker=dict(size=8, color='#9146FF')); fig3.update_layout(c_layout); st.plotly_chart(fig3, use_container_width=True)

# --- 6. PAGE: RANKINGS (RESTORED INSPECTOR) ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played_sorted = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    
    if not played_sorted.empty:
        # Inspector Detail View
        with st.expander("🔍 Deep Dive Inspector"):
            sq = st.selectbox("Select game to breakdown:", ["-- Choose --"] + played_sorted['Title'].tolist(), label_visibility="collapsed")
            if sq != "-- Choose --":
                gd = played_sorted[played_sorted['Title'] == sq].iloc[0]
                ic1, ic2 = st.columns([1, 2])
                with ic1:
                    if gd['Cover_URL']: st.image(gd['Cover_URL'], width=200)
                with ic2:
                    st.markdown(f"### {sq}")
                    st.write(f"**Platform:** {gd['Platform']} | **Genre:** {gd['Genre']}")
                    m_c1, m_c2, m_c3 = st.columns(3)
                    m_c1.metric("Final Score", gd['Base_Score'])
                    m_c2.metric("Critics", gd['OpenCritic'])
                    m_c3.metric("Fun Factor", f"{gd['S_Fun']}/10")
                    st.progress(gd['Base_Score'] / 100)

        # Top 10 Visual Grid
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
            st.markdown("<h5>The Rest of the Pack</h5>", unsafe_allow_html=True)
            rest_of_pack = played_sorted.iloc[10:]
            st.dataframe(rest_of_pack[['Title', 'Platform', 'Base_Score', 'OpenCritic', 'Genre']], use_container_width=True, hide_index=True)

# --- 7. ADMIN ---
elif page == "Add Game":
    st.markdown("<h2>ADD TO LIBRARY</h2>", unsafe_allow_html=True)
    with st.form("add_game"):
        t, p = st.text_input("Title"), st.text_input("Platform")
        st_select = st.selectbox("Status", ["Backlog", "Playing", "Upcoming"])
        if st.form_submit_button("SAVE GAME"):
            url = fetch_cover_art(t)
            new_row = {'Title': t, 'Platform': p, 'Status': st_select, 'Cover_URL': url, 'ReleaseDate': str(datetime.date.today()), 'Base_Score': 0}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    st.markdown("<h2>DATABASE MANAGEMENT</h2>", unsafe_allow_html=True)
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("SAVE CHANGES"): save_database(ed); st.success("Database Updated")

st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
