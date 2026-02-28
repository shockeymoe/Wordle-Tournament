import pandas as pd
import os

WORDS_FILE = 'word_list.csv'
ARCHIVE_URL = "https://mdahlman.github.io/wordle/"

print("Fetching past Wordle answers from the archive...")

try:
    # 1. Read the HTML table directly from the website
    dfs = pd.read_html(ARCHIVE_URL)
    archive_df = dfs[0] # Grab the first table on the page
    
    # 2. Extract the 'Word' column and clean it up (make it uppercase)
    past_words = archive_df['Word'].dropna().astype(str).str.upper().tolist()
    print(f"Successfully fetched {len(past_words)} past answers.")

    # 3. Load your local word list
    if os.path.exists(WORDS_FILE):
        my_words_df = pd.read_csv(WORDS_FILE)
        
        # Ensure the 'Weight' column exists, defaulting to 1.0 if it doesn't
        if 'Weight' not in my_words_df.columns:
            my_words_df['Weight'] = 1.0
            
        # 4. Find all words in your CSV that match the past answers list
        # Using .isin() makes this instantly check the whole column
        mask = my_words_df['Word'].str.upper().isin(past_words)
        
        # 5. Overwrite the weight for those specific words
        my_words_df.loc[mask, 'Weight'] = 0.01
        
        # 6. Save the file
        my_words_df.to_csv(WORDS_FILE, index=False)
        print(f"Successfully updated the weights in {WORDS_FILE}!")
    else:
        print(f"Error: Could not find '{WORDS_FILE}' in the current folder.")

except Exception as e:
    print(f"An error occurred: {e}")