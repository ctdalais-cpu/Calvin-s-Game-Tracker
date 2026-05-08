import streamlit as st
import pandas as pd
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- API CREDENTIALS ---
CLIENT_ID = st.secrets["TWITCH_CLIENT_ID"]
CLIENT_SECRET = st.secrets["TWITCH_CLIENT_SECRET"]
ADMIN_PIN = st.secrets["ADMIN_PIN"]

st.set_page_config(page_title="Game Hub Pro", layout="wide", initial_sidebar_state="expanded")

# --- ULTIMATE AESTHETIC CSS ---
st.markdown("""
    <style>
        /* Main Background and Fonts */
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
            padding: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        /* Status Cards */
        .status-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 15px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 10px;
        }

        /* Metrics Styling */
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 12px;
            border-left: 5px solid #9146FF;
        }

        /* Image Styling */
        img {
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            transition: 0.3s ease;
        }
        img:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(145, 70, 255, 0.4);
        }

        /* Buttons */
        .stButton>button {
            border-radius: 8px;
            background-color: #2D3748;
            border: none;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #9146FF;
            color: white;
            border: none;
        }
    </style>
""", unsafe_allow_html=True)

# --- (Keep your GENRE_CONFIG, MASTER_COLUMNS, and Connection Logic as is) ---

# [Snippet: Assuming Google Sheets and Fetching functions are here as per your previous code]

# --- PAGE 1: DASHBOARD (REIMAGINED) ---
if page == "Dashboard":
    # Hero Header
    st.markdown("<h1 style='text-align: center; color: #9146FF;'>GAME COMMAND CENTER</h1>", unsafe_allow_html=True)
    
    played_games = df[df['Status'] == 'Played']
    upcoming_all = df[df['Status'] == 'Upcoming'].copy()
    
    # Top Row Stats
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Completed", len(played_games))
    with m2: 
        avg = played_games['Base_Score'].mean() if not played_games.empty else 0
        st.metric("Avg Score", f"{avg:.1f}/100")
    with m3: st.metric("Backlog", len(df[df['Status'] == 'Backlog']))
    with m4:
        # High Score
        top_game = played_games.sort_values('Base_Score', ascending=False).iloc[0]['Title'] if not played_games.empty else "N/A"
        st.metric("GOAT", top_game)

    st.divider()

    dash_left, dash_right = st.columns([1, 1.2], gap="large")
    
    with dash_left:
        st.subheader("⚡ Now Playing")
        playing_games = df[df['Status'] == 'Playing']
        
        if not playing_games.empty:
            for idx, row in playing_games.iterrows():
                # A more visual "Now Playing" card
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        if row['Cover_URL']: st.image(row['Cover_URL'])
                    with c2:
                        st.markdown(f"### {row['Title']}")
                        st.caption(f"🚀 {row['Platform']}")
                        if st.session_state.admin_pin_input == ADMIN_PIN:
                            if st.button("Complete Entry", key=f"fin_{idx}"):
                                st.session_state.scoring_game = row['Title']
                                st.rerun()
        else:
            st.info("No active sessions. Check your backlog!")

        st.write("")
        st.subheader("📚 The Backlog")
        # Multi-column layout for backlog so it doesn't take too much vertical space
        backlog_games = df[df['Status'] == 'Backlog']
        if not backlog_games.empty:
            for _, b_row in backlog_games.iterrows():
                with st.expander(f"{b_row['Title']} ({b_row['Platform']})"):
                    st.write(f"Added to backlog on {b_row['ReleaseDate']}")
                    if st.button("Start Playing", key=f"start_{b_row['Title']}"):
                        df.loc[df['Title'] == b_row['Title'], 'Status'] = 'Playing'
                        save_database(df)
                        st.rerun()

    with dash_right:
        st.subheader("🗓️ Upcoming Hype")
        if not upcoming_all.empty:
            # Sort by date
            upcoming_all['DateObj'] = pd.to_datetime(upcoming_all['ReleaseDate'], errors='coerce')
            upcoming_all = upcoming_all.sort_values('DateObj')
            
            # Use a horizontal scroll-style or grid
            cols = st.columns(3)
            for i, (_, row) in enumerate(upcoming_all.head(6).iterrows()):
                with cols[i % 3]:
                    if row['Cover_URL']: st.image(row['Cover_URL'])
                    st.markdown(f"<p style='font-size:0.9rem; font-weight:bold; margin-bottom:0;'>{row['Title']}</p>", unsafe_allow_html=True)
                    st.caption(row['ReleaseDate'])
        else:
            st.info("Nothing on the radar.")

# --- PAGE 2: RANKINGS (UPGRADED VISUALS) ---
elif page == "Rankings":
    st.markdown("<h2 style='color: #9146FF;'>THE HALL OF FAME</h2>", unsafe_allow_html=True)
    
    played_games = df[df['Status'] == 'Played'].copy()
    
    if not played_games.empty:
        # Custom "Podium" for Top 3
        top_3 = played_games.sort_values('Base_Score', ascending=False).head(3)
        p1, p2, p3 = st.columns(3)
        
        podium_slots = [p1, p2, p3]
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (idx, row) in enumerate(top_3.iterrows()):
            with podium_slots[i]:
                st.markdown(f"<h3 style='text-align:center;'>{medals[i]}</h3>", unsafe_allow_html=True)
                if row['Cover_URL']: st.image(row['Cover_URL'])
                st.markdown(f"<p style='text-align:center;'><b>{row['Title']}</b><br>{row['Base_Score']}</p>", unsafe_allow_html=True)

        st.divider()
        
        # Interactive Data Table with color formatting
        st.dataframe(
            played_games[['Title', 'Platform', 'Base_Score', 'OpenCritic']].sort_values('Base_Score', ascending=False),
            use_container_width=True,
            column_config={
                "Base_Score": st.column_config.ProgressColumn("My Score", min_value=0, max_value=100, format="%f"),
                "OpenCritic": st.column_config.NumberColumn("Critics")
            },
            hide_index=True
        )
