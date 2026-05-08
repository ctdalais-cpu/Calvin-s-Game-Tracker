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
    "Action": [{"name": "Level Design", "desc": "Pacing, environment layout, and encounter variety."}, {"name": "Combat Feel", "desc": "Impact, responsiveness, and weapon/ability satisfaction."}],
    "RPG": [{"name": "Narrative", "desc": "Story, lore, world-building, and dialogue."}, {"name": "Characters", "desc": "Party members, NPCs, and character development."}],
    "Roguelite": [{"name": "Replayability", "desc": "Variety between runs, unlock progression, and longevity."}, {"name": "Clarity", "desc": "Readability of UI, combat cues, and mechanics amidst chaos."}],
    "Online Multiplayer": [{"name": "Balance", "desc": "Fairness of mechanics, matchmaking, and meta diversity."}, {"name": "Community", "desc": "Social features, toxicity levels, and player interaction."}],
    "Horror": [{"name": "Atmosphere", "desc": "Lighting, mood, and environmental dread."}, {"name": "Tension", "desc": "Pacing, scare timing, and feelings of vulnerability."}],
    "Puzzle": [{"name": "Ingenuity", "desc": "Cleverness of mechanics and rewarding 'Aha!' moments."}, {"name": "Clarity", "desc": "Readability of rules, logic, and visual cues."}],
    "Adventure": [{"name": "Exploration", "desc": "Rewarding curiosity, secrets, and sense of discovery."}, {"name": "World-Building", "desc": "Environmental storytelling, lore, and setting."}],
    "Strategy": [{"name": "Tactical Depth", "desc": "Meaningful choices, strategic variety, and complexity."}, {"name": "UI / UX", "desc": "Menu navigation, readability, and ease of issuing commands."}]
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

# --- SIDEBAR NAVIGATION WITH ADMIN BOUNCER ---
# Only show the public pages by default
available_pages = ["Dashboard", "Rankings"]

# The Admin Unlock Box
st.sidebar.write("---")
user_pin = st.sidebar.text_input("Admin Passcode:", type="password")

# If the PIN matches, unlock the rest of the app
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
            view_mode = st.radio("Display Mode:", ["Grid", "Agenda"], horizontal=True, label_visibility="collapsed")
            st.write("") 
            
            if view_mode == "Grid":
                cols = st.columns(5) 
                for index, row in upcoming_all.reset_index().iterrows():
                    with cols[index % 5]: 
                        with st.container(border=True):
                            if pd.notna(row['Cover_URL']) and row['Cover_URL'] != "": st.image(row['Cover_URL'], use_container_width=True)
                            st.write(f"**{row['Title']}**")
                            st.caption(f"{row['ReleaseDate']} | {row['Platform']}")
            elif view_mode == "Agenda":
                upcoming_all['MonthYear'] = upcoming_all['DateObj'].dt.strftime('%B %Y').fillna('TBD')
                for month, group in upcoming_all.groupby('MonthYear', sort=False):
                    st.markdown(f"**{month}**")
                    for _, row in group.iterrows():
                        st.write(f"{row['ReleaseDate']} — {row['Title']} ({row['Platform']})")
                    st.divider()
        else: st.info("No upcoming releases tracked.")

        if user_pin == ADMIN_PIN:
            with st.expander("Quick Add Upcoming"):
                with st.form("quick_up"):
                    t = st.text_input("Title")
                    c1, c2 = st.columns(2)
                    with c1: p = st.text_input("Platform")
                    with c2: d = st.date_input("Exact Date", datetime.date.today())
                    h = st.slider("Hype Level", 1, 5, 3)
                    if st.form_submit_button("Add to Calendar"):
                        with st.spinner("Fetching cover art..."): url = fetch_cover_art(t)
                        new_up = pd.DataFrame([{'Title': t, 'Status': 'Upcoming', 'ReleaseDate': d.strftime('%Y-%m-%d'), 'Platform': p, 'Hype': h, 'Genre': 'TBD', 'Base_Score': 0, 'OpenCritic': 0, 'Elo_Rating': 0, 'Cover_URL': url, 'S_Gameplay': 0, 'S_Visuals': 0, 'S_Audio': 0, 'S_Fun': 0, 'Bonus_1_Name': 'TBD', 'S_Bonus_1': 0, 'Bonus_2_Name': 'TBD', 'S_Bonus_2': 0}])
                        df = pd.concat([df, new_up], ignore_index=True)
                        save_database(df)
                        st.rerun()

