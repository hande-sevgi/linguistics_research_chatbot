import requests
import re
import streamlit as st

st.set_page_config(
    page_title="Linguistics Research Assistant",
    page_icon="📚",
    layout="centered"
)

from urllib.parse import quote_plus

def lingbuzz_search_url(query):
    return f"https://lingbuzz.net/lingbuzz/search?q={quote_plus(query)}"
    
st.title("Linguistics Research Assistant")
st.caption("Search open scholarly metadata from OpenAlex for linguistics-related works.")
st.markdown("### Additional sources")
st.markdown(f"[Search LingBuzz for this topic]({lingbuzz_search_url(query)})")

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words_sorted = sorted(words, key=lambda x: x[0])
    return " ".join(word for _, word in words_sorted)

def search_openalex(query, max_results=10):
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
    return data.get("results", [])

import requests
import re

def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words_sorted = sorted(words, key=lambda x: x[0])
    return " ".join(word for _, word in words_sorted)


def tokenize_query(query):
    """
    Split the user's query into searchable terms.
    Removes very short/common words.
    """
    stopwords = {
        "the", "and", "or", "of", "in", "on", "for", "to", "a", "an",
        "with", "by", "from", "about"
    }

    terms = re.findall(r"\b\w+\b", query.lower())
    terms = [t for t in terms if len(t) > 2 and t not in stopwords]

    return terms


def relevance_score(work, query_terms):
    """
    Score how central the user's keywords are to the work.
    Title matches matter most.
    Abstract matches matter next.
    Concept matches also help.
    Citations are only a small bonus.
    """
    title = (work.get("title") or "").lower()
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")).lower()

    concepts = work.get("concepts") or []
    concept_text = " ".join(
        concept.get("display_name", "") for concept in concepts
    ).lower()

    score = 0

    for term in query_terms:
        if term in title:
            score += 5
        if term in abstract:
            score += 2
        if term in concept_text:
            score += 2

    # Bonus if multiple query terms appear in the title
    title_matches = sum(1 for term in query_terms if term in title)
    if title_matches >= 2:
        score += 5

    # Small citation bonus, capped so famous but irrelevant papers do not dominate
    cited_by = work.get("cited_by_count", 0) or 0
    score += min(cited_by / 100, 3)

    return score


def search_openalex_relevant(query, max_results=10):
    """
    Search broadly in OpenAlex, then rerank by thematic relevance.
    """
    url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "per-page": 50,
        "sort": "relevance_score:desc",
        "mailto": "handesevgi@g.harvard.edu"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    works = data.get("results", [])

    query_terms = tokenize_query(query)

    scored_works = []
    for work in works:
        score = relevance_score(work, query_terms)
        work["custom_relevance_score"] = score
        scored_works.append(work)

    # Keep only works with meaningful keyword overlap
    scored_works = [
        work for work in scored_works
        if work["custom_relevance_score"] > 0
    ]

    scored_works = sorted(
        scored_works,
        key=lambda w: w["custom_relevance_score"],
        reverse=True
    )

    return scored_works[:max_results]
    
query = st.text_input("Enter keywords, e.g. Turkish ideophones under negation")

if st.button("Search") and query:
    with st.spinner("Searching OpenAlex..."):
        try:
            works = search_openalex(query, max_results=10)
        except Exception as e:
            st.error(f"OpenAlex search failed: {e}")
            st.stop()

    if not works:
        st.warning("No results found. Try different keywords.")
        st.stop()

    st.subheader(f"Top results for: {query}")

    for i, work in enumerate(works, start=1):
        title = work.get("title") or "Untitled"
        year = work.get("publication_year") or "n.d."
        cited_by = work.get("cited_by_count", 0)
        doi = work.get("doi")
        openalex_url = work.get("id")

        authorships = work.get("authorships", [])
        authors = []
        for authorship in authorships[:4]:
            author = authorship.get("author", {})
            name = author.get("display_name")
            if name:
                authors.append(name)

        if len(authorships) > 4:
            authors.append("et al.")

        author_text = ", ".join(authors) if authors else "Unknown authors"

        primary_location = work.get("primary_location") or {}
        landing_page_url = primary_location.get("landing_page_url")

        link = doi or landing_page_url or openalex_url

        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

        with st.container():
            st.markdown(f"### {i}. {title}")
            st.markdown(f"**Authors:** {author_text}")
            st.markdown(f"**Year:** {year} | **Cited by:** {cited_by}")

            if link:
                st.markdown(f"[Open work]({link})")

            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract)

            st.divider()
