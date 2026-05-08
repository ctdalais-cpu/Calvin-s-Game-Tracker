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

# --- 2. THE CLEAN AESTHETIC (CSS) ---
st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, #1a1c23 0%, #0e1117 100%);
            color: #E2E8F0;
        }
        
        /* Transparent Glass Containers */
        div[data-testid="stVerticalBlock"] > div[style*="border"] {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(8px);
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            padding: 12px;
        }

        /* Clean Metrics */
        div[data-testid="stMetricValue"] { 
            font-size: 2rem; 
            font-weight: 800; 
            color: #FFFFFF; 
            letter-spacing: -1px;
        }
        div[data-testid="stMetricLabel"] {
            color: #94A3B8;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 1px;
        }
        
        img {
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        }

        /* Sidebar cleaning */
        .css-1d391kg { background-color: #0e1117; }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINES ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
df = pd.DataFrame(records) if records else pd.DataFrame(columns=['Title', 'Status', 'ReleaseDate', 'Platform', 'Cover_URL', 'Base_Score', 'OpenCritic', 'Genre'])

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

# --- 4. SIDEBAR ---
if "admin_pin_input" not in st.session_state: st.session_state.admin_pin_input = ""
pages = ["Dashboard", "Rankings"]
if st.session_state.admin_pin_input == ADMIN_PIN:
    pages.extend(["Add Game", "Edit Database"])
page = st.sidebar.radio("Navigation", pages)

# --- 5. PAGE: DASHBOARD ---
if page == "Dashboard":
    st.markdown("<h2 style='letter-spacing:-1px;'>COMMAND CENTER</h2>", unsafe_allow_html=True)
    
    played_games = df[df['Status'] == 'Played']
    playing_games = df[df['Status'] == 'Playing']
    backlog_games = df[df['Status'] == 'Backlog']
    upcoming_games = df[df['Status'] == 'Upcoming'].copy()
    
    col_main, col_side = st.columns([2, 1], gap="medium")
    
    with col_main:
        # Currently Playing Grid
        st.markdown("### CURRENTLY PLAYING")
        if not playing_games.empty:
            p_cols = st.columns(3)
            for i, (idx, row) in enumerate(playing_games.iterrows()):
                with p_cols[i % 3]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                        st.markdown(f"**{row['Title']}**")
                        st.caption(row['Platform'])
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("FINISH", key=f"fin_{idx}", use_container_width=True):
                                st.session_state.scoring_game = row['Title']; st.rerun()
        else: st.info("Queue empty.")

        # Backlog Grid
        st.markdown("### BACKLOG")
        if not backlog_games.empty:
            b_cols = st.columns(4)
            for i, (idx, row) in enumerate(backlog_games.iterrows()):
                with b_cols[i % 4]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                        st.markdown(f"<p style='font-size:0.8rem; font-weight:bold; margin-bottom:0;'>{row['Title']}</p>", unsafe_allow_html=True)
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("PLAY", key=f"bl_{idx}", use_container_width=True):
                                df.loc[df['Title'] == row['Title'], 'Status'] = 'Playing'
                                save_database(df); st.rerun()
        
    with col_side:
        st.markdown("### UPCOMING")
        if not upcoming_games.empty:
            upcoming_games['DateObj'] = pd.to_datetime(upcoming_games['ReleaseDate'], errors='coerce')
            upcoming_games = upcoming_games.sort_values('DateObj')
            u_cols = st.columns(2)
            for i, (_, row) in enumerate(upcoming_all.head(6).iterrows()):
                with u_cols[i % 2]:
                    with st.container(border=True):
                        if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                        st.markdown(f"<p style='font-size:0.75rem; font-weight:bold; margin-bottom:0;'>{row['Title']}</p>", unsafe_allow_html=True)
                        st.markdown(f"<p style='font-size:0.7rem; color:#9146FF;'>{row['ReleaseDate']}</p>", unsafe_allow_html=True)

    # --- INFOGRAPHICS (FIXED TRANSPARENCY) ---
    st.divider()
    if not played_games.empty:
        st.markdown("### ANALYTICS")
        c1, c2, c3 = st.columns(3)
        
        # Consistent Chart Styling
        chart_layout = dict(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=40, b=20, l=20, r=20),
            font=dict(color="white"),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False)
        )

        with c1:
            fig1 = px.pie(played_games, names='Genre', hole=0.5, title="GENRE DISTRO", template="plotly_dark")
            fig1.update_layout(chart_layout)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            played_games['Year'] = played_games['ReleaseDate'].astype(str).str[:4]
            yearly = played_games.groupby('Year')['Base_Score'].mean().reset_index()
            fig2 = px.bar(yearly, x='Year', y='Base_Score', title="SCORE TREND", template="plotly_dark")
            fig2.update_traces(marker_color='#9146FF')
            fig2.update_layout(chart_layout)
            st.plotly_chart(fig2, use_container_width=True)
        with c3:
            fig3 = px.scatter(played_games, x='OpenCritic', y='Base_Score', hover_name='Title', title="VS CRITICS", template="plotly_dark")
            fig3.update_traces(marker=dict(size=12, color='#9146FF', symbol='square'))
            fig3.update_layout(chart_layout)
            st.plotly_chart(fig3, use_container_width=True)

    # --- STATS AT BOTTOM ---
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Completed", len(played_games))
    m2.metric("Average", f"{played_games['Base_Score'].mean():.1f}" if not played_games.empty else "0")
    m3.metric("Backlog Count", len(backlog_games))
    m4.metric("Next", upcoming_games.iloc[0]['Title'] if not upcoming_games.empty else "TBD")

# --- RANKINGS ---
elif page == "Rankings":
    st.markdown("## HALL OF FAME")
    played = df[df['Status'] == 'Played'].sort_values('Base_Score', ascending=False)
    if not played.empty:
        # Podium
        top_3 = played.head(3)
        cols = st.columns(3)
        for i, (_, row) in enumerate(top_3.iterrows()):
            with cols[i]:
                with st.container(border=True):
                    if row['Cover_URL']: st.image(row['Cover_URL'], use_container_width=True)
                    st.markdown(f"<h3 style='text-align:center;'>{row['Base_Score']}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<p style='text-align:center;'>{row['Title']}</p>", unsafe_allow_html=True)
        st.divider()
        st.dataframe(played[['Title', 'Platform', 'Base_Score', 'OpenCritic']], use_container_width=True, hide_index=True)

# --- ADMIN ---
elif page == "Add Game":
    with st.form("add"):
        t = st.text_input("Title")
        p = st.text_input("Platform")
        st = st.selectbox("Status", ["Backlog", "Playing", "Upcoming"])
        if st.form_submit_button("Save"):
            url = fetch_cover_art(t)
            new_row = {'Title': t, 'Platform': p, 'Status': st, 'Cover_URL': url, 'ReleaseDate': str(datetime.date.today()), 'Base_Score': 0}
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_database(df); st.rerun()

elif page == "Edit Database":
    ed = st.data_editor(df, num_rows="dynamic")
    if st.button("Save Changes"): save_database(ed); st.success("Updated")

# Sidebar Admin Footer
st.sidebar.divider()
st.sidebar.text_input("Admin Access", type="password", key="admin_pin_input")
