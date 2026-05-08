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

# --- 2. ULTRA-CLEAN CSS ---
st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
        }
        
        /* Containers: No borders, subtle depth */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.02) !important;
            backdrop-filter: blur(12px);
            border-radius: 10px;
            border: none !important;
            padding: 12px !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }

        /* Enforce uniformity on Box Art */
        [data-testid="stImage"] img {
            border-radius: 4px;
            width: 100%;
            height: 160px; /* Fixed height for consistency */
            object-fit: cover;
            margin-bottom: 5px;
        }

        /* Typography */
        h2 { letter-spacing: -1px; margin-bottom: 1.5rem !important; }
        h5 { font-size: 0.8rem !important; color: #94A3B8 !important; letter-spacing: 1px; margin-top: 1rem; }
        
        .game-title {
            font-size: 0.75rem !important;
            font-weight: 600;
            text-align: center;
            margin-top: 5px;
            line-height: 1.2;
            min-height: 30px;
        }

        /* Sidebar/Metric Fixes */
        div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 800; color: #9146FF; }
        #MainMenu, footer, header {visibility: hidden;}
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

# --- 5. DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    # Filter Data
    playing = df[df['Status'] == 'Playing']
    backlog = df[df['Status'] == 'Backlog']
    upcoming = df[df['Status'] == 'Upcoming'].copy()
    played = df[df['Status'] == 'Played']

    # 1. CURRENTLY PLAYING
    st.markdown("<h5>CURRENTLY PLAYING</h5>", unsafe_allow_html=True)
    if not playing.empty:
        p_cols = st.columns(6) # Smaller tiles
        for i, (idx, row) in enumerate(playing.iterrows()):
            with p_cols[i % 6]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'])
                    st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                    if st.session_state.admin_pin_input == ADMIN_PIN:
                        if st.button("FINISH", key=f"fin_{idx}", use_container_width=True):
                            st.session_state.scoring_game = row['Title']; st.rerun()
    else: st.caption("No active sessions.")

    # 2. UPCOMING RELEASES (Horizontal Row)
    st.markdown("<h5>UPCOMING RELEASES</h5>", unsafe_allow_html=True)
    if not upcoming.empty:
        upcoming['DateObj'] = pd.to_datetime(upcoming['ReleaseDate'], errors='coerce')
        upcoming = upcoming.sort_values('DateObj')
        u_cols = st.columns(6)
        for i, (_, row) in enumerate(upcoming.head(6).iterrows()):
            with u_cols[i % 6]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'])
                    st.markdown(f"<p class='game-title'>{row['Title']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size:0.6rem; color:#9146FF; text-align:center;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)

    # 3. BACKLOG
    st.markdown("<h5>BACKLOG</h5>", unsafe_allow_html=True)
    if not backlog.empty:
        b_cols = st.columns(8) # High density for backlog
        for i, (idx, row) in enumerate(backlog.iterrows()):
            with b_cols[i % 8]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'])
                    st.markdown(f"<p class='game-title' style='opacity:0.7;'>{row['Title']}</p>", unsafe_allow_html=True)
                    if st.session_state.admin_pin_input == ADMIN_PIN:
                        if st.button("PLAY", key=f"bl_{idx}", use_container_width=True):
                            df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                            save_database(df); st.rerun()

    # 4. ANALYTICS (Full Width)
    st.divider()
    if not played.empty:
        st.markdown("<h5>ANALYTICS</h5>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        chart_style = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color="white", size=10), margin=dict(t=30, b=10, l=10, r=10))
        
        with c1:
            fig1 = px.pie(played, names='Genre', hole=0.6, title="GENRE DISTRO", template="plotly_dark")
            fig1.update_layout(chart_style)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            played['Year'] = played['ReleaseDate'].astype(str).str[:4]
            yearly = played.groupby('Year')['Base_Score'].mean().reset_index()
            fig2 = px.bar(yearly, x='Year', y='Base_Score', title="SCORE TREND", template="plotly_dark")
            fig2.update_traces(marker_color='#9146FF')
            fig2.update_layout(chart_style)
            st.plotly_chart(fig2, use_container_width=True)
        with c3:
            fig3 = px.scatter(played, x='OpenCritic', y='Base_Score', hover_name='Title', title="VS CRITICS", template="plotly_dark")
            fig3.update_traces(marker=dict(size=8, color='#9146FF'))
            fig3.update_layout(chart_style)
            st.plotly_chart(fig3, use_container_width=True)

    # 5. METRICS
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("COMPLETED", len(played))
    m2.metric("AVERAGE", f"{played['Base_Score'].mean():.1f}" if not played.empty else "0")
    m3.metric("BACKLOG", len(backlog))
    m4.metric("NEXT UP", upcoming.iloc[0]['Title'] if not upcoming.empty else "TBD")

# --- OTHER PAGES ---
elif page == "Rankings":
    st.markdown("<h2>HALL OF FAME</h2>", unsafe_allow_html=True)
    played = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    if not played.empty:
        st.dataframe(played[['Title', 'Platform', 'Base_Score', 'OpenCritic']], use_container_width=True, hide_index=True)

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
    if st.button("Apply Changes"): save_database(ed); st.success("Database Sync Complete")

st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
