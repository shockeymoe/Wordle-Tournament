import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection  # <--- NEW IMPORT
from datetime import date
from collections import Counter

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="Wordle Tournament & Solver", layout="wide")

# 1. Setup the Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Define the URL to your Google Sheet
# (Paste your actual Google Sheet link here)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vTpE4N_ieQ76Dp-wnjoAw3_dONrZo3NRqAtVxnvYiBA/edit?gid=1475120069#gid=1475120069"

# 3. Load Data from Google Sheets
# Note: We use the 'worksheet' parameter to grab the correct tab

try:
    # Load Scores Tab
    scores_df = conn.read(spreadsheet=SHEET_URL, worksheet="Scores")
    
    # Load Words Tab
    words_df = conn.read(spreadsheet=SHEET_URL, worksheet="Words")
    
    # Handle case where the sheet might be empty or new
    if scores_df.empty:
        scores_df = pd.DataFrame(columns=['Date', 'Player 1', 'Player 2', 'Player 3', 'Player 4'])
    
    if words_df.empty:
        # Fallback if the Words tab is empty
        dummy_words = ["APPLE", "CRANE", "GHOST", "SLATE", "TRAIN", "BRICK", "JUMPY", "WALTZ", "OTTER", "AZURE"] 
        words_df = pd.DataFrame(dummy_words, columns=['Word'])

except Exception as e:
    st.error(f"⚠️ Error loading data from Google Sheets: {e}")
    st.stop()

# 4. Prepare the list (same as before)
all_words = words_df['Word'].astype(str).str.upper().tolist()

# --- HELPER FUNCTIONS ---
def reset_solver():
    """Callback to clear solver state immediately."""
    st.session_state.guesses = []
    st.session_state.solver_input = ""

# --- SIDEBAR: NAVIGATION ---
st.sidebar.title("Wordle HQ")
app_mode = st.sidebar.radio("Go to:", ["🏆 Tournament Scores", "🧠 Solver & Game Interface"])

# --- TAB 1: TOURNAMENT SCORES ---
if app_mode == "🏆 Tournament Scores":
    st.title("🏆 Tournament Scoreboard")

    # --- DYNAMIC PLAYER DETECTION ---
    scores_df.columns = scores_df.columns.str.strip() # Clean headers
    player_cols = [col for col in scores_df.columns if col.lower() != 'date']

    if not player_cols:
        st.error("⚠️ No player columns found in CSV. Please ensure your CSV has 'Date' and player names.")
    else:
        with st.expander("📝 Enter Daily Scores", expanded=True):
            with st.form("score_form"):
                inputs = {}
                cols = st.columns(len(player_cols))
                
                for idx, player in enumerate(player_cols):
                    with cols[idx]:
                        inputs[player] = st.number_input(f"{player}", min_value=1, max_value=6, value=4)
                
                submitted = st.form_submit_button("Submit Scores")
                
                if submitted:
                    new_row = {'Date': date.today()}
                    for player, score in inputs.items():
                        new_row[player] = score
                        
                    scores_df = pd.concat([scores_df, pd.DataFrame([new_row])], ignore_index=True)
                    scores_df.to_csv(SCORES_FILE, index=False)
                    st.success("Scores saved!")
                    st.rerun()

        st.divider()
        
        # Check if we have data to graph
        if not scores_df.empty:
            # --- DATA PREP FOR GRAPHS ---
            scores_df['Date'] = pd.to_datetime(scores_df['Date'])
            
            # Force numeric conversion for all detected player columns
            for col in player_cols:
                scores_df[col] = pd.to_numeric(scores_df[col], errors='coerce')

            # --- CUSTOM COLORS (HEX CODES) ---
            # Blue, Teal, Green, Pink
            default_colors = ['#153CFF', '#2BD7E9', '#2E8B57', '#ED83ED']
            
            domain = player_cols
            # Logic to handle if you have more than 4 players (defaults extra players to gray)
            range_colors = default_colors[:len(player_cols)] if len(player_cols) <= 4 else default_colors + ['gray']*(len(player_cols)-4)
            
            # PREPARE DATA (Long Format)
            melted_df = scores_df.melt(id_vars=['Date'], value_vars=player_cols, var_name='Player', value_name='Score')
            melted_df = melted_df.dropna(subset=['Score'])

            # --- GRAPH 1: MONTHLY AVERAGE TREND ---
            st.subheader("Monthly Performance")
            
            line_chart = alt.Chart(melted_df).mark_line(point=True).encode(
                x=alt.X('yearmonth(Date):T', title='Month'),
                y=alt.Y('mean(Score):Q', title='Average Score', scale=alt.Scale(domain=[2, 5])),
                color=alt.Color('Player:N', scale=alt.Scale(domain=domain, range=range_colors)),
                tooltip=['Player', 'yearmonth(Date)', 'mean(Score)']
            ).properties(
                title="Average Monthly Score per Player"
            ).interactive()
            
            st.altair_chart(line_chart, use_container_width=True)