# --- PAGE 2: RANKINGS ---
elif page == "Rankings":
    st.title("Overall Rankings")
    played_games = df[df['Status'] == 'Played'].copy()
    if not played_games.empty:
        c_filter, _ = st.columns([1, 3])
        with c_filter:
            av_years = sorted(played_games['ReleaseDate'].unique().tolist(), reverse=True)
            sel_year = st.selectbox("Filter by Release Year:", ["All Time"] + av_years, label_visibility="collapsed")
        st.write("") 
            
        if sel_year != "All Time": played_games = played_games[played_games['ReleaseDate'] == sel_year]
        if played_games.empty: st.info(f"No games found for {sel_year}.")
        else:
            rv = played_games.sort_values(by='Base_Score', ascending=False).copy()
            rv.insert(0, 'Rank', range(1, len(rv) + 1))
            cl_table = rv[['Rank', 'Title', 'Platform', 'ReleaseDate', 'Base_Score', 'OpenCritic']].rename(columns={'ReleaseDate': 'Year', 'Base_Score': 'My Score', 'OpenCritic': 'Critic'})
            c_left, c_right = st.columns([2, 1], gap="large")
            with c_left: st.dataframe(cl_table, hide_index=True, use_container_width=True, column_config={"Rank": st.column_config.NumberColumn("Rank", width=50), "Title": st.column_config.TextColumn("Title", width="large")})
            with c_right:
                st.subheader("Inspector")
                sq = st.selectbox("Deep dive breakdown:", ["-- Select a game --"] + rv['Title'].tolist(), label_visibility="collapsed")
                if sq != "-- Select a game --":
                    gd = rv[rv['Title'] == sq].iloc[0]
                    ci, cinfo = st.columns([1, 3]) 
                    with ci:
                        if pd.notna(gd['Cover_URL']) and gd['Cover_URL'] != "": st.image(gd['Cover_URL'], use_container_width=True)
                    with cinfo:
                        st.markdown(f"**{sq}**")
                        st.caption(f"Genre: {gd['Genre']}")
                    
                    m1, m2 = st.columns(2)
                    if gd['OpenCritic'] > 0: 
                        m1.metric("My Score", f"{gd['Base_Score']:.1f}", f"{gd['Base_Score'] - gd['OpenCritic']:+.1f} vs Critics", delta_color="normal")
                        m2.metric("OpenCritic", f"{gd['OpenCritic']:.0f}")
                    else: 
                        m1.metric("My Score", f"{gd['Base_Score']:.1f}")
                        m2.metric("OpenCritic", "N/A")
                        
                    st.divider()
                    
                    c1, c2 = st.columns(2)
                    c1.metric("Gameplay", f"{gd['S_Gameplay']}/10")
                    c2.metric("Visuals", f"{gd['S_Visuals']}/10")
                    
                    c3, c4 = st.columns(2)
                    c3.metric("Audio", f"{gd['S_Audio']}/10")
                    c4.metric("Fun", f"{gd['S_Fun']}/10")
                    
                    c5, c6 = st.columns(2)
                    c5.metric(str(gd['Bonus_1_Name']), f"{gd['S_Bonus_1']}/10")
                    c6.metric(str(gd['Bonus_2_Name']), f"{gd['S_Bonus_2']}/10")
    else: st.info("You haven't scored any games yet.")

    st.write("")
    with st.expander("View DNF Graveyard"):
        if not df[df['Status'] == 'DNF'].empty: st.dataframe(df[df['Status'] == 'DNF'][['Title', 'Platform', 'ReleaseDate']], hide_index=True, use_container_width=True)
        else: st.write("No abandoned games yet.")

