import re
from urllib.parse import quote_plus

import requests
import streamlit as st

from linguistics_terms import (
    BROAD_SINGLE_TERMS,
    STOPWORDS,
    SPECIALIZED_LINGUISTIC_TERMS,
    KNOWN_COLLOCATIONS,
    TERM_VARIANTS,
    LINGUISTIC_DOMAIN_TERMS,
)


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
# Text helpers
# -----------------------------

def normalize_text(text):
    """Lowercase and normalize spacing."""
    if not text:
        return ""

    text = str(text).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


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

    This function handles:
    - quoted phrases
    - known linguistic collocations
    - ordinary keywords
    - stopwords

    Example:
    Turkish bare nouns under negation

    becomes:
    ["bare nouns", "turkish", "negation"]

    not:
    ["turkish", "bare", "nouns", "negation"]
    """
    query = normalize_text(query)

    units = []

    # 1. Extract quoted phrases first.
    quoted_phrases = re.findall(r'"([^"]+)"', query)

    for phrase in quoted_phrases:
        phrase = normalize_text(phrase)
        if phrase:
            units.append(phrase)

    # Remove quoted phrases before further processing.
    query_without_phrases = re.sub(r'"[^"]+"', " ", query)

    # 2. Extract known linguistic collocations.
    # Longer collocations first, so "negative polarity items"
    # is captured before "polarity items".
    sorted_collocations = sorted(
        KNOWN_COLLOCATIONS,
        key=len,
        reverse=True
    )

    for collocation in sorted_collocations:
        collocation = normalize_text(collocation)
        pattern = r"\b" + re.escape(collocation) + r"\b"

        if re.search(pattern, query_without_phrases):
            units.append(collocation)
            query_without_phrases = re.sub(
                pattern,
                " ",
                query_without_phrases
            )

    # 3. Tokenize whatever remains.
    words = re.findall(r"\b\w+\b", query_without_phrases)

    keywords = [
        word for word in words
        if len(word) > 2 and word not in STOPWORDS
    ]

    units.extend(keywords)

    # 4. Remove duplicates while preserving order.
    unique_units = []

    for unit in units:
        if unit not in unique_units:
            unique_units.append(unit)

    return unique_units


def get_unit_variants(unit):
    """
    Return simple variants for a query unit.

    This helps match:
    pragmatics / pragmatic
    semantics / semantic
    ideophones / ideophone / ideophonic
    clitics / clitic
    negation / negative / negated

    This is intentionally simple, not a full linguistic stemmer.
    """
    unit = normalize_text(unit)
    variants = {unit}

    # Add hand-coded variants from linguistics_terms.py.
    if unit in TERM_VARIANTS:
        variants.update(TERM_VARIANTS[unit])

    # Do not aggressively alter multi-word phrases.
    # But still allow variation on the final word.
    if " " in unit:
        words = unit.split()
        last_word = words[-1]
        last_variants = get_unit_variants(last_word)

        for variant in last_variants:
            phrase_variant = " ".join(words[:-1] + [variant])
            variants.add(phrase_variant)

        return variants

    # Basic singular/plural matching.
    if unit.endswith("s") and len(unit) > 4:
        variants.add(unit[:-1])

    if not unit.endswith("s") and len(unit) > 3:
        variants.add(unit + "s")

    # Field noun/adjective pairs.
    # pragmatics -> pragmatic
    # semantics -> semantic
    # phonetics -> phonetic
    if unit.endswith("ics") and len(unit) > 5:
        variants.add(unit[:-1])

    # pragmatic -> pragmatics
    # semantic -> semantics
    # phonetic -> phonetics
    if unit.endswith("ic") and len(unit) > 4:
        variants.add(unit + "s")

    # morphology -> morphological
    # phonology -> phonological
    # typology -> typological
    if unit.endswith("ology") and len(unit) > 6:
        variants.add(unit[:-1] + "ical")

    return variants


def is_query_too_broad(query):
    """
    Reject broad one-word queries like 'syntax',
    but allow more specific one-word queries like 'clitics' or 'ideophones'.
    """
    units = extract_query_units(query)

    if len(units) == 1 and units[0] in BROAD_SINGLE_TERMS:
        return True

    return False


# -----------------------------
# OpenAlex work helpers
# -----------------------------

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


def contains_any_term(text, terms):
    """Return True if any term from a set appears in text."""
    text = normalize_text(text)

    for term in terms:
        term = normalize_text(term)
        if term and term in text:
            return True

    return False

def is_linguistics_related(work, query_units):
    """
    Barrier 1: decide whether the work belongs to linguistics.

    This is the first and most important constraint.

    Only after passing this barrier can a work become a Golden Catch
    or Nearby Find.
    """
    title, abstract, concept_text = get_work_text_fields(work)
    combined_text = f"{title} {abstract} {concept_text}"

    # Barrier 1: require a positive linguistics signal.
    linguistic_signal_terms = build_linguistic_signal_terms()

    has_linguistic_signal = contains_any_term(
        combined_text,
        linguistic_signal_terms
    )

    if not has_linguistic_signal:
        return False

    return True

def build_linguistic_signal_terms():
    """
    Build a broad set of positive linguistics signals.

    This includes:
    - general domain terms
    - specialized one-word terms
    - known multi-word collocations
    """
    signal_terms = set()

    signal_terms.update(LINGUISTIC_DOMAIN_TERMS)
    signal_terms.update(SPECIALIZED_LINGUISTIC_TERMS)
    signal_terms.update(KNOWN_COLLOCATIONS)

    return signal_terms

def unit_matches_text(unit, text):
    """Return True if a query unit or one of its variants appears in text."""
    text = normalize_text(text)
    variants = get_unit_variants(unit)

    for variant in variants:
        variant = normalize_text(variant)
        if variant and variant in text:
            return True

    return False


def count_unit_matches(text, query_units):
    """Count how many query units or their variants appear in a text field."""
    count = 0

    for unit in query_units:
        if unit_matches_text(unit, text):
            count += 1

    return count


def get_matched_units(text, query_units):
    """Return the query units that appear in a text field, allowing variants."""
    matched = []

    for unit in query_units:
        if unit_matches_text(unit, text):
            matched.append(unit)

    return matched


def minimum_required_nearby_matches(query_units):
    """
    Nearby Finds require meaningful overlap.

    For a niche one-word query like 'clitics' or 'pragmatics',
    one abstract match is enough.

    For multi-unit queries, at least two abstract matches are required.
    """
    if len(query_units) == 1:
        return 1

    return 2


def is_golden_catch(work, query_units):
    """
    A Golden Catch is a direct match.

    The abstract must include all meaningful query units, allowing simple variants.

    Example:
    Query: Turkish ideophones under negation
    Query units: turkish, ideophones, negation

    Golden Catch:
    The abstract includes Turkish, ideophone/ideophones, and negation/negative.
    """
    _, abstract, _ = get_work_text_fields(work)

    if not abstract:
        return False

    abstract_matches = count_unit_matches(abstract, query_units)

    return abstract_matches == len(query_units)


def is_nearby_find(work, query_units):
    """
    A Nearby Find is related, but not a full direct match.

    The abstract must include some meaningful overlap:
    - one match for one-unit niche queries
    - at least two matches for multi-unit queries

    Golden Catches are excluded from Nearby Finds.
    """
    if is_golden_catch(work, query_units):
        return False

    _, abstract, _ = get_work_text_fields(work)

    if not abstract:
        return False

    required_matches = minimum_required_nearby_matches(query_units)
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
        if unit_matches_text(unit, title):
            score += 5
        if unit_matches_text(unit, abstract):
            score += 3
        if unit_matches_text(unit, concept_text):
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

    Step-by-step constraints:
    1. First narrow the OpenAlex search to linguistics.
    2. Then remove anything that still does not look linguistic.
    3. Then check abstract matches.
    4. Classify as Golden Catch or Nearby Find.
    """
    url = "https://api.openalex.org/works"

    # Add linguistics directly to the query so OpenAlex starts in the right domain.
    linguistics_query = f"{query} linguistics"

    params = {
        "search": linguistics_query,
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
        # Hidden barrier: only linguistics works can pass.
        if not is_linguistics_related(work, query_units):
            continue

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
        key=lambda item: item["custom_relevance_score"],
        reverse=True
    )

    nearby_finds = sorted(
        nearby_finds,
        key=lambda item: item["custom_relevance_score"],
        reverse=True
    )

    return golden_catches[:10], nearby_finds[:10]

