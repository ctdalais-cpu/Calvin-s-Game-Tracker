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

# --- 2. BORDERLESS DEPTH AESTHETIC (CSS) ---
st.markdown("""
    <style>
        /* Overall App Background */
        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
        }
        
        /* Clean, Borderless Containers with Shadow */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.03) !important;
            backdrop-filter: blur(10px);
            border-radius: 12px;
            border: none !important;
            padding: 10px !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            transition: transform 0.3s ease, background 0.3s ease;
        }

        /* Hover Effect for Depth */
        div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
            background: rgba(255, 255, 255, 0.06) !important;
            transform: translateY(-3px);
        }

        /* Image Constraints to prevent "Ugly Large" look */
        [data-testid="stImage"] img {
            border-radius: 6px;
            margin-bottom: 8px;
            object-fit: cover;
        }

        /* Metric Styling */
        div[data-testid="stMetricValue"] { 
            font-size: 1.8rem; 
            font-weight: 800;
            color: #9146FF !important; 
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #94A3B8;
        }

        /* Typography */
        h2, h3, h5 {
            letter-spacing: -0.5px;
            font-weight: 700 !important;
        }

        /* Button Styling */
        .stButton>button {
            border-radius: 6px;
            border: none;
            background-color: rgba(255,255,255,0.1);
            color: white;
            font-size: 0.7rem;
            font-weight: 600;
            transition: 0.2s;
        }
        .stButton>button:hover {
            background-color: #9146FF;
            color: white;
        }

        /* Hide Streamlit Clutter */
        #MainMenu, footer, header {visibility: hidden;}
        .block-container { padding-top: 2rem; }
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

# --- 4. SIDEBAR NAVIGATION ---
if "admin_pin_input" not in st.session_state: st.session_state.admin_pin_input = ""
pages = ["Dashboard", "Rankings"]
if st.session_state.admin_pin_input == ADMIN_PIN:
    pages.extend(["Add Game", "Edit Database"])
page = st.sidebar.radio("Navigation", pages)

# --- 5. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2>COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    played_games = df[df['Status'] == 'Played']
    playing_games = df[df['Status'] == 'Playing']
    backlog_games = df[df['Status'] == 'Backlog']
    upcoming_games = df[df['Status'] == 'Upcoming'].copy()
    
    col_main, col_side = st.columns([2.5, 1], gap="medium")
    
    with col_main:
        st.markdown("##### CURRENTLY PLAYING")
        if not playing_games.empty:
            p_cols = st.columns(4) 
            for i, (idx, row) in enumerate(playing_games.iterrows()):
                with p_cols[i % 4]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], width='stretch')
                        st.markdown(f"<p style='font-size:0.85rem; font-weight:600; text-align:center; margin-bottom:4px;'>{row['Title']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("FINISH", key=f"fin_{idx}", width='stretch'):
                                st.session_state.scoring_game = row['Title']; st.rerun()
        else: st.info("Nothing currently active.")

        st.write("<br>", unsafe_allow_html=True)
        st.markdown("##### BACKLOG")
        if not backlog_games.empty:
            b_cols = st.columns(5) 
            for i, (idx, row) in enumerate(backlog_games.iterrows()):
                with b_cols[i % 5]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], width='stretch')
                        st.markdown(f"<p style='font-size:0.75rem; text-align:center; opacity:0.8;'>{row['Title']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("PLAY", key=f"bl_{idx}", width='stretch'):
                                df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                                save_database(df); st.rerun()
        
    with col_side:
        st.markdown("##### UPCOMING")
        if not upcoming_games.empty:
            upcoming_games['DateObj'] = pd.to_datetime(upcoming_games['ReleaseDate'], errors='coerce')
            upcoming_games = upcoming_games.sort_values('DateObj')
            u_cols = st.columns(2)
            for i, (_, row) in enumerate(upcoming_games.head(6).iterrows()):
                with u_cols[i % 2]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], width='stretch')
                        st.markdown(f"<p style='font-size:0.75rem; font-weight:600; margin-bottom:0; line-height:1.2;'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:0.65rem; color:#9146FF; margin-top:2px;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)

    # --- INFOGRAPHICS (TRANSPARENT) ---
    st.divider()
    if not played_games.empty:
        st.markdown("##### ANALYTICS")
        c1, c2, c3 = st.columns(3)
        chart_layout = dict(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=30, b=10, l=10, r=10),
            font=dict(color="white", size=10),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False)
        )
        with c1:
            fig1 = px.pie(played_games, names='Genre', hole=0.6, title="GENRE DISTRO", template="plotly_dark")
            fig1.update_layout(chart_layout)
            st.plotly_chart(fig1, width='stretch')
        with c2:
            played_games['Year'] = played_games['ReleaseDate'].astype(str).str[:4]
            yearly = played_games.groupby('Year')['Base_Score'].mean().reset_index()
            fig2 = px.bar(yearly, x='Year', y='Base_Score', title="SCORE TREND", template="plotly_dark")
            fig2.update_traces(marker_color='#9146FF')
            fig2.update_layout(chart_layout)
            st.plotly_chart(fig2, width='stretch')
        with c3:
            fig3 = px.scatter(played_games, x='OpenCritic', y='Base_Score', hover_name='Title', title="VS CRITICS", template="plotly_dark")
            fig3.update_traces(marker=dict(size=10, color='#9146FF'))
            fig3.update_layout(chart_layout)
            st.plotly_chart(fig3, width='stretch')

    # --- STATS ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Completed", len(played_games))
    m2.metric("Average", f"{played_games['Base_Score'].mean():.1f}" if not played_games.empty else "0")
    m3.metric("Backlog", len(backlog_games))
    m4.metric("Next", upcoming_games.iloc[0]['Title'] if not upcoming_games.empty else "TBD")

# --- OTHER PAGES ---
elif page == "Rankings":
    st.markdown("## HALL OF FAME")
    played = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    if not played.empty:
        top_3 = played.head(3)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top_3.iterrows()):
            with cols[i]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'], width='stretch')
                    st.markdown(f"<h3 style='text-align:center;'>{row['Base_Score']}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<p style='text-align:center; font-size:0.9rem;'>{row['Title']}</p>", unsafe_allow_html=True)
        st.divider()
        st.dataframe(played[['Title', 'Platform', 'Base_Score', 'OpenCritic']], width='stretch', hide_index=True)

elif page == "Add Game":
    st.title("Add New Game")
    with st.form("add_new"):
        t = st.text_input("Title")
        p = st.text_input("Platform")
        st_select = st.selectbox("Status", ["Backlog", "Playing", "Upcoming"])
        if st.form_submit_button("Save Game"):
            url = fetch_cover_art(t)
            new_row = {'Title': t, 'Platform': p, 'Status': st_select, 'Cover_URL': url, 'ReleaseDate': str(datetime.date.today()), 'Base_Score': 0}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    st.title("Database Management")
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("Apply Changes"): save_database(ed); st.success("Updated")

st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