# --- PAGE 3: ADD GAME (ADMIN ONLY) ---
elif page == "Add Game" and user_pin == ADMIN_PIN:
    st.title("Add to Library")
    add_status = st.radio("What are you adding?", ["Played (Completed)", "Currently Playing", "Upcoming Release", "Did Not Finish (DNF)"], horizontal=True)
    db_status = "Played" if "Played" in add_status else ("Playing" if "Playing" in add_status else ("Upcoming" if "Upcoming" in add_status else "DNF"))
    if db_status == "Played":
        genre = st.selectbox("Select Primary Genre", list(GENRE_CONFIG.keys()))
        b1_data, b2_data = GENRE_CONFIG[genre][0], GENRE_CONFIG[genre][1]
        
    with st.form("add_game_form", clear_on_submit=True):
        new_title = st.text_input("Game Title")
        c_plat, c_year, c_oc = st.columns(3)
        with c_plat: new_plat = st.text_input("Platform")
        if db_status == "Upcoming":
            with c_year: final_date_str = st.date_input("Exact Release Date", datetime.date.today()).strftime('%Y-%m-%d')
        else:
            with c_year: final_date_str = str(st.text_input("Release Year"))
        
        if db_status == "Played":
            with c_oc: new_oc = st.number_input("OpenCritic Score", 0, 100, 0)
            st.markdown("**Core Elements**")
            c1, c2 = st.columns(2)
            with c1: 
                gameplay = st.slider("Gameplay", 1.0, 10.0, 5.0, 0.1)
                visuals = st.slider("Visuals", 1.0, 10.0, 5.0, 0.1)
            with c2: 
                audio = st.slider("Audio", 1.0, 10.0, 5.0, 0.1)
                fun = st.slider("Fun Factor", 1.0, 10.0, 5.0, 0.1)
            st.markdown(f"**Genre Specific: {genre}**")
            c3, c4 = st.columns(2)
            with c3: bonus1 = st.slider(b1_data["name"], 1.0, 10.0, 5.0, 0.1)
            with c4: bonus2 = st.slider(b2_data["name"], 1.0, 10.0, 5.0, 0.1)
        elif db_status == "Upcoming": up_hype = st.slider("Hype Level", 1, 5, 3)
            
        if st.form_submit_button("Save to Database"):
            with st.spinner("Fetching cover art from IGDB..."): cover_url = fetch_cover_art(new_title)
            if db_status == "Played":
                b_score = round((gameplay*2) + (visuals*2) + (audio*2) + (fun*2) + (bonus1*1) + (bonus2*1), 1)
                new_df = pd.DataFrame([{'Title': new_title, 'Status': db_status, 'ReleaseDate': final_date_str, 'Platform': new_plat, 'Hype': 0, 'Genre': genre, 'Base_Score': b_score, 'OpenCritic': new_oc, 'Elo_Rating': b_score*15, 'Cover_URL': cover_url, 'S_Gameplay': gameplay, 'S_Visuals': visuals, 'S_Audio': audio, 'S_Fun': fun, 'Bonus_1_Name': b1_data["name"], 'S_Bonus_1': bonus1, 'Bonus_2_Name': b2_data["name"], 'S_Bonus_2': bonus2}])
            else:
                new_df = pd.DataFrame([{'Title': new_title, 'Status': db_status, 'ReleaseDate': final_date_str, 'Platform': new_plat, 'Hype': up_hype if db_status == "Upcoming" else 0, 'Genre': 'TBD', 'Base_Score': 0, 'OpenCritic': 0, 'Elo_Rating': 0, 'Cover_URL': cover_url, 'S_Gameplay': 0, 'S_Visuals': 0, 'S_Audio': 0, 'S_Fun': 0, 'Bonus_1_Name': 'TBD', 'S_Bonus_1': 0, 'Bonus_2_Name': 'TBD', 'S_Bonus_2': 0}])
            df = pd.concat([df, new_df], ignore_index=True)
            save_database(df)
            st.success("Game saved successfully.")
            st.rerun()

# --- PAGE 4: THE ARENA (ADMIN ONLY) ---
elif page == "The Arena" and user_pin == ADMIN_PIN:
    st.title("The Arena")
    pg = df[df['Status'] == 'Played']
    if len(pg) < 2: st.info("Score at least 2 games to unlock the Arena.")
    else:
        if 'game_a' not in st.session_state:
            matchup = pg.sample(2)
            st.session_state.game_a, st.session_state.game_b = matchup.iloc[0]['Title'], matchup.iloc[1]['Title']
        ga, gb = st.session_state.game_a, st.session_state.game_b
        
        st.subheader("Which game is better?")
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            if st.button(f"Vote for {ga}", use_container_width=True): va = True
            else: va = False
        with c2:
            if st.button(f"Vote for {gb}", use_container_width=True): vb = True
            else: vb = False
            
        if va or vb:
            ea, eb = float(df.loc[df['Title'] == ga, 'Elo_Rating'].values[0]), float(df.loc[df['Title'] == gb, 'Elo_Rating'].values[0])
            xa, xb = 1 / (1 + 10 ** ((eb - ea) / 400)), 1 / (1 + 10 ** ((ea - eb) / 400))
            if va: df.loc[df['Title'] == ga, 'Elo_Rating'], df.loc[df['Title'] == gb, 'Elo_Rating'] = ea + 32 * (1 - xa), eb + 32 * (0 - xb)
            else: df.loc[df['Title'] == ga, 'Elo_Rating'], df.loc[df['Title'] == gb, 'Elo_Rating'] = ea + 32 * (0 - xa), eb + 32 * (1 - xb)
            save_database(df)
            del st.session_state.game_a, st.session_state.game_b
            st.rerun()