# -----------------------------
# External source helpers
# -----------------------------

def google_scholar_search_url(query):
    """
    Create a more constrained Google Scholar search link.

    This does not filter Google Scholar results inside the app.
    It only sends Google Scholar a smarter query by:
    - preserving known collocations as quoted phrases
    - adding a linguistics-domain cue
    - excluding common non-linguistic domains such as biology and medicine
    """
    units = extract_query_units(query)

    scholar_terms = []

    for unit in units:
        if " " in unit:
            scholar_terms.append(f'"{unit}"')
        else:
            scholar_terms.append(unit)

    # Add a domain cue so Scholar knows this is about linguistics.
    scholar_terms.append("linguistics")

    # These are query-level exclusions.
    # They help reduce biology/medicine false positives like stem-cell morphology.
    exclusions = [
        "-biology",
        "-medicine",
        "-clinical",
        "-biomedical",
        '-"stem cell"',
        '-"stem cells"',
        "-spermatogonial",
        "-protein",
        "-gene",
        "-genes",
        "-genetic",
        "-cancer",
        "-tumor",
        "-tumour",
        "-neuron",
        "-neurons",
        "-cellular",
        '-"cell proliferation"',
        '-"cell differentiation"',
    ]

    scholar_query = " ".join(scholar_terms + exclusions)

    return f"https://scholar.google.com/scholar?q={quote_plus(scholar_query)}"


