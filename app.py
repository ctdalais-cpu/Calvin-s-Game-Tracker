import streamlit as st
import pandas as pd
import datetime
import requests
import gspread
from google.oauth2.service_account import Credentials

# --- API CREDENTIALS ---
CLIENT_ID = st.secrets["TWITCH_CLIENT_ID"]
CLIENT_SECRET = st.secrets["TWITCH_CLIENT_SECRET"]
ADMIN_PIN = st.secrets["ADMIN_PIN"]

st.set_page_config(page_title="Game Tracker", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
        div[data-testid="stMetricValue"] { font-size: 2rem; }
        div[data-testid="stSidebarNav"] { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- MASTER CONFIGURATION ---
GENRE_CONFIG = {
    "Action": [{"name": "Level Design", "desc": ""}, {"name": "Combat Feel", "desc": ""}],
    "RPG": [{"name": "Narrative", "desc": ""}, {"name": "Characters", "desc": ""}],
    "Roguelite": [{"name": "Replayability", "desc": ""}, {"name": "Clarity", "desc": ""}],
    "Online Multiplayer": [{"name": "Balance", "desc": ""}, {"name": "Community", "desc": ""}],
    "Horror": [{"name": "Atmosphere", "desc": ""}, {"name": "Tension", "desc": ""}],
    "Puzzle": [{"name": "Ingenuity", "desc": ""}, {"name": "Clarity", "desc": ""}],
    "Adventure": [{"name": "Exploration", "desc": ""}, {"name": "World-Building", "desc": ""}],
    "Strategy": [{"name": "Tactical Depth", "desc": ""}, {"name": "UI / UX", "desc": ""}]
}

MASTER_COLUMNS = [
    'Title', 'Status', 'ReleaseDate', 'Platform', 'Hype', 'Genre', 'Base_Score', 'OpenCritic', 'Elo_Rating', 'Cover_URL',
    'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'Bonus_1_Name', 'S_Bonus_1', 'Bonus_2_Name', 'S_Bonus_2'
]

# --- GOOGLE SHEETS CONNECTION ---
scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open("Game Tracker Database").sheet1

records = sheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    df['ReleaseDate'] = df['ReleaseDate'].astype(str)
    for col in MASTER_COLUMNS:
        if col not in df.columns:
            df[col] = 0 if 'Score' in col or 'Elo' in col else ""
else:
    df = pd.DataFrame(columns=MASTER_COLUMNS)
    sheet.append_row(MASTER_COLUMNS)

def save_database(dataframe):
    dataframe = dataframe.fillna("")
    data_to_write = [dataframe.columns.values.tolist()] + dataframe.values.tolist()
    sheet.clear()
    sheet.update(data_to_write)

def fetch_cover_art(title):
    try:
        auth_res = requests.post(f"https://id.twitch.tv/oauth2/token?client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&grant_type=client_credentials")
        access_token = auth_res.json().get('access_token')
        if not access_token: return ""
        headers = {'Client-ID': CLIENT_ID, 'Authorization': f'Bearer {access_token}'}
        data = f'search "{title}"; fields cover.url; limit 1;'
        res = requests.post("https://api.igdb.com/v4/games", headers=headers, data=data)
        game_data = res.json()
        if game_data and len(game_data) > 0 and 'cover' in game_data[0]:
            return "https:" + game_data[0]['cover']['url'].replace("t_thumb", "t_cover_big")
        return ""
    except: return ""

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🎮 Game Tracker")
st.sidebar.divider()

available_pages = ["Dashboard", "Rankings"]
st.sidebar.write("---")
user_pin = st.sidebar.text_input("Admin Passcode:", type="password")

if user_pin == ADMIN_PIN:
    available_pages.extend(["Add Game", "The Arena", "Edit Database"])
elif user_pin != "":
    st.sidebar.error("Incorrect Passcode")

page = st.sidebar.radio("Navigation", available_pages, label_visibility="collapsed")

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.title("Dashboard")
    played_games = df[df['Status'] == 'Played']
    upcoming_all = df[df['Status'] == 'Upcoming'].copy()
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1: st.metric("Completed Games", len(played_games))
    with col_m2:
        avg_score = played_games['Base_Score'].mean() if not played_games.empty else 0
        st.metric("Average Score", f"{avg_score:.1f}")
    with col_m3:
        if not upcoming_all.empty:
            upcoming_all['DateObj'] = pd.to_datetime(upcoming_all['ReleaseDate'], errors='coerce')
            future_games = upcoming_all[upcoming_all['DateObj'] >= pd.Timestamp(datetime.date.today())]
            next_game = future_games.sort_values(by='DateObj').iloc[0]['Title'] if not future_games.empty else "None Scheduled"
            st.metric("Next Release", next_game)
        else: st.metric("Next Release", "None Scheduled")
            
    st.divider()
    dash_left, dash_right = st.columns([1.2, 1], gap="large")
    
    with dash_left:
        st.subheader("Currently Playing")
        playing_games = df[df['Status'] == 'Playing']
        
        if 'scoring_game' in st.session_state and user_pin == ADMIN_PIN:
            finish_target = st.session_state.scoring_game
            target_data = playing_games[playing_games['Title'] == finish_target].iloc[0]
            st.markdown(f"**Finish:** {finish_target}")
            if st.button("Cancel / Back"):
                del st.session_state.scoring_game
                st.rerun()
                
            is_dnf = st.toggle("Mark as DNF (Unscored & Dropped)")
            if is_dnf:
                if st.button("Save to Graveyard", use_container_width=True):
                    df.loc[df['Title'] == finish_target, 'Status'] = 'DNF'
                    save_database(df)
                    del st.session_state.scoring_game
                    st.rerun()
            else:
                genre_opts = list(GENRE_CONFIG.keys())
                start_g = target_data['Genre'] if target_data['Genre'] in genre_opts else genre_opts[0]
                new_g = st.selectbox("Assign Genre", genre_opts, index=genre_opts.index(start_g))
                b1, b2 = GENRE_CONFIG[new_g][0], GENRE_CONFIG[new_g][1]
                
                with st.form("score_active"):
                    new_oc = st.number_input("OpenCritic", 0, 100, int(target_data['OpenCritic']))
                    c1, c2 = st.columns(2)
                    with c1: 
                        g_play = st.slider("Gameplay", 1.0, 10.0, 5.0, 0.1)
                        vis = st.slider("Visuals", 1.0, 10.0, 5.0, 0.1)
                    with c2: 
                        aud = st.slider("Audio", 1.0, 10.0, 5.0, 0.1)
                        fun = st.slider("Fun Factor", 1.0, 10.0, 5.0, 0.1)
                    c3, c4 = st.columns(2)
                    with c3: b1_val = st.slider(b1["name"], 1.0, 10.0, 5.0, 0.1)
                    with c4: b2_val = st.slider(b2["name"], 1.0, 10.0, 5.0, 0.1)
                    
                    if st.form_submit_button("Score & Move to Rankings", use_container_width=True):
                        base_score = round((g_play*2) + (vis*2) + (aud*2) + (fun*2) + (b1_val*1) + (b2_val*1), 1)
                        df.loc[df['Title'] == finish_target, ['Status', 'Genre', 'OpenCritic', 'Base_Score', 'Elo_Rating', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'Bonus_1_Name', 'S_Bonus_1', 'Bonus_2_Name', 'S_Bonus_2']] = ['Played', new_g, new_oc, base_score, base_score * 15, g_play, vis, aud, fun, b1["name"], b1_val, b2["name"], b2_val]
                        save_database(df)
                        del st.session_state.scoring_game
                        st.rerun()
        else:
            if not playing_games.empty:
                for idx, row in playing_games.iterrows():
                    with st.container(border=True):
                        col_t, col_b = st.columns([3, 1])
                        col_t.write(f"**{row['Title']}** ({row['Platform']})")
                        if user_pin == ADMIN_PIN:
                            if col_b.button("Finish", key=f"fin_{idx}", use_container_width=True):
                                st.session_state.scoring_game = row['Title']
                                st.rerun()
            else: st.info("You aren't currently playing anything.")

    with dash_right:
        st.subheader("Upcoming Releases")
        if not upcoming_all.empty:
            upcoming_all['DateObj'] = pd.to_datetime(upcoming_all['ReleaseDate'], errors='coerce')
            upcoming_all = upcoming_all.sort_values(by='DateObj')
            cols = st.columns(5) 
            for index, row in upcoming_all.reset_index().iterrows():
                with cols[index % 5]: 
                    with st.container(border=True):
                        if pd.notna(row['Cover_URL']) and row['Cover_URL'] != "": st.image(row['Cover_URL'], use_container_width=True)
                        st.write(f"**{row['Title']}**")
                        st.caption(f"{row['ReleaseDate']}")
        else: st.info("No upcoming releases tracked.")

# --- PAGE 2: RANKINGS ---
elif page == "Rankings":
    st.title("Overall Rankings")
    played_games = df[df['Status'] == 'Played'].copy()
    if not played_games.empty:
        rv = played_games.sort_values(by='Base_Score', ascending=False).copy()
        rv.insert(0, 'Rank', range(1, len(rv) + 1))
        cl_table = rv[['Rank', 'Title', 'Platform', 'ReleaseDate', 'Base_Score', 'OpenCritic']].rename(columns={'ReleaseDate': 'Year', 'Base_Score': 'My Score', 'OpenCritic': 'Critic'})
        
        c_left, c_right = st.columns([2, 1], gap="large")
        with c_left: st.dataframe(cl_table, hide_index=True, use_container_width=True)
        with c_right:
            st.subheader("Inspector")
            sq = st.selectbox("Select a game:", ["-- Select --"] + rv['Title'].tolist())
            if sq != "-- Select --":
                gd = rv[rv['Title'] == sq].iloc[0]
                if pd.notna(gd['Cover_URL']) and gd['Cover_URL'] != "": st.image(gd['Cover_URL'], use_container_width=True)
                st.write(f"**{sq}** ({gd['Genre']})")
                m1, m2 = st.columns(2)
                m1.metric("My Score", f"{gd['Base_Score']:.1f}")
                m2.metric("OpenCritic", f"{gd['OpenCritic']:.0f}" if gd['OpenCritic'] > 0 else "N/A")
                st.divider()
                st.write(f"Gameplay: {gd['S_Gameplay']}/10 | Visuals: {gd['S_Visuals']}/10")
                st.write(f"Audio: {gd['S_Audio']}/10 | Fun: {gd['S_Fun']}/10")
    else: st.info("You haven't scored any games yet.")

# --- PAGE 3: ADD GAME ---
elif page == "Add Game" and user_pin == ADMIN_PIN:
    st.title("Add to Library")
    add_status = st.radio("Status", ["Played", "Playing", "Upcoming"], horizontal=True)
    with st.form("add"):
        new_title = st.text_input("Title")
        c1, c2 = st.columns(2)
        with c1: new_plat = st.text_input("Platform")
        with c2: final_date = st.text_input("Year/Date")
        if st.form_submit_button("Save Game"):
            url = fetch_cover_art(new_title)
            new_df = pd.DataFrame([{'Title': new_title, 'Status': add_status, 'ReleaseDate': final_date, 'Platform': new_plat, 'Cover_URL': url}])
            df = pd.concat([df, new_df], ignore_index=True)
            save_database(df)
            st.success("Saved!")
            st.rerun()

# --- PAGE 4: THE ARENA ---
elif page == "The Arena" and user_pin == ADMIN_PIN:
    st.title("The Arena")
    pg = df[df['Status'] == 'Played']
    if len(pg) < 2: st.info("Score at least 2 games.")
    else:
        if 'game_a' not in st.session_state:
            matchup = pg.sample(2)
            st.session_state.game_a, st.session_state.game_b = matchup.iloc[0]['Title'], matchup.iloc[1]['Title']
        ga, gb = st.session_state.game_a, st.session_state.game_b
        st.subheader("Which is better?")
        c1, c2 = st.columns(2)
        if c1.button(ga, use_container_width=True):
            # Simple Elo logic placeholder
            del st.session_state.game_a, st.session_state.game_b
            st.rerun()
        if c2.button(gb, use_container_width=True):
            del st.session_state.game_a, st.session_state.game_b
            st.rerun()

# --- PAGE 5: EDIT DATABASE ---
elif page == "Edit Database" and user_pin == ADMIN_PIN:
    st.title("Edit Database")
    et = st.selectbox("Select Game", ["-- Select --"] + df['Title'].tolist())
    if et != "-- Select --":
        td = df[df['Title'] == et].iloc[0]
        with st.form("edit_form"):
            new_url = st.text_input("Manual Cover URL", str(td['Cover_URL']))
            if st.form_submit_button("Update"):
                df.loc[df['Title'] == et, 'Cover_URL'] = new_url
                save_database(df)
                st.success("Updated!")
                st.rerun()