# --- PAGE 5: EDIT DATABASE (ADMIN ONLY) ---
elif page == "Edit Database" and user_pin == ADMIN_PIN:
    st.title("Edit Database")
    if df.empty: st.info("No games yet.")
    else:
        et = st.selectbox("Search for game:", ["-- Select --"] + df['Title'].tolist())
        if et != "-- Select --":
            td = df[df['Title'] == et].iloc[0]
            ns = st.selectbox("Status", ["Upcoming", "Playing", "Played", "DNF"], index=["Upcoming", "Playing", "Played", "DNF"].index(td['Status']))
            ng = td['Genre']
            if ns == "Played":
                go = list(GENRE_CONFIG.keys())
                ng = st.selectbox("Genre", go, index=go.index(ng) if ng in go else 0)
                b1, b2 = GENRE_CONFIG[ng][0], GENRE_CONFIG[ng][1]
            with st.form("edit"):
                c_p, c_y, c_oc = st.columns(3)
                with c_p: ep = st.text_input("Platform", str(td['Platform']))
                with c_y: ey = st.text_input("Date/Year", str(td['ReleaseDate']))
                if ns == "Played":
                    with c_oc: eoc = st.number_input("OpenCritic", 0, 100, int(td['OpenCritic']))
                    c1, c2 = st.columns(2)
                    with c1: 
                        eg = st.slider("Gameplay", 1.0, 10.0, float(td['S_Gameplay']) if td['S_Gameplay']>0 else 5.0, 0.1)
                        ev = st.slider("Visuals", 1.0, 10.0, float(td['S_Visuals']) if td['S_Visuals']>0 else 5.0, 0.1)
                    with c2: 
                        ea = st.slider("Audio", 1.0, 10.0, float(td['S_Audio']) if td['S_Audio']>0 else 5.0, 0.1)
                        ef = st.slider("Fun", 1.0, 10.0, float(td['S_Fun']) if td['S_Fun']>0 else 5.0, 0.1)
                    c3, c4 = st.columns(2)
                    with c3: eb1 = st.slider(b1["name"], 1.0, 10.0, float(td['S_Bonus_1']) if td['Bonus_1_Name']==b1['name'] else 5.0, 0.1)
                    with c4: eb2 = st.slider(b2["name"], 1.0, 10.0, float(td['S_Bonus_2']) if td['Bonus_2_Name']==b2['name'] else 5.0, 0.1)
                if st.form_submit_button("Update Game"):
                    curl = fetch_cover_art(et) if pd.isna(td['Cover_URL']) or td['Cover_URL'] == "" else td['Cover_URL']
                    if ns == "Played":
                        bs = round((eg*2) + (ev*2) + (ea*2) + (ef*2) + (eb1*1) + (eb2*1), 1)
                        df.loc[df['Title'] == et, ['Status', 'Genre', 'Platform', 'ReleaseDate', 'OpenCritic', 'Base_Score', 'Elo_Rating', 'Cover_URL', 'S_Gameplay', 'S_Visuals', 'S_Audio', 'S_Fun', 'Bonus_1_Name', 'S_Bonus_1', 'Bonus_2_Name', 'S_Bonus_2']] = [ns, ng, ep, ey, eoc, bs, td['Elo_Rating'] if td['Elo_Rating']>0 else bs*15, curl, eg, ev, ea, ef, b1["name"], eb1, b2["name"], eb2]
                    else: df.loc[df['Title'] == et, ['Status', 'Platform', 'ReleaseDate', 'Cover_URL']] = [ns, ep, ey, curl]
                    save_database(df)
                    st.success("Database updated.")
                    st.rerun()
