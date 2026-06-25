import re
from urllib.parse import quote_plus

import requests
import streamlit as st


# -----------------------------
# Page setup
# -----------------------------

st.set_page_config(
    page_title="What Have Others Found Before Me?",
    page_icon="📚",
    layout="wide"
)

st.title("What Have Others Found Before Me?")
st.caption(
    "A literature-discovery tool for finding close matches, nearby work, "
    "and possible research gaps."
)


# -----------------------------
# Query settings
# -----------------------------

BROAD_SINGLE_TERMS = {
    "syntax", "semantics", "phonology", "morphology", "pragmatics",
    "linguistics", "language", "grammar", "discourse", "meaning",
    "words", "sentences", "speech", "communication", "acquisition",
    "variation", "typology"
}

STOPWORDS = {
    "the", "and", "or", "of", "in", "on", "for", "to", "a", "an",
    "with", "by", "from", "about", "into", "across", "under", "over",
    "between", "among", "through", "at", "as", "is", "are", "was",
    "were", "be", "been", "being", "this", "that", "these", "those"
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


def normalize_text(text):
    """Lowercase and normalize spacing."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_query_units(query):
    """
    Extract meaningful search units from the query.

    Quoted phrases are kept as phrases:
    "under negation" -> under negation

    Remaining unquoted words are tokenized, with stopwords removed.

    Example:
    Turkish ideophones "under negation"

    becomes:
    ["under negation", "turkish", "ideophones"]

    The word "under" does not count separately as a keyword.
    """
    query = normalize_text(query)

    quoted_phrases = re.findall(r'"([^"]+)"', query)

    cleaned_phrases = []
    for phrase in quoted_phrases:
        phrase = normalize_text(phrase)
        if phrase:
            cleaned_phrases.append(phrase)

    query_without_phrases = re.sub(r'"[^"]+"', " ", query)
    words = re.findall(r"\b\w+\b", query_without_phrases)

    keywords = [
        word for word in words
        if len(word) > 2 and word not in STOPWORDS
    ]

    units = cleaned_phrases + keywords

    unique_units = []
    for unit in units:
        if unit not in unique_units:
            unique_units.append(unit)

    return unique_units


def is_query_too_broad(query):
    """
    Reject broad one-word queries like 'syntax',
    but allow more specific one-word queries like 'clitics'.
    """
    units = extract_query_units(query)

    if len(units) == 1 and units[0] in BROAD_SINGLE_TERMS:
        return True

    return False


def get_work_text_fields(work):
    """Return normalized title, abstract, and OpenAlex concept text."""
    title = normalize_text(work.get("title") or "")

    abstract = normalize_text(
        reconstruct_abstract(work.get("abstract_inverted_index"))
    )

    concepts = work.get("concepts") or []
    concept_text = " ".join(
        concept.get("display_name", "") for concept in concepts
    )
    concept_text = normalize_text(concept_text)

    return title, abstract, concept_text


def count_unit_matches(text, query_units):
    """Count how many query units appear in a text field."""
    count = 0

    for unit in query_units:
        if unit in text:
            count += 1

    return count


def get_matched_units(text, query_units):
    """Return the query units that appear in a text field."""
    return [unit for unit in query_units if unit in text]


def minimum_required_abstract_matches(query_units):
    """
    For a niche one-word query like 'clitics', require one abstract match.
    For multi-unit queries, require at least two abstract matches.
    """
    if len(query_units) == 1:
        return 1

    return 2


def is_golden_catch(work, query_units):
    """
    A Golden Catch is a strong match.

    The abstract must include all meaningful query units.

    Example query:
    Turkish ideophones "under negation"

    A Golden Catch should include:
    - Turkish
    - ideophones
    - under negation

    in the abstract.
    """
    _, abstract, _ = get_work_text_fields(work)

    if not abstract:
        return False

    abstract_matches = count_unit_matches(abstract, query_units)

    return abstract_matches == len(query_units)


def is_nearby_find(work, query_units):
    """
    A Nearby Find is related, but not a perfect match.

    The abstract must include:
    - one match for one-unit niche queries
    - at least two matches for multi-unit queries
    """
    _, abstract, _ = get_work_text_fields(work)

    if not abstract:
        return False

    required_matches = minimum_required_abstract_matches(query_units)
    abstract_matches = count_unit_matches(abstract, query_units)

    return abstract_matches >= required_matches


def relevance_score(work, query_units):
    """
    Score how central the user's keywords or phrases are to the work.

    Title matches matter most.
    Abstract matches matter next.
    OpenAlex concept matches also help.
    Citation count is only a small bonus.
    """
    title, abstract, concept_text = get_work_text_fields(work)

    score = 0

    for unit in query_units:
        if unit in title:
            score += 5
        if unit in abstract:
            score += 3
        if unit in concept_text:
            score += 2

    title_matches = count_unit_matches(title, query_units)
    abstract_matches = count_unit_matches(abstract, query_units)
    concept_matches = count_unit_matches(concept_text, query_units)

    if title_matches >= 2:
        score += 5

    if abstract_matches >= 2:
        score += 5

    if abstract_matches == len(query_units):
        score += 10

    if concept_matches >= 2:
        score += 3

    cited_by = work.get("cited_by_count", 0) or 0
    score += min(cited_by / 100, 3)

    return score


def search_openalex(query):
    """
    Search OpenAlex and classify works into:
    - Golden Catch
    - Nearby Finds

    If no Golden Catch is found, the app suggests that this may be
    a research gap or that different terminology may be needed.
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

    golden_catches = []
    nearby_finds = []

    for work in works:
        score = relevance_score(work, query_units)
        work["custom_relevance_score"] = score

        title, abstract, concept_text = get_work_text_fields(work)

        work["matched_in_abstract"] = get_matched_units(abstract, query_units)
        work["matched_in_title"] = get_matched_units(title, query_units)
        work["matched_in_concepts"] = get_matched_units(concept_text, query_units)

        if is_golden_catch(work, query_units):
            golden_catches.append(work)
        elif is_nearby_find(work, query_units):
            nearby_finds.append(work)

    golden_catches = sorted(
        golden_catches,
        key=lambda work: work["custom_relevance_score"],
        reverse=True
    )

    nearby_finds = sorted(
        nearby_finds,
        key=lambda work: work["custom_relevance_score"],
        reverse=True
    )

    return golden_catches[:10], nearby_finds[:10]


def google_scholar_search_url(query):
    """Create a Google Scholar search link for the user's query."""
    return f"https://scholar.google.com/scholar?q={quote_plus(query)}"


def simplified_lingbuzz_query(query):
    """
    Create a shorter LingBuzz query using content words only.

    LingBuzz can return noisy results with long phrase-like searches,
    so this keeps only the first few content words.
    """
    units = extract_query_units(query)

    content_words = []

    for unit in units:
        words = re.findall(r"\b\w+\b", unit.lower())

        for word in words:
            if word not in STOPWORDS and len(word) > 2:
                content_words.append(word)

    unique_words = []

    for word in content_words:
        if word not in unique_words:
            unique_words.append(word)

    return " ".join(unique_words[:3])


def lingbuzz_search_url(query):
    """Create a simplified LingBuzz search link."""
    simple_query = simplified_lingbuzz_query(query)
    return f"https://lingbuzz.net/lingbuzz/search?q={quote_plus(simple_query)}"


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


def display_work(work, index):
    """Display one OpenAlex work."""
    title = work.get("title") or "Untitled"
    year = work.get("publication_year") or "n.d."
    cited_by = work.get("cited_by_count", 0)
    score = work.get("custom_relevance_score", 0)
    author_text = get_author_text(work)
    link = get_work_link(work)
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    matched_in_abstract = work.get("matched_in_abstract", [])
    matched_in_title = work.get("matched_in_title", [])
    matched_in_concepts = work.get("matched_in_concepts", [])

    with st.container():
        st.markdown(f"#### {index}. {title}")
        st.markdown(f"**Authors:** {author_text}")
        st.markdown(
            f"**Year:** {year} | **Cited by:** {cited_by} | "
            f"**Relevance score:** {score:.2f}"
        )

        if matched_in_abstract:
            st.markdown(
                "**Matched in abstract:** "
                + ", ".join(f"`{unit}`" for unit in matched_in_abstract)
            )

        if matched_in_title:
            st.markdown(
                "**Matched in title:** "
                + ", ".join(f"`{unit}`" for unit in matched_in_title)
            )

        if matched_in_concepts:
            st.markdown(
                "**Matched in OpenAlex concepts:** "
                + ", ".join(f"`{unit}`" for unit in matched_in_concepts)
            )

        if link:
            st.markdown(f"[Open work]({link})")

        if abstract:
            with st.expander("Abstract"):
                st.write(abstract)

        st.divider()


# -----------------------------
# User input
# -----------------------------

query = st.text_input(
    "What are you trying to find?",
    placeholder='e.g. Turkish ideophones "under negation"'
)

st.caption(
    'Tip: Put phrases in quotation marks, for example: '
    '`Turkish ideophones "under negation"`'
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
    # Search summary
    # -----------------------------

    st.markdown("### Search units")
    st.write(
        "The app will look for these meaningful keywords or phrases. "
        "Stopwords like `under` do not count separately."
    )
    st.code(", ".join(query_units))

    st.markdown("---")

    # -----------------------------
    # External source cards
    # -----------------------------

    st.markdown("### Continue the search elsewhere")

    simple_lingbuzz = simplified_lingbuzz_query(query)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 150px;
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

    with col2:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 150px;
            ">
                <h4>LingBuzz</h4>
                <p>Manual follow-up search using a simplified query:</p>
                <p><code>{simple_lingbuzz}</code></p>
                <a href="{lingbuzz_search_url(query)}" target="_blank">
                    Search LingBuzz
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # -----------------------------
    # OpenAlex search
    # -----------------------------

    with st.spinner("Searching OpenAlex..."):
        try:
            golden_catches, nearby_finds = search_openalex(query)
        except Exception as error:
            st.error(f"OpenAlex search failed: {error}")
            st.stop()

    # -----------------------------
    # Golden Catch results
    # -----------------------------

    if golden_catches:
        st.success(
            "Golden Catch! I found works whose abstracts include all of your "
            "meaningful keywords or phrases."
        )

        st.markdown("### 🎣 Golden Catch")

        for index, work in enumerate(golden_catches, start=1):
            display_work(work, index)

    else:
        st.warning(
            "Hmm... I did not find a Golden Catch. This could be a research gap, "
            "or the relevant work may use different terminology."
        )

    # -----------------------------
    # Nearby Finds results
    # -----------------------------

    if nearby_finds:
        st.info(
            "Nearby Finds: these works are related, but they may not include "
            "all of your key concepts in the abstract."
        )

        st.markdown("### Nearby Finds")

        for index, work in enumerate(nearby_finds, start=1):
            display_work(work, index)

    elif not golden_catches:
        st.error(
            "I did not find close or nearby matches in OpenAlex. Try broader terms, "
            "singular/plural variants, or different terminology."
        )
