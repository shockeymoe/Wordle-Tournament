import streamlit as st
import pandas as pd
import os
import altair as alt
from datetime import date
from collections import Counter

# --- CONFIGURATION & SETUP ---
st.set_page_config(page_title="Wordle Tournament & Solver", layout="wide")

SCORES_FILE = 'Scores.csv'
WORDS_FILE = 'word_list.csv'

# --- HELPER FUNCTIONS ---
def save_dataframe_safely(df, filename):
    try:
        df.to_csv(filename, index=False)
        return True, None
    except PermissionError:
        return False, f"⚠️ **Permission Denied:** '{filename}' is open. Close Excel and try again."
    except Exception as e:
        return False, f"⚠️ Error: {e}"

def reset_solver():
    st.session_state.guesses = []
    st.session_state.solver_input = ""

# --- LOAD DATA ---
if not os.path.exists(SCORES_FILE):
    st.error(f"❌ Missing: {SCORES_FILE}")
    st.stop()
else:
    scores_df = pd.read_csv(SCORES_FILE)
    scores_df['Date'] = scores_df['Date'].astype(str).str.strip()

if not os.path.exists(WORDS_FILE):
    st.error(f"❌ Missing: {WORDS_FILE}")
    st.stop()
else:
    words_df = pd.read_csv(WORDS_FILE)
    words_df.columns = [c.capitalize() for c in words_df.columns]

# Weighting Setup
if 'Weight' not in words_df.columns:
    words_df['Weight'] = 1.0

word_weights = dict(zip(words_df['Word'].astype(str).str.upper(), words_df['Weight']))
all_words = words_df['Word'].astype(str).str.upper().tolist()

# --- SIDEBAR ---
st.sidebar.title("Wordle HQ")
app_mode = st.sidebar.radio("Navigation", ["🏆 Scoreboard", "🧠 Solver"])

# ==========================================
# TAB 1: TOURNAMENT SCOREBOARD
# ==========================================
if app_mode == "🏆 Scoreboard":
    st.title("🏆 Tournament Scoreboard")
    player_cols = [col for col in scores_df.columns if col.lower() != 'date']

    if not player_cols:
        st.error("⚠️ No players found in CSV.")
    else:
        with st.container(border=True):
            st.caption("📝 **Quick Score Entry**")
            c_date, c_player, c_score, c_btn = st.columns([2, 2, 1, 1])
            with c_date:
                input_date = st.date_input("Date", value=date.today(), label_visibility="collapsed")
                input_date_str = input_date.strftime("%Y-%m-%d")
            with c_player:
                selected_player = st.selectbox("Player", player_cols, label_visibility="collapsed")
            
            current_val = 4
            existing_row = scores_df[scores_df['Date'] == input_date_str]
            if not existing_row.empty:
                val = existing_row.iloc[0][selected_player]
                if pd.notna(val) and str(val).strip() != '':
                    try:
                        current_val = int(float(val))
                    except:
                        pass
            with c_score:
                new_score = st.number_input("Score", min_value=1, max_value=7, value=current_val, label_visibility="collapsed")
            with c_btn:
                if st.button("💾 Save", use_container_width=True):
                    if not existing_row.empty:
                        row_idx = existing_row.index[0]
                        scores_df.at[row_idx, selected_player] = new_score
                    else:
                        new_row = {'Date': input_date_str, selected_player: new_score}
                        scores_df = pd.concat([scores_df, pd.DataFrame([new_row])], ignore_index=True)

                    success, error_msg = save_dataframe_safely(scores_df, SCORES_FILE)
                    if success:
                        st.success(f"Saved: {selected_player} ({new_score})")
                        st.rerun()
                    else:
                        st.error(error_msg)

        if not scores_df.empty:
            st.markdown("### Performance")
            graph_df = scores_df.copy()
            graph_df['Date'] = pd.to_datetime(graph_df['Date'], errors='coerce')
            for col in player_cols:
                graph_df[col] = pd.to_numeric(graph_df[col], errors='coerce')

            default_colors = ['#0000FF', '#00DFDA', '#00D000', '#FD00F2']
            domain = player_cols
            range_colors = default_colors[:len(player_cols)] if len(player_cols) <= 4 else default_colors + ['gray']*(len(player_cols)-4)
            
            melted_df = graph_df.melt(id_vars=['Date'], value_vars=player_cols, var_name='Player', value_name='Score').dropna(subset=['Score'])

            line_chart = alt.Chart(melted_df).mark_line(point=True).encode(
                x=alt.X('yearmonth(Date):T', title=None),
                y=alt.Y('mean(Score):Q', title='Avg Score', scale=alt.Scale(domain=[2, 5])),
                color=alt.Color('Player:N', scale=alt.Scale(domain=domain, range=range_colors)),
                tooltip=['Player', 'yearmonth(Date)', 'mean(Score)']
            ).properties(height=300).interactive(bind_y=False)
            
            st.altair_chart(line_chart, width='stretch')

            avg_data = melted_df.groupby('Player')['Score'].mean().reset_index()
            bar_chart = alt.Chart(avg_data).mark_bar().encode(
                y=alt.Y('Player:N', title=None), 
                x=alt.X('Score:Q', title='Avg Score'),
                color=alt.Color('Player:N', legend=None, scale=alt.Scale(domain=domain, range=range_colors)),
                tooltip=['Player', 'Score']
            ).properties(height=250)
            
            col1, col2 = st.columns(2)
            with col1:
                st.altair_chart(bar_chart, width='stretch')
            with st.expander("View Raw Data"):
                st.dataframe(scores_df.sort_values(by='Date', ascending=False), width='stretch')

