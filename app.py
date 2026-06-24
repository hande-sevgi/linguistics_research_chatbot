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
# Query settings
# -----------------------------

BROAD_SINGLE_TERMS = {
    "syntax", "semantics", "phonology", "morphology", "pragmatics",
    "linguistics", "language", "grammar", "discourse", "meaning",
    "words", "sentences", "speech", "communication"
}

STOPWORDS = {
    "the", "and", "or", "of", "in", "on", "for", "to", "a", "an",
    "with", "by", "from", "about", "into", "across", "under", "over",
    "between", "among", "through", "at", "as", "is", "are"
}


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

    words_sorted = sorted(words, key=lambda item: item[0])
    return " ".join(word for _, word in words_sorted)


def extract_query_units(query):
    """
    Extract meaningful search units from the query.

    Quoted phrases are kept as phrases:
    "under negation" -> under negation

    Remaining unquoted words are tokenized, with stopwords removed.
    """
    query = query.strip().lower()

    quoted_phrases = re.findall(r'"([^"]+)"', query)

    query_without_phrases = re.sub(r'"[^"]+"', " ", query)
    words = re.findall(r"\b\w+\b", query_without_phrases)

    keywords = [
        word for word in words
        if len(word) > 2 and word not in STOPWORDS
    ]

    units = quoted_phrases + keywords

    return units


def is_query_too_broad(query):
    """
    Reject broad one-word queries like 'syntax',
    but allow more specific one-word queries like 'clitics'.
    """
    units = extract_query_units(query)

    if len(units) == 1 and units[0] in BROAD_SINGLE_TERMS:
        return True

    return False


def abstract_match_count(abstract, query_units):
    """
    Count how many query units appear in the abstract.

    Phrases count as one unit.
    Stopwords inside phrases are not counted separately.
    """
    abstract = abstract.lower()

    count = 0
    for unit in query_units:
        if unit in abstract:
            count += 1

    return count


def contains_required_keywords(work, query_units, min_abstract_matches=2):
    """
    Return True only if the abstract contains at least two query units.

    This keeps results focused on works where the user's topic is central,
    rather than merely mentioned in the title or metadata.
    """
    abstract = reconstruct_abstract(work.get("abstract_inverted_index")).lower()

    if not abstract:
        return False

    return abstract_match_count(abstract, query_units) >= min_abstract_matches


def relevance_score(work, query_units):
    """
    Score how central the user's keywords/phrases are to the work.

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

    for unit in query_units:
        if unit in title:
            score += 5
        if unit in abstract:
            score += 3
        if unit in concept_text:
            score += 2

    title_matches = sum(1 for unit in query_units if unit in title)
    abstract_matches = abstract_match_count(abstract, query_units)

    if title_matches >= 2:
        score += 5

    if abstract_matches >= 2:
        score += 5

    cited_by = work.get("cited_by_count", 0) or 0
    score += min(cited_by / 100, 3)

    return score


def search_openalex_relevant(query, max_results=10):
    """
    Search OpenAlex, keep only works whose abstracts contain at least
    two query units, then rerank by custom relevance score.
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

    query_units = extract_query_units(query)

    scored_works = []

    for work in works:
        if contains_required_keywords(work, query_units, min_abstract_matches=2):
            score = relevance_score(work, query_units)
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
    placeholder='e.g. Turkish ideophones "under negation"'
)


# -----------------------------
# Main search
# -----------------------------

if st.button("Search") and query:
    if is_query_too_broad(query):
        st.warning(
            "Please provide more specific information. For example, instead of "
            "'syntax', try 'clitics in syntax', 'word order in Turkish', or "
            "'syntax of negation'."
        )
        st.stop()

    query_units = extract_query_units(query)

    if not query_units:
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
                <p>Top 10 ranked results are shown below.</p>
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
        "OpenAlex results below are filtered so that the abstract includes at least "
        "two of these keyword units or phrases:"
    )
    st.code(", ".join(query_units))

    # -----------------------------
    # OpenAlex results
    # -----------------------------

    with st.spinner("Searching OpenAlex..."):
        try:
            works = search_openalex_relevant(query, max_results=10)
        except Exception as error:
            st.error(f"OpenAlex search failed: {error}")
            st.stop()

    if not works:
        st.warning(
            "No OpenAlex works found whose abstract includes at least two of the "
            "keyword units. Try fewer keywords, broader terms, singular/plural "
            "variants, or quotation marks for exact phrases. You can still use "
            "the LingBuzz and Google Scholar links above."
        )
        st.stop()

    st.markdown("### Top 10 OpenAlex ranked results")

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
