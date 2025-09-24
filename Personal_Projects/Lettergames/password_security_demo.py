import streamlit as st
import secrets
import string
import math
import time

# Try optional stronger estimator
try:
    from zxcvbn import zxcvbn
    HAS_ZXCVBN = True
except Exception:
    HAS_ZXCVBN = False

# --- Utilities ---
def charsets_used(pw: str):
    sets = {
        "lower": any(c.islower() for c in pw),
        "upper": any(c.isupper() for c in pw),
        "digits": any(c.isdigit() for c in pw),
        "symbols": any((not c.isalnum()) for c in pw),
    }
    return sets

def naive_entropy(pw: str):
    # Estimate entropy assuming independent chars drawn from used charset
    use = charsets_used(pw)
    pool = 0
    if use["lower"]:
        pool += 26
    if use["upper"]:
        pool += 26
    if use["digits"]:
        pool += 10
    if use["symbols"]:
        # approximate printable punctuation
        pool += 32
    if pool == 0:
        return 0.0
    ent = math.log2(pool) * len(pw)
    return ent

def entropy_to_guesses(entropy_bits):
    # approx guesses needed = 2^entropy
    return 2 ** entropy_bits

def friendly_time(seconds):
    # nice human readable time
    intervals = [
        ("years", 60*60*24*365),
        ("days", 60*60*24),
        ("hours", 60*60),
        ("minutes", 60),
        ("seconds", 1),
    ]
    out = []
    for name, sec in intervals:
        if seconds >= sec:
            val = int(seconds // sec)
            out.append(f"{val} {name}")
            seconds -= val * sec
        if len(out) >= 2:
            break
    return ", ".join(out) if out else "less than 1 second"

# Common attack speeds to show ranges (guesses per second)
ATTACK_PROFILES = {
    "Online (throttled)": 10,           # e.g., server rate limited
    "Moderate offline (single GPU)": 1e9,
    "High-end offline (GPU cluster)": 1e11,
    "State actor (massive cluster)": 1e14,
}

COMMON_PASSWORDS = {
    # tiny sample; ideally expand or load a full list locally
    "123456", "password", "123456789", "qwerty", "111111", "12345678",
    "abc123", "password1", "iloveyou"
}

# --- Generators ---
def generate_random(length=16, use_upper=True, use_digits=True, use_symbols=True, exclude_ambiguous=True):
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase if use_upper else ""
    digits = string.digits if use_digits else ""
    symbols = string.punctuation if use_symbols else ""
    pool = lower + upper + digits + symbols
    if exclude_ambiguous:
        for ch in "Il1O0`'\"\\/|":
            pool = pool.replace(ch, "")
    if not pool:
        raise ValueError("Character set is empty.")
    return "".join(secrets.choice(pool) for _ in range(length))

# Simple diceware-like word generator (reads a tiny built-in wordlist)
DICEWARE_WORDS = ["correct", "horse", "battery", "staple", "orange", "candle", "garden", "stream", "planet", "silver"]
def generate_words(n_words=4, separator="-"):
    words = [secrets.choice(DICEWARE_WORDS) for _ in range(n_words)]
    return separator.join(words)

# --- Scoring wrapper ---
def score_password(pw: str):
    result = {}
    result["length"] = len(pw)
    result["contains"] = charsets_used(pw)
    result["common_password"] = pw in COMMON_PASSWORDS

    if HAS_ZXCVBN and pw:
        try:
            zx = zxcvbn(pw)
            result["zxcvbn_score"] = zx.get("score", None)      # 0-4
            result["zxcvbn_feedback"] = zx.get("feedback", {})
            # zxcvbn returns guesses estimate
            result["guesses"] = zx.get("guesses", None)
            if result["guesses"] is not None:
                result["entropy_bits"] = math.log2(result["guesses"]) if result["guesses"]>0 else 0.0
        except Exception:
            result["zxcvbn_score"] = None
            result["guesses"] = None
            result["entropy_bits"] = naive_entropy(pw)
    else:
        result["zxcvbn_score"] = None
        ent = naive_entropy(pw)
        result["entropy_bits"] = ent
        result["guesses"] = entropy_to_guesses(ent) if ent>0 else 0

    # simple qualitative strength
    bits = result.get("entropy_bits", 0) or 0
    if bits < 28:
        strength = "Very weak"
    elif bits < 36:
        strength = "Weak"
    elif bits < 60:
        strength = "Reasonable"
    elif bits < 80:
        strength = "Strong"
    else:
        strength = "Very strong"
    result["strength_label"] = strength
    return result

# --- Streamlit UI ---
st.set_page_config(page_title="Password Strength & Generator", layout="centered")

st.title("🔐 Password Strength Checker + Generator")
st.markdown(
    "Educational demo: estimate password strength, get recommendations, and generate secure passwords. "
    "**Do not paste live/real passwords used on your accounts.**"
)

col1, col2 = st.columns([2,1])

with col1:
    st.subheader("Evaluate a password")
    pw_input = st.text_input("Enter a password to evaluate (use a test/example, not a live password)", type="default")
    show_mask = st.checkbox("Mask input (recommended)", value=True)
    # If user wants masking, use password widget instead
    if show_mask:
        pw_input = st.text_input("Password (masked)", type="password", value=pw_input)

    if pw_input:
        res = score_password(pw_input)
        st.metric("Strength", res["strength_label"])
        st.write(f"Length: {res['length']} characters")
        used = ", ".join([k for k,v in res["contains"].items() if v]) or "none"
        st.write(f"Character sets used: {used}")

        if res.get("zxcvbn_score") is not None:
            st.write(f"zxcvbn score (0-4): {res['zxcvbn_score']}")
            fb = res.get("zxcvbn_feedback") or {}
            if fb.get("warning"):
                st.warning(fb["warning"])
            if fb.get("suggestions"):
                for s in fb["suggestions"]:
                    st.info(s)

        st.write("Estimated entropy: **{:.1f} bits**".format(res.get("entropy_bits", 0)))

        # Estimate crack times across profiles
        st.subheader("Estimated time to crack (illustrative)")
        for name, gps in ATTACK_PROFILES.items():
            guesses = res.get("guesses") or entropy_to_guesses(res.get("entropy_bits", 0))
            # average-case: half the search space
            seconds = guesses / gps / 2.0 if guesses>0 else 0
            st.write(f"- {name}: {friendly_time(seconds)} (at {int(gps):,} guesses/sec)")

        if res["common_password"]:
            st.error("This password is in a small common-password list — avoid it.")
        else:
            st.success("Not a tiny common-password hit (but check a larger list if in doubt).")

        st.subheader("Suggestions")
        suggestions = []
        if res["length"] < 12:
            suggestions.append("Increase length — longer passwords are the single biggest improvement.")
        if not res["contains"]["symbols"]:
            suggestions.append("Add symbols or punctuation.")
        if not res["contains"]["digits"]:
            suggestions.append("Add digits.")
        if not res["contains"]["upper"]:
            suggestions.append("Add uppercase letters or use mixed-case.")
        if suggestions:
            for s in suggestions:
                st.info(s)
        else:
            st.write("Looks good by basic heuristics.")

with col2:
    st.subheader("Generate a password")
    mode = st.selectbox("Generator mode", ["Random characters", "Diceware-style words"])
    if mode == "Random characters":
        length = st.slider("Length", 8, 64, 16)
        use_upper = st.checkbox("Include uppercase", value=True)
        use_digits = st.checkbox("Include digits", value=True)
        use_symbols = st.checkbox("Include symbols", value=True)
        exclude_amb = st.checkbox("Exclude ambiguous chars (e.g., l, 1, O, 0)", value=True)
        if st.button("Generate random password"):
            gen = generate_random(length, use_upper, use_digits, use_symbols, exclude_ambiguous=exclude_amb)
            st.code(gen)
            st.write("Copy it and store it in a password manager (recommended).")
            st.experimental_set_query_params()
    else:
        n_words = st.slider("Number of words", 3, 6, 4)
        sep = st.text_input("Separator", "-")
        if st.button("Generate word password"):
            gen = generate_words(n_words, separator=sep)
            st.code(gen)
            st.write("Diceware-like passphrases (several common words) are easier to remember.")

st.markdown("---")
st.write("**Notes & best practice:**")
st.markdown(
"""
- Use a reputable **password manager** (KeePass, Bitwarden, 1Password, etc.) to store long unique passwords.
- Prefer passphrases (multiple random words) or long random character strings.
- Avoid reusing passwords across sites.
- This demo gives **estimates** only. Real attacker capability varies.
"""
)

st.caption("This app is for educational / defensive use only. Do not use it to attack accounts or to check other people's credentials.")