def simplified_lingbuzz_query(query):
    """
    Create a shorter LingBuzz query using linguistic search units.

    LingBuzz can be noisy with long searches, so this:
    - preserves known collocations as phrases
    - removes stopwords through extract_query_units()
    - keeps only the first few units
    """
    units = extract_query_units(query)

    lingbuzz_terms = []

    for unit in units:
        if " " in unit:
            lingbuzz_terms.append(f'"{unit}"')
        else:
            lingbuzz_terms.append(unit)

    # Keep only the first 4 units so the search does not become too brittle.
    return " ".join(lingbuzz_terms[:4])


def lingbuzz_search_url(query):
    """
    Create a simplified LingBuzz search link.

    LingBuzz results are external and are not filtered inside the app.
    """
    simple_query = simplified_lingbuzz_query(query)
    return f"https://lingbuzz.net/lingbuzz/search?q={quote_plus(simple_query)}"
# -----------------------------
# Display helpers
# -----------------------------

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

with st.form("search_form"):
    query = st.text_input(
        "What are you curious about?",
        placeholder="e.g. Turkish ideophones under negation"
    )

    st.caption(
        "You can type natural research phrases. "
    )

    submitted = st.form_submit_button("Search")


# -----------------------------
# Main search
# -----------------------------

if submitted and query:
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

    with st.spinner("Searching OpenAlex and removing non-linguistics results..."):
        try:
            golden_catches, nearby_finds = search_openalex(query)
        except Exception as error:
            st.error(f"OpenAlex search failed: {error}")
            st.stop()

    # -----------------------------
    # Results logic
    # -----------------------------

    if golden_catches:
        st.success(
            "Golden Catch! I found linguistics works whose abstracts include "
            "all of your meaningful keywords or phrases."
        )

        st.markdown("### 🎣 Golden Catch")

        for index, work in enumerate(golden_catches, start=1):
            display_work(work, index)

    if nearby_finds:
        if golden_catches:
            st.info(
                "I also found Nearby Finds. These are linguistics works that are "
                "related, but they may not include all of your key concepts in "
                "the abstract."
            )
        else:
            st.info(
                "I did not find a Golden Catch, but I found Nearby Finds. "
                "These are linguistics works that are related, though they may "
                "not directly combine all of your key concepts."
            )

        st.markdown("### Nearby Finds")

        for index, work in enumerate(nearby_finds, start=1):
            display_work(work, index)

    if not golden_catches and not nearby_finds:
        st.warning(
            "Hmm... I did not find matching linguistics works in OpenAlex. "
            "This could be a research gap, or the relevant work may use "
            "different terminology."
        )