# --- GRAPH 2: LEADERBOARD (Layered Bar + Text) ---
            st.subheader("Leaderboard (Yearly Average)")
            
            # Calculate averages
            avg_data = melted_df.groupby('Player')['Score'].mean().reset_index()
            
            # 1. Base Chart (The Bars)
            base = alt.Chart(avg_data).encode(
                x=alt.X('Player:N', axis=None),
                y=alt.Y('Score:Q', title='Average Score'),
                color=alt.Color('Player:N', scale=alt.Scale(domain=domain, range=range_colors))
            )

            # 2. Bar Layer
            bars = base.mark_bar()

            # 3. Text Layer (The Numbers)
            text = base.mark_text(
                align='center',
                baseline='bottom',
                dy=-5,  # Shift text up by 5 pixels so it sits on top
                color='black' # Ensure text is visible
            ).encode(
                text=alt.Text('Score:Q', format='.2f') # Format to 2 decimal places
            )

            # Combine them into one chart
            chart = (bars + text).properties(
                width=400,
                height=300
            )
            
            st.altair_chart(chart)

        else:
            st.info("No scores entered yet. Graphs will appear here once data is available.")

    # Show raw data at the bottom
    with st.expander("View Raw Data"):
        st.dataframe(scores_df.sort_values(by='Date', ascending=False), width='stretch')


# --- TAB 2: SOLVER & GAME INTERFACE ---
elif app_mode == "🧠 Solver & Game Interface":
    st.title("🧠 Daily Solver")

    col_game, col_tools = st.columns([1, 1])

    with col_game:
        st.subheader("1. Remove Today's Answer")
        
        if 'removal_msg' in st.session_state and st.session_state.removal_msg:
            st.success(st.session_state.removal_msg)
            st.session_state.removal_msg = None

        st.info(f"Words remaining in database: {len(all_words)}")
        
        with st.form("remove_word", clear_on_submit=True):
            todays_word = st.text_input("Enter Today's Winning Word:").upper().strip()
            remove_btn = st.form_submit_button("Remove from Database")
            
            if remove_btn and todays_word:
                if todays_word in all_words:
                    all_words.remove(todays_word)
                    pd.DataFrame(all_words, columns=['Word']).to_csv(WORDS_FILE, index=False)
                    st.session_state.removal_msg = f"Successfully removed '{todays_word}'!"
                    st.rerun()
                else:
                    st.error("Word not found (or already removed).")

    with col_tools:
        header_col, btn_col = st.columns([3, 1])
        
        with header_col:
            st.subheader("2. The Solver")
        
        with btn_col:
            st.button("Reset", on_click=reset_solver, use_container_width=True)

        st.write("Enter your guess and feedback to see viable options.")

        if 'guesses' not in st.session_state:
            st.session_state.guesses = []
        
        guess_input = st.text_input("Type your guess (5 letters):", max_chars=5, key="solver_input").upper()
        
        if guess_input and len(guess_input) == 5:
            cols = st.columns(5)
            feedback = []
            
            for i, letter in enumerate(guess_input):
                color = cols[i].selectbox(
                    f"{letter}", 
                    ["⬛ Grey", "🟨 Yellow", "🟩 Green"], 
                    key=f"char_{i}_{guess_input}"
                )
                feedback.append(color)

            if st.button("Apply Logic"):
                st.session_state.guesses.append({'word': guess_input, 'feedback': feedback})

        # --- SOLVER LOGIC ---
        possible_words = all_words.copy()

        for entry in st.session_state.guesses:
            word = entry['word']
            fb = entry['feedback']
            
            for i, (char, status) in enumerate(zip(word, fb)):
                if "🟩 Green" in status:
                    possible_words = [w for w in possible_words if len(w) > i and w[i] == char]
                elif "🟨 Yellow" in status:
                    possible_words = [w for w in possible_words if char in w and (len(w) > i and w[i] != char)]
                elif "⬛ Grey" in status:
                    possible_words = [w for w in possible_words if char not in w]

        # --- RANKING LOGIC ---
        letter_counts = Counter("".join(possible_words))
        
        def calculate_word_score(word):
            unique_chars = set(word)
            score = sum(letter_counts[char] for char in unique_chars)
            return score

        if possible_words:
            ranked_data = []
            for w in possible_words:
                ranked_data.append({
                    "Word": w, 
                    "Score": calculate_word_score(w)
                })
            
            ranked_df = pd.DataFrame(ranked_data)
            ranked_df = ranked_df.sort_values(by="Score", ascending=False).reset_index(drop=True)
            ranked_df.index += 1 

            st.divider()
            
            st.write("Current Guesses:")
            for g in st.session_state.guesses:
                st.text(f"{g['word']} - { ''.join([x[0] for x in g['feedback']]) }")

            st.metric("Viable Answers", len(possible_words))
            
            st.subheader("Top Suggestions")
            st.dataframe(ranked_df, width='stretch', height=300)

            with st.expander("View Letter Frequency Stats"):
                freq_df = pd.DataFrame.from_dict(letter_counts, orient='index', columns=['Count'])
                st.bar_chart(freq_df.sort_values('Count', ascending=False))
        
        else:

            st.error("No words match your criteria! Check your inputs.")


