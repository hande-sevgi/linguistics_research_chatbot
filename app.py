import os
import streamlit as st
from openai import OpenAI

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="AI Advising Chatbot",
    page_icon="💬",
    layout="centered"
)

st.title("AI Advising Chatbot")
st.caption("A small LLM-powered chatbot built with Streamlit and the OpenAI API.")

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
You are an advising-support chatbot.

Your job is to help users think through advising-related questions clearly and supportively.
You can help with:
- course selection
- deadlines
- research opportunities
- advising appointments
- general academic planning

Important rules:
- Do not invent specific university policies.
- If the user asks about a policy, deadline, requirement, or sensitive issue, recommend checking with the relevant office or advisor.
- Ask clarifying questions when the user's request is ambiguous.
- Keep responses concise, warm, and useful.
- Give concrete next steps when possible.
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
user_input = st.chat_input("Ask me an advising question...")

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
