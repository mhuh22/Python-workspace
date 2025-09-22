
import random
from collections import Counter
import string
import streamlit as st

# ----------------------------
# Data & Helpers
# ----------------------------
DEFAULT_WORDS = """
apple banana mango strawberry 
orange grape pineapple apricot lemon coconut watermelon 
cherry papaya berry peach lychee muskmelon
""".split()

HANGMAN_PICS = [
    """
    
    
    
        
    =======
    """,
    """
      |
      |
      |
      |
    =======
    """,
    """
      +---.
      |
      |
      |
      |
    =======
    """,
    """
      +---.
      |   O
      |
      |
      |
    =======
    """,
    """
      +---.
      |   O
      |   |
      |
      |
    =======
    """,
    """
      +---.
      |   O
      |  /|
      |
      |
    =======
    """,
    """
      +---.
      |   O
      |  /|\\
      |
      |
    =======
    """,
    """
      +---.
      |   O
      |  /|\\
      |  /
      |
    =======
    """,
    """
      +---.
      |   O
      |  /|\\
      |  / \\
      |
    =======
    """,
]

def pick_word(words):
    return random.choice(words).lower().strip()

def masked_word(word, guessed):
    return " ".join([c if c in guessed else "_" for c in word])

def is_win(word, guessed):
    # Player wins if all letters of the word are in guessed set
    return set(word).issubset(guessed)

def stage_index(max_chances, remaining):
    used = max_chances - remaining
    # Clamp to valid range
    return min(used, len(HANGMAN_PICS) - 1)

# ----------------------------
# App State Initialization
# ----------------------------
if "word" not in st.session_state:
    st.session_state.word = pick_word(DEFAULT_WORDS)
if "guessed" not in st.session_state:
    st.session_state.guessed = set()
if "remaining" not in st.session_state:
    # Classic hangman uses about 6–8 lives; we also tie it loosely to word length
    st.session_state.max_chances = max(7, min(10, len(st.session_state.word) + 2))
    st.session_state.remaining = st.session_state.max_chances
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "message" not in st.session_state:
    st.session_state.message = ""

# ----------------------------
# Sidebar Controls
# ----------------------------
st.sidebar.header("Game Controls")
with st.sidebar.expander("New Game", expanded=True):
    custom_word = st.text_input(
        "Custom word (optional)", 
        value="", 
        type="password", 
        help="Enter a secret word for 2‑player mode. Leave blank to use random fruit."
    )
    allow_non_fruit = st.checkbox("Allow any letters (not just fruit hint)", value=False)
    randomize_btn = st.button("Start New Game")

    if randomize_btn:
        if custom_word.strip():
            candidate = "".join([c for c in custom_word.lower() if c in string.ascii_lowercase])
            if len(candidate) < 3:
                st.warning("Custom word must be at least 3 letters and only letters a‑z.")
            else:
                st.session_state.word = candidate
        else:
            st.session_state.word = pick_word(DEFAULT_WORDS)

        st.session_state.guessed = set()
        st.session_state.max_chances = max(7, min(10, len(st.session_state.word) + 2))
        st.session_state.remaining = st.session_state.max_chances
        st.session_state.game_over = False
        st.session_state.message = ""
        st.success("New game started!")

# ----------------------------
# Main UI
# ----------------------------
st.title("🍎 Hangman (Streamlit)")
hint = "word is a name of a fruit" if st.session_state.word in DEFAULT_WORDS else "custom word"
st.caption(f"Guess the word — hint: **{hint}**")

# Hangman drawing
pic_idx = stage_index(st.session_state.max_chances, st.session_state.remaining)
st.code(HANGMAN_PICS[pic_idx])

# Word display
st.subheader("Word")
st.write(f"**{masked_word(st.session_state.word, st.session_state.guessed)}**")

# Status
alphabet = " ".join(sorted(st.session_state.guessed)) if st.session_state.guessed else "—"
st.write(f"Guessed letters: {alphabet}")
st.write(f"Chances remaining: **{st.session_state.remaining}** / {st.session_state.max_chances}")

# ----------------------------
# Guess Form
# ----------------------------
def process_guess(letter: str):
    letter = letter.lower().strip()
    if not letter or len(letter) != 1 or letter not in string.ascii_lowercase:
        st.session_state.message = "Enter a single letter (a‑z)."
        return
    if letter in st.session_state.guessed:
        st.session_state.message = f"You already guessed '{letter}'."
        return

    st.session_state.guessed.add(letter)

    if letter not in st.session_state.word:
        st.session_state.remaining -= 1
        st.session_state.message = f"'{letter}' is not in the word."
    else:
        st.session_state.message = f"Nice! '{letter}' is in the word."

    # Check end conditions
    if is_win(st.session_state.word, st.session_state.guessed):
        st.balloons()
        st.session_state.game_over = True
        st.session_state.message = f"🎉 Congratulations! You guessed the word: **{st.session_state.word}**"
    elif st.session_state.remaining <= 0:
        st.session_state.game_over = True
        st.session_state.message = f"❌ You lost! The word was **{st.session_state.word}**."

with st.form("guess_form", clear_on_submit=True):
    guess = st.text_input("Enter a letter to guess:", max_chars=1, help="Type a single letter then press Submit.")
    submitted = st.form_submit_button("Submit Guess", disabled=st.session_state.game_over)
    if submitted and not st.session_state.game_over:
        process_guess(guess)

# Feedback message
if st.session_state.message:
    st.info(st.session_state.message)

# Play again button
col1, col2 = st.columns(2)
if col1.button("🔁 Play Again"):
    st.session_state.word = pick_word(DEFAULT_WORDS)
    st.session_state.guessed = set()
    st.session_state.max_chances = max(7, min(10, len(st.session_state.word) + 2))
    st.session_state.remaining = st.session_state.max_chances
    st.session_state.game_over = False
    st.session_state.message = ""

# Optional: reveal (for debugging / teaching). Comment this out in production.
with st.expander("Reveal (for teaching/demo)"):
    st.text(f"Secret word: {st.session_state.word}")
