import streamlit as st
import pandas as pd
import altair as alt
from streamlit_gsheets import GSheetsConnection
from datetime import date

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="Wordle Tournament", layout="wide")
st.title("Wordle Tournament & Solver")

# --- 2. CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# ⚠️ REPLACE THIS WITH YOUR ACTUAL GOOGLE SHEET LINK
SHEET_URL = "https://docs.google.com/spreadsheets/d/1vTpE4N_ieQ76Dp-wnjoAw3_dONrZo3NRqAtVxnvYiBA/edit?usp=sharing"

# --- 3. LOAD DATA ---
try:
    # Load Scores
    scores_df = conn.read(spreadsheet=SHEET_URL, worksheet="Scores")
    
    # Load Words
    words_df = conn.read(spreadsheet=SHEET_URL, worksheet="Words")

    # Handle empty/new sheets
    if scores_df.empty:
        scores_df = pd.DataFrame(columns=['Date', 'Player 1', 'Player 2', 'Player 3', 'Player 4'])
    
    if words_df.empty:
        words_df = pd.DataFrame(columns=['Word'])

except Exception as e:
    st.error(f"⚠️ Error loading data. Did you set the URL and rename the tabs to 'Scores' and 'Words'?\nError: {e}")
    st.stop()

# --- 4. APP LAYOUT (TABS) ---
tab1, tab2, tab3 = st.tabs(["🏆 Dashboard", "📝 Log Scores", "🗑️ Manage Words"])

# ==========================================
# TAB 1: DASHBOARD (Data & Charts)
# ==========================================
with tab1:
    st.header("Tournament Standings")
    
    # Display the raw data table
    st.dataframe(scores_df, use_container_width=True)

    # VISUALIZATION (Fixing the Altair Crash)
    if not scores_df.empty and len(scores_df) > 0:
        st.subheader("Score Trends")
        
        # We must 'melt' the data to make it friendly for Altair Charts
        # This converts wide format (Player 1, Player 2 columns) into long format
        melted_df = scores_df.melt(id_vars=['Date'], var_name='Player', value_name='Score')
        
        # Convert Score to numbers (just in case they are strings)
        melted_df['Score'] = pd.to_numeric(melted_df['Score'], errors='coerce')

        # Create the Chart
        line_chart = alt.Chart(melted_df).mark_line(point=True).encode(
            x='Date',
            y='Score',
            color='Player',
            tooltip=['Date', 'Player', 'Score']
        ).interactive()

        st.altair_chart(line_chart, use_container_width=True)
    else:
        st.info("Log some scores to see the chart!")

# ==========================================
# TAB 2: LOG SCORES (Add New Data)
# ==========================================
with tab2:
    st.header("Log New Scores")
    
    with st.form("score_form"):
        game_date = st.date_input("Date", date.today())
        
        # Create 4 columns for inputs
        c1, c2, c3, c4 = st.columns(4)
        with c1: p1 = st.text_input("Player 1 Score")
        with c2: p2 = st.text_input("Player 2 Score")
        with c3: p3 = st.text_input("Player 3 Score")
        with c4: p4 = st.text_input("Player 4 Score")
        
        submitted = st.form_submit_button("Save Scores")

        if submitted:
            # Create a new row
            new_data = pd.DataFrame([{
                "Date": game_date,
                "Player 1": p1,
                "Player 2": p2,
                "Player 3": p3,
                "Player 4": p4
            }])
            
            # Combine and Save
            updated_df = pd.concat([scores_df, new_data], ignore_index=True)
            
            try:
                conn.update(worksheet="Scores", data=updated_df)
                st.success("✅ Scores saved! Reloading...")
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving scores: {e}")

# ==========================================
# TAB 3: MANAGE WORDS (Remove Used Words)
# ==========================================
with tab3:
    st.header("Word List Manager")
    
    # Calculate remaining words
    st.metric("Words Remaining", len(words_df))

    # Dropdown to remove words
    current_word_list = words_df['Word'].astype(str).tolist()
    words_to_remove = st.multiselect("Select words to remove (burned):", options=current_word_list)

    if st.button("❌ Remove Selected Words"):
        if len(words_to_remove) > 0:
            # Filter out the selected words
            updated_words_df = words_df[~words_df['Word'].isin(words_to_remove)]
            
            try:
                conn.update(worksheet="Words", data=updated_words_df)
                st.success(f"✅ Removed: {', '.join(words_to_remove)}")
                import time
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error updating word list: {e}")
        else:
            st.warning("⚠️ Select at least one word to remove.")
