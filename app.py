import re
from urllib.parse import quote_plus

import requests
import streamlit as st


# -----------------------------
# Page setup
# -----------------------------

st.set_page_config(
    page_title="Linguistics Research Assistant",
    page_icon="📚",
    layout="wide"
)

st.title("Linguistics Research Assistant")
st.caption(
    "Search open scholarly metadata from OpenAlex and continue the same search "
    "in LingBuzz and Google Scholar."
)


# -----------------------------
# Helper functions
# -----------------------------

def reconstruct_abstract(inverted_index):
    """Reconstruct OpenAlex abstracts from inverted-index format."""
    if not inverted_index:
        return ""

    words = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words.append((pos, word))

    words_sorted = sorted(words, key=lambda x: x[0])
    return " ".join(word for _, word in words_sorted)


def tokenize_query(query):
    """Split the user's query into meaningful searchable terms."""
    stopwords = {
        "the", "and", "or", "of", "in", "on", "for", "to", "a", "an",
        "with", "by", "from", "about", "into", "across", "under"
    }

    terms = re.findall(r"\b\w+\b", query.lower())
    terms = [term for term in terms if len(term) > 2 and term not in stopwords]

    return terms


def contains_all_keywords(work, query_terms):
    """
    Return True only if every query term appears in the title,
    abstract, or OpenAlex concept metadata.
    """
    title = (work.get("title") or "").lower()
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")).lower()

    concepts = work.get("concepts") or []
    concept_text = " ".join(
        concept.get("display_name", "") for concept in concepts
    ).lower()

    searchable_text = f"{title} {abstract} {concept_text}"

    return all(term in searchable_text for term in query_terms)


def relevance_score(work, query_terms):
    """
    Score how central the user's keywords are to the work.

    Title matches matter most.
    Abstract matches matter next.
    OpenAlex concept matches also help.
    Citation count is only a small bonus.
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

    title_matches = sum(1 for term in query_terms if term in title)
    if title_matches >= 2:
        score += 5

    cited_by = work.get("cited_by_count", 0) or 0
    score += min(cited_by / 100, 3)

    return score


def search_openalex_relevant(query, max_results=10):
    """
    Search OpenAlex, keep only works containing all keywords,
    then rerank by custom relevance score.
    """
    url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "per-page": 100,
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
        if contains_all_keywords(work, query_terms):
            score = relevance_score(work, query_terms)
            work["custom_relevance_score"] = score
            scored_works.append(work)

    scored_works = sorted(
        scored_works,
        key=lambda work: work["custom_relevance_score"],
        reverse=True
    )

    return scored_works[:max_results]


def lingbuzz_search_url(query):
    """Create a LingBuzz search link for the user's query."""
    return f"https://lingbuzz.net/lingbuzz/search?q={quote_plus(query)}"


def google_scholar_search_url(query):
    """Create a Google Scholar search link for the user's query."""
    return f"https://scholar.google.com/scholar?q={quote_plus(query)}"


def get_author_text(work, max_authors=4):
    """Return a readable author string from OpenAlex authorships."""
    authorships = work.get("authorships", [])
    authors = []

    for authorship in authorships[:max_authors]:
        author = authorship.get("author", {})
        name = author.get("display_name")
        if name:
            authors.append(name)

    if len(authorships) > max_authors:
        authors.append("et al.")

    return ", ".join(authors) if authors else "Unknown authors"


def get_work_link(work):
    """Return the best available link for an OpenAlex work."""
    doi = work.get("doi")
    openalex_url = work.get("id")

    primary_location = work.get("primary_location") or {}
    landing_page_url = primary_location.get("landing_page_url")

    return doi or landing_page_url or openalex_url


# -----------------------------
# User input
# -----------------------------

query = st.text_input(
    "Enter keywords or a research topic",
    placeholder="e.g. Turkish ideophones negation"
)

max_results = st.slider(
    "Number of OpenAlex results",
    min_value=5,
    max_value=20,
    value=10
)


# -----------------------------
# Main search
# -----------------------------

if st.button("Search") and query:
    query_terms = tokenize_query(query)

    if not query_terms:
        st.warning("Please enter more specific keywords.")
        st.stop()

    st.markdown("## Results")

    # -----------------------------
    # Source cards
    # -----------------------------

    st.markdown("### Search across sources")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 145px;
            ">
                <h4>OpenAlex</h4>
                <p>Ranked results are shown below.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 145px;
            ">
                <h4>LingBuzz</h4>
                <p>Linguistics preprints and working papers.</p>
                <a href="{lingbuzz_search_url(query)}" target="_blank">
                    Search LingBuzz
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 145px;
            ">
                <h4>Google Scholar</h4>
                <p>Broader scholarly search across books, articles, and citations.</p>
                <a href="{google_scholar_search_url(query)}" target="_blank">
                    Search Google Scholar
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # -----------------------------
    # Keyword constraint
    # -----------------------------

    st.markdown("### Keyword constraint")
    st.write(
        "OpenAlex results below include all of these keywords in the title, "
        "abstract, or OpenAlex concepts:"
    )
    st.code(", ".join(query_terms))

    # -----------------------------
    # OpenAlex results
    # -----------------------------

    with st.spinner("Searching OpenAlex..."):
        try:
            works = search_openalex_relevant(query, max_results=max_results)
        except Exception as error:
            st.error(f"OpenAlex search failed: {error}")
            st.stop()

    if not works:
        st.warning(
            "No OpenAlex works found that include all keywords. Try fewer keywords, "
            "broader terms, or singular/plural variants. You can still use the LingBuzz "
            "and Google Scholar links above."
        )
        st.stop()

    st.markdown("### OpenAlex ranked results")

    for index, work in enumerate(works, start=1):
        title = work.get("title") or "Untitled"
        year = work.get("publication_year") or "n.d."
        cited_by = work.get("cited_by_count", 0)
        score = work.get("custom_relevance_score", 0)
        author_text = get_author_text(work)
        link = get_work_link(work)
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

        with st.container():
            st.markdown(f"#### {index}. {title}")
            st.markdown(f"**Authors:** {author_text}")
            st.markdown(
                f"**Year:** {year} | **Cited by:** {cited_by} | "
                f"**Relevance score:** {score:.2f}"
            )

            if link:
                st.markdown(f"[Open work]({link})")

            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract)

            st.divider()
