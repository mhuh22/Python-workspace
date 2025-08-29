import os
from openai import OpenAI
import tiktoken
import streamlit as st

# api_key = os.getenv("OPENAI_API_KEY")
api_key = st.secrets['openai_api_key']

client = OpenAI(api_key=api_key)
MODEL = "gpt-4.1-nano-2025-04-14"
TEMPERATURE = 0.7
MAX_TOKENS = 100
TOKEN_BUDGET = 1000
SYSTEM_PROMPT = "You are a fed up and sassy assistant who hates answering questions."

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

def get_encoding(model):
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        print(f"Warning: Tokenizer for model '{model}' not found. Falling back to 'cl100k_base'.")
        return tiktoken.get_encoding("cl100k_base")

ENCODING = get_encoding(MODEL)

def count_tokens(text):
    return len(ENCODING.encode(text))

def total_tokens_used(messages):
    try:
        return sum(count_tokens(msg["content"]) for msg in messages)
    except Exception as e:
        print(f"[token count error]: {e}")
        return 0

def enforce_token_budget(messages, budget=TOKEN_BUDGET):
    try:
        while total_tokens_used(messages) > budget:
            if len(messages) <= 2:
                break 
            messages.pop(1)
    except Exception as e:
        print(f"[token budget error]: {e}")

def chat(user_input, temperature=TEMPERATURE, max_tokens=MAX_TOKENS):
    messages = st.session_state.messages
    messages.append({"role": "user", "content": user_input})

    enforce_token_budget(messages)

    with st.spinner("Thinking..."):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})
    return reply

st.title("Sassy Chatbot")
st.sidebar.header("Options")
st.sidebar.write("This is a demo of a sassy chatbot using OpenAI's API.")

max_tokens = st.sidebar.slider("Max Tokens", 1, 250, 100)
temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.7)
system_message_type = st.sidebar.selectbox("System Message",("Sassy Assistant", "Angry Assistant", "Custom"))

if system_message_type == "Sassy Assistant":
    SYSTEM_PROMPT = "You are a sassy assistant that is fed up with answering questions."
elif system_message_type == "Angry Assistant":
    SYSTEM_PROMPT = "You are an angry assistant that likes yelling in all caps."
elif system_message_type == "Custom":
    SYSTEM_PROMPT = st.sidebar.text_area("Custom System Message", "Enter your custom system message here.")
else:
    SYSTEM_PROMPT = "You are a helpful assistant."

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

if st.sidebar.button("Apply New System Message"):
    st.session_state.messages[0] = {"role": "system", "content": SYSTEM_PROMPT}
    st.success("System message updated.")

if st.sidebar.button("Reset Conversation"):
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    st.success("Conversation reset.")

if prompt := st.chat_input("What is up?"):
    reply = chat(prompt, temperature=temperature, max_tokens=max_tokens)