# ==========================================
# TAB 2: DAILY SOLVER
# ==========================================
elif app_mode == "🧠 Solver":
    
    # Check if a removal just happened to show the verification message after rerun
    if 'last_removed' in st.session_state:
        st.success(st.session_state.last_removed)
        del st.session_state.last_removed

    with st.expander("🛠️ Admin: Remove Today's Answer"):
        c_rem_1, c_rem_2 = st.columns([3, 1])
        with c_rem_1:
            todays_word = st.text_input("Winning Word:", key="remove_input", label_visibility="collapsed", placeholder="Enter word to remove...").upper().strip()
        with c_rem_2:
            if st.button("Remove"):
                if not todays_word:
                    st.warning("Please enter a word.")
                elif todays_word in all_words:
                    updated_words_df = words_df[words_df['Word'].str.upper() != todays_word]
                    success, error_msg = save_dataframe_safely(updated_words_df, WORDS_FILE)
                    if success:
                        # Store message in session state so it survives the rerun
                        st.session_state.last_removed = f"✅ Verified: '{todays_word}' has been removed from {WORDS_FILE}."
                        st.rerun()
                    else:
                        st.error(error_msg)
                else:
                    st.info(f"ℹ️ The word '{todays_word}' is not in the list.")

    st.title("🧠 Daily Solver")
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### Enter Guess")
        if 'guesses' not in st.session_state:
            st.session_state.guesses = []
        
        guess_input = st.text_input("Type word:", max_chars=5, key="solver_input", label_visibility="collapsed", placeholder="TYPE GUESS HERE").upper()

        # Feedback Grid (Only if guess is typed)
        feedback = []
        if guess_input and len(guess_input) == 5:
            st.caption("Set colors:")
            cols = st.columns(5)
            for i, letter in enumerate(guess_input):
                with cols[i]:
                    st.markdown(f"<h3 style='text-align: center; margin-bottom: 0px;'>{letter}</h3>", unsafe_allow_html=True)
                    color = st.selectbox("Color", ["⬛", "🟨", "🟩"], key=f"char_{i}_{guess_input}", label_visibility="collapsed")
                    full_text = "⬛ Grey" if color == "⬛" else "🟨 Yellow" if color == "🟨" else "🟩 Green"
                    feedback.append(full_text)

            st.write("")
            b1, b2 = st.columns(2)
            with b1:
                if st.button("🚀 Apply Logic", use_container_width=True):
                    st.session_state.guesses.append({'word': guess_input, 'feedback': feedback})
            with b2:
                # Reset always available
                st.button("🔄 Reset", on_click=reset_solver, use_container_width=True, key="reset_active")
        else:
            # RESET BUTTON: Always available when input is empty or invalid
            st.write("")
            st.button("🔄 Reset Solver", on_click=reset_solver, use_container_width=True, key="reset_idle")

    with col_right:
        st.markdown("### Analysis")
        possible_words = all_words.copy()
        
        global_confirmed_present = set()
        for entry in st.session_state.guesses:
            for char, status in zip(entry['word'], entry['feedback']):
                if "🟩" in status or "🟨" in status:
                    global_confirmed_present.add(char)

        for entry in st.session_state.guesses:
            word, fb = entry['word'], entry['feedback']
            local_confirmed_present = {char for char, status in zip(word, fb) if "🟩" in status or "🟨" in status}
            
            for i, (char, status) in enumerate(zip(word, fb)):
                if "🟩" in status:
                    possible_words = [w for w in possible_words if len(w) > i and w[i] == char]
                elif "🟨" in status:
                    possible_words = [w for w in possible_words if char in w and (len(w) > i and w[i] != char)]
                elif "⬛" in status:
                    if char in global_confirmed_present or char in local_confirmed_present:
                        possible_words = [w for w in possible_words if len(w) > i and w[i] != char]
                    else:
                        possible_words = [w for w in possible_words if char not in w]

        # --- RANKING ---
        letter_counts = Counter("".join(possible_words))
        
        if possible_words:
            ranked_data = []
            for w in possible_words:
                raw_score = sum(letter_counts[char] for char in set(w))
                weight = word_weights.get(w, 0.02)
                ranked_data.append({
                    "Word": w, 
                    "Raw Score": raw_score, 
                    "Weight": weight,
                    "Final Score": round(raw_score * weight, 2),
                    "Type": "Original" if weight == 1.0 else "Expanded"
                })
            
            ranked_df = pd.DataFrame(ranked_data).sort_values(by=["Final Score", "Raw Score"], ascending=False).reset_index(drop=True)
            ranked_df.index += 1 

            m1, m2 = st.columns(2)
            m1.metric("Viable Words", len(possible_words))
            m2.metric("Top Final Score", ranked_df.iloc[0]['Final Score'] if not ranked_df.empty else 0)

            if st.session_state.guesses:
                st.caption("History:")
                for g in st.session_state.guesses:
                    icon_str = "".join([x[0] for x in g['feedback']])
                    st.text(f"{g['word']} {icon_str}")

            st.markdown("#### Top Suggestions")
            st.dataframe(ranked_df, width='stretch', height=350)
        else:
            st.error("No words match criteria.")