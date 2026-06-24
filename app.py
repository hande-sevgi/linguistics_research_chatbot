import os
import streamlit as st
from openai import OpenAI

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="Linguistics Research Assistant",
    page_icon="💬",
    layout="centered"
)

st.title("Linguistics Research Assistant")
st.caption("Enter keywords or a topic to get a curated list of relevant linguistic works.")

# -----------------------------
# API key setup
# -----------------------------
# For local use:
# export OPENAI_API_KEY="your_key_here"
#
# For Streamlit Cloud:
# add OPENAI_API_KEY to Secrets.

api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)

if not api_key:
    st.error("Please set your OPENAI_API_KEY first.")
    st.stop()

client = OpenAI(api_key=api_key)

# -----------------------------
# System prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a linguistics research assistant chatbot.

Given user-provided keywords, topics, or research questions, generate a list of 10 relevant academic works in linguistics.

For each work, provide:
- Citation: Author(s), year, title
- Area: relevant subfield
- Relevance: one sentence explaining why the work is useful for the query
- Confidence: high / medium / low

Important:
- Do not fabricate references.
- If you are unsure about bibliographic details, mark confidence as low and say the details should be verified.
- If fewer than 10 reliable works come to mind, provide fewer than 10 and explain why.
- If the query is too broad, ask one clarifying question before listing works.
- Prefer foundational works plus a few more recent works when possible.
- Keep the response readable and concise.
"""

# -----------------------------
# Conversation memory
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

# Display previous messages, except system prompt
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    elif message["role"] == "assistant":
        with st.chat_message("assistant"):
            st.markdown(message["content"])

# -----------------------------
# Chat input
# -----------------------------
user_input = st.chat_input("Enter keywords or a linguistics research topic...")

if user_input:
    # Add user message to memory
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    # Build the input for the model
    conversation_text = ""
    for msg in st.session_state.messages:
        role = msg["role"]
        content = msg["content"]
        conversation_text += f"{role.upper()}: {content}\n\n"

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = client.responses.create(
                model="gpt-5.5-mini",
                input=conversation_text
            )

            assistant_reply = response.output_text
            st.markdown(assistant_reply)

    # Save assistant response
    st.session_state.messages.append(
        {"role": "assistant", "content": assistant_reply}
    )

# -----------------------------
# Reset button
# -----------------------------
if st.button("Reset conversation"):
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    st.rerun()
