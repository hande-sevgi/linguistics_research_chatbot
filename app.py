import os
import requests
import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="Linguistics Research Assistant",
    page_icon="📚",
    layout="centered"
)

st.title("Linguistics Research Assistant")
st.caption("Enter keywords or a research topic to find relevant open scholarly works.")

api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)

if not api_key:
    st.error("Please set your OPENAI_API_KEY first.")
    st.stop()

client = OpenAI(api_key=api_key)


def search_openalex(query, max_results=25):
    """
    Search OpenAlex works endpoint for papers matching a query.
    Returns simplified metadata for ranking/summarization.
    """
    url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "per-page": max_results,
        "sort": "cited_by_count:desc",
        "mailto": "handesevgi@g.harvard.edu"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    works = data.get("results", [])

    simplified = []

    for work in works:
        title = work.get("title") or "Untitled"

        year = work.get("publication_year")
        cited_by = work.get("cited_by_count", 0)

        authorships = work.get("authorships", [])
        authors = []
        for authorship in authorships[:4]:
            author = authorship.get("author", {})
            name = author.get("display_name")
            if name:
                authors.append(name)

        if len(authorships) > 4:
            authors.append("et al.")

        doi = work.get("doi")
        openalex_url = work.get("id")
        primary_location = work.get("primary_location") or {}
        landing_page_url = primary_location.get("landing_page_url")

        abstract_inverted = work.get("abstract_inverted_index")
        abstract = reconstruct_abstract(abstract_inverted)

        simplified.append({
            "title": title,
            "year": year,
            "authors": ", ".join(authors) if authors else "Unknown authors",
            "cited_by_count": cited_by,
            "doi": doi,
            "url": doi or landing_page_url or openalex_url,
            "abstract": abstract
        })

    return simplified


def reconstruct_abstract(inverted_index):
    """
    OpenAlex stores abstracts as an inverted index.
    This reconstructs the abstract into readable text.
    """
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words_sorted = sorted(words, key=lambda x: x[0])
    return " ".join(word for _, word in words_sorted)


def format_works_for_llm(works):
    formatted = []

    for i, work in enumerate(works, start=1):
        formatted.append(
            f"""
Paper {i}
Title: {work['title']}
Authors: {work['authors']}
Year: {work['year']}
Citations: {work['cited_by_count']}
URL: {work['url']}
Abstract: {work['abstract'][:1200]}
"""
        )

    return "\n".join(formatted)


SYSTEM_PROMPT = """
You are a linguistics research assistant.

The user will give keywords, a topic, or a research question.
You will receive search results from OpenAlex.

Your task:
1. Select the 10 most relevant works from the search results.
2. Prioritize works that are relevant to linguistics, language, meaning, syntax, semantics, pragmatics, morphology, sign language, gesture, psycholinguistics, sociolinguistics, or NLP, depending on the user's query.
3. For each work, provide:
   - citation-style line: Author(s), year, title
   - one-sentence explanation of relevance
   - link if available
4. Do not invent works.
5. If the search results are weak, say that the list should be treated as a starting point.
6. Keep the response clear and concise.
"""


query = st.chat_input("Enter keywords, e.g. ideophones negation Turkish")

if query:
    st.markdown(f"**Search query:** {query}")

    with st.spinner("Searching OpenAlex..."):
        try:
            works = search_openalex(query, max_results=30)
        except Exception as e:
            st.error(f"OpenAlex search failed: {e}")
            st.stop()

    if not works:
        st.warning("No works found. Try different keywords.")
        st.stop()

    works_text = format_works_for_llm(works)

    user_prompt = f"""
User query: {query}

OpenAlex search results:
{works_text}

Please return the 10 most relevant works for this query.
"""

    with st.spinner("Ranking and summarizing works..."):
        response = client.responses.create(
            model="gpt-5.5-mini",
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
        )

    st.markdown(response.output_text)

    with st.expander("View raw OpenAlex results"):
        for work in works:
            st.write(work)
