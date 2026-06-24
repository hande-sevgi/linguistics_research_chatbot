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
    "A literature-discovery tool for linguistics researchers. "
    "Search OpenAlex, then continue the search in Google Scholar or LingBuzz."
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
    "between", "among", "through", "at", "as", "is", "are", "when",
    "while", "within", "without", "during", "their", "its", "this",
    "that", "these", "those"
}

LINGUISTICS_SIGNAL_TERMS = {
    "linguistic", "linguistics", "language", "languages", "grammar",
    "syntax", "syntactic", "semantics", "semantic", "pragmatics",
    "pragmatic", "phonology", "phonological", "phonetics", "phonetic",
    "morphology", "morphological", "morphosyntax", "morphosyntactic",
    "discourse", "utterance", "word", "words", "sentence", "sentences",
    "clitic", "clitics", "negation", "adverb", "adverbial", "focus",
    "information structure", "sign language", "gesture", "modality",
    "typology", "bilingual", "multilingual", "corpus linguistics",
    "language acquisition", "language processing", "sociolinguistics",
    "psycholinguistics", "computational linguistics",
    "natural language processing", "translation", "anaphora",
    "agreement", "case marking", "tense", "aspect", "evidential",
    "evidentiality", "classifier", "noun phrase", "verb phrase",
    "relative clause", "ideophone", "ideophones"
}

EXCLUDED_NON_LINGUISTIC_TERMS = {
    "biology", "biological", "cell", "cells", "cellular", "molecular",
    "genetics", "genome", "protein", "proteins", "plant", "plants",
    "animal", "animals", "species", "evolution", "ecology", "medical",
    "medicine", "clinical", "anatomy", "physiology", "disease",
    "patient", "patients", "neuron", "neural", "brain", "cancer",
    "tumor", "bacteria", "microbial", "material", "materials",
    "crystal", "crystals", "polymer", "surface", "nanoparticle",
    "nanoparticles", "soil", "leaf", "leaves", "root", "roots",
    "stem", "stems", "organism", "organisms", "tissue", "tissues",
    "specimen", "specimens", "embryo", "embryonic"
}

LINGUISTIC_SUBFIELDS = {
    "Syntax": {
        "syntax", "syntactic", "sentence structure", "word order",
        "clause", "clausal", "movement", "agreement", "case", "binding",
        "argument structure", "island", "islands", "ellipsis"
    },
    "Semantics": {
        "semantics", "semantic", "meaning", "truth conditions",
        "compositionality", "quantification", "scope", "modality",
        "tense", "aspect", "event semantics", "plurality",
        "definiteness", "presupposition"
    },
    "Pragmatics": {
        "pragmatics", "pragmatic", "implicature", "presupposition",
        "context", "common ground", "speech act", "speech acts",
        "discourse", "information structure", "focus", "topic"
    },
    "Phonology": {
        "phonology", "phonological", "prosody", "stress", "tone",
        "intonation", "syllable", "segment", "feature", "features",
        "vowel harmony", "phonotactics"
    },
    "Phonetics": {
        "phonetics", "phonetic", "acoustic", "articulation",
        "articulatory", "vowel", "consonant", "formant",
        "voice onset time", "speech perception", "speech production"
    },
    "Morphology": {
        "morphology", "morphological", "morpheme", "morphemes",
        "affix", "suffix", "prefix", "inflection", "derivation",
        "word formation", "distributed morphology", "allomorphy"
    },
    "Sociolinguistics": {
        "sociolinguistics", "sociolinguistic", "variation",
        "dialect", "register", "style", "language contact",
        "code switching", "codeswitching", "identity", "community"
    },
    "Psycholinguistics": {
        "psycholinguistics", "psycholinguistic", "processing",
        "comprehension", "production", "reaction time",
        "eye tracking", "language acquisition", "sentence processing"
    },
    "Computational linguistics / NLP": {
        "computational linguistics", "natural language processing",
        "nlp", "language model", "language models", "corpus",
        "annotation", "parsing", "parser", "machine translation",
        "large language model", "large language models"
    },
    "Typology / Fieldwork": {
        "typology", "typological", "fieldwork", "elicitation",
        "cross-linguistic", "crosslinguistic", "language documentation",
        "endangered language", "endangered languages", "descriptive grammar"
    },
    "Sign language / Gesture": {
        "sign language", "sign languages", "gesture", "gestures",
        "modality", "visual modality", "manual", "nonmanual",
        "classifier", "classifiers", "iconicity", "signing"
    },
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


def term_variants(term):
    """
    Create simple singular/plural variants.

    This helps match ideophone/ideophones, clitic/clitics, etc.
    """
    variants = {term}

    if term.endswith("ies") and len(term) > 4:
        variants.add(term[:-3] + "y")

    if term.endswith("s") and len(term) > 4:
        variants.add(term[:-1])
    else:
        variants.add(term + "s")

    return variants


def get_query_tokens(query):
    """Return lowercase word tokens from the query."""
    return re.findall(r"\b\w+\b", query.lower())


def extract_content_terms(query):
    """
    Extract meaningful content terms from the query.

    Function words such as 'under' are removed, so:
    Turkish ideophones under negation
    becomes:
    Turkish, ideophones, negation
    """
    tokens = get_query_tokens(query)

    content_terms = [
        token for token in tokens
        if len(token) > 2 and token not in STOPWORDS
    ]

    return content_terms


def infer_query_phrases(query):
    """
    Infer phrase-like units without requiring punctuation.

    Example:
    Turkish ideophones under negation
    -> Turkish ideophones
    -> ideophones negation
    -> Turkish ideophones negation
    """
    content_terms = extract_content_terms(query)

    phrases = []

    for i in range(len(content_terms) - 1):
        phrases.append(f"{content_terms[i]} {content_terms[i + 1]}")

    for i in range(len(content_terms) - 2):
        phrases.append(
            f"{content_terms[i]} {content_terms[i + 1]} {content_terms[i + 2]}"
        )

    return phrases


def describe_interpreted_query(query):
    """
    Create a readable explanation of how the app interpreted the query.
    """
    content_terms = extract_content_terms(query)

    if len(content_terms) >= 3:
        return (
            "The app interpreted your query as a search for works connecting "
            f"{', '.join(content_terms[:-1])}, and {content_terms[-1]}."
        )

    if len(content_terms) == 2:
        return (
            "The app interpreted your query as a search for works connecting "
            f"{content_terms[0]} and {content_terms[1]}."
        )

    if len(content_terms) == 1:
        return (
            "The app interpreted your query as a focused search for "
            f"{content_terms[0]}."
        )

    return "The app could not identify enough content terms in the query."


def is_query_too_broad(query):
    """
    Reject broad or ambiguous one-word queries like 'syntax' or 'morphology',
    but allow more specific one-word queries like 'clitics' or 'ideophones'.
    """
    content_terms = extract_content_terms(query)

    if len(content_terms) == 1 and content_terms[0] in BROAD_SINGLE_TERMS:
        return True

    return False


def unit_in_text(unit, text):
    """
    Return True if a term or phrase appears in text.

    For single terms, simple singular/plural variants are allowed.
    For phrases, the phrase must appear directly.
    """
    unit = normalize_text(unit)
    text = normalize_text(text)

    if " " in unit:
        return unit in text

    return any(variant in text for variant in term_variants(unit))


def count_content_term_matches(text, content_terms):
    """Count how many content terms appear in text."""
    text = normalize_text(text)

    count = 0
    for term in content_terms:
        if unit_in_text(term, text):
            count += 1

    return count


def count_phrase_matches(text, phrases):
    """Count how many inferred phrases appear in text."""
    text = normalize_text(text)

    count = 0
    for phrase in phrases:
        if phrase in text:
            count += 1

    return count


def get_openalex_topic_text(work):
    """Collect OpenAlex topic/category metadata into one searchable string."""
    primary_topic = work.get("primary_topic") or {}

    topic_name = primary_topic.get("display_name") or ""

    field = primary_topic.get("field") or {}
    field_name = field.get("display_name") or ""

    subfield = primary_topic.get("subfield") or {}
    subfield_name = subfield.get("display_name") or ""

    domain = primary_topic.get("domain") or {}
    domain_name = domain.get("display_name") or ""

    return normalize_text(
        " ".join([topic_name, field_name, subfield_name, domain_name])
    )


def get_concept_text(work):
    """Collect OpenAlex concept metadata into one searchable string."""
    concepts = work.get("concepts") or []

    concept_names = [
        concept.get("display_name", "")
        for concept in concepts
    ]

    return normalize_text(" ".join(concept_names))


def get_work_searchable_text(work):
    """Collect title, abstract, topic, and concept text."""
    title = work.get("title") or ""
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    topic_text = get_openalex_topic_text(work)
    concept_text = get_concept_text(work)

    return normalize_text(
        " ".join([title, abstract, topic_text, concept_text])
    )


def has_linguistics_signal(work):
    """
    Return True if the work appears to be linguistics-related.

    This checks OpenAlex topic metadata, concepts, title, and abstract.
    """
    searchable_text = get_work_searchable_text(work)

    return any(term in searchable_text for term in LINGUISTICS_SIGNAL_TERMS)


def is_excluded_non_linguistic_work(work):
    """
    Return True if the work looks like biology, medicine, materials science,
    or another non-linguistic domain.

    This is especially useful for ambiguous terms like morphology.
    """
    searchable_text = get_work_searchable_text(work)

    return any(term in searchable_text for term in EXCLUDED_NON_LINGUISTIC_TERMS)


def is_linguistics_work(work):
    """
    Keep works that have a linguistics/language signal and do not look
    strongly non-linguistic.
    """
    return has_linguistics_signal(work) and not is_excluded_non_linguistic_work(work)


def selected_subfield_terms(selected_subfields):
    """Collect search terms for the selected linguistic subfields."""
    terms = set()

    for subfield in selected_subfields:
        terms.update(LINGUISTIC_SUBFIELDS.get(subfield, set()))

    return terms


def matches_selected_subfields(work, selected_subfields):
    """
    Return True if no subfield filter is selected, or if the work matches
    at least one selected linguistic subfield.
    """
    if not selected_subfields:
        return True

    searchable_text = get_work_searchable_text(work)
    terms = selected_subfield_terms(selected_subfields)

    return any(term in searchable_text for term in terms)


def subfield_match_labels(work, selected_subfields=None):
    """
    Return readable subfield labels that match the work.
    If selected_subfields is provided, only check those.
    """
    searchable_text = get_work_searchable_text(work)

    subfields_to_check = selected_subfields or list(LINGUISTIC_SUBFIELDS.keys())
    matched = []

    for subfield in subfields_to_check:
        terms = LINGUISTIC_SUBFIELDS.get(subfield, set())
        if any(term in searchable_text for term in terms):
            matched.append(subfield)

    return matched


def contains_required_abstract_terms(work, content_terms, min_matches=2):
    """
    Return True if the abstract contains enough of the user's content terms.

    If the query has only one content term, one match is enough.
    If the query has two or more content terms, at least two must appear
    in the abstract.
    """
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    if not abstract:
        return False

    required_matches = min(min_matches, len(content_terms))

    return count_content_term_matches(abstract, content_terms) >= required_matches


def relevance_score(work, content_terms, inferred_phrases, selected_subfields=None):
    """
    Score how central the user's topic is to the work.

    Title matches matter most.
    Abstract matches matter strongly.
    Inferred phrase matches help.
    OpenAlex topic/concept matches help.
    Selected subfield matches help.
    Citation count is only a small bonus.
    """
    title = normalize_text(work.get("title") or "")
    abstract = normalize_text(
        reconstruct_abstract(work.get("abstract_inverted_index"))
    )
    topic_text = get_openalex_topic_text(work)
    concept_text = get_concept_text(work)

    score = 0

    for term in content_terms:
        if unit_in_text(term, title):
            score += 6
        if unit_in_text(term, abstract):
            score += 4
        if unit_in_text(term, topic_text):
            score += 3
        if unit_in_text(term, concept_text):
            score += 2

    phrase_text = " ".join([title, abstract, topic_text, concept_text])
    phrase_matches = count_phrase_matches(phrase_text, inferred_phrases)
    score += phrase_matches * 5

    abstract_matches = count_content_term_matches(abstract, content_terms)
    title_matches = count_content_term_matches(title, content_terms)

    if abstract_matches >= 2:
        score += 6

    if title_matches >= 2:
        score += 6

    if is_linguistics_work(work):
        score += 5

    if selected_subfields and matches_selected_subfields(work, selected_subfields):
        score += 5

    cited_by = work.get("cited_by_count", 0) or 0
    score += min(cited_by / 100, 3)

    return score


def build_openalex_search_query(query, selected_subfields=None):
    """
    Add linguistics bias and optional subfield bias to the OpenAlex search.

    This helps prevent ambiguous searches such as 'morphology'
    from drifting into biology.
    """
    content_terms = extract_content_terms(query)
    base_query = " ".join(content_terms)

    subfield_query = ""
    if selected_subfields:
        subfield_query = " ".join(
            subfield.lower()
            for subfield in selected_subfields
        )

    return f"{base_query} linguistics language {subfield_query}".strip()


def search_openalex_relevant(query, selected_subfields=None, max_results=10):
    """
    Search OpenAlex, keep only linguistics-related works whose abstracts
    contain enough of the user's content terms, then rerank them.
    """
    url = "https://api.openalex.org/works"

    content_terms = extract_content_terms(query)
    inferred_phrases = infer_query_phrases(query)
    openalex_query = build_openalex_search_query(query, selected_subfields)

    params = {
        "search": openalex_query,
        "per-page": 100,
        "sort": "relevance_score:desc",
        "mailto": "handesevgi@g.harvard.edu"
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    works = data.get("results", [])

    scored_works = []

    for work in works:
        if (
            is_linguistics_work(work)
            and matches_selected_subfields(work, selected_subfields)
            and contains_required_abstract_terms(
                work,
                content_terms,
                min_matches=2
            )
        ):
            score = relevance_score(
                work,
                content_terms,
                inferred_phrases,
                selected_subfields
            )
            work["custom_relevance_score"] = score
            scored_works.append(work)

    scored_works = sorted(
        scored_works,
        key=lambda item: item["custom_relevance_score"],
        reverse=True
    )

    return scored_works[:max_results]


def google_scholar_search_url(query, selected_subfields=None):
    """Create a Google Scholar search link."""
    scholar_terms = [query, "linguistics"]

    if selected_subfields:
        scholar_terms.extend(selected_subfields)

    scholar_query = " ".join(scholar_terms)

    return f"https://scholar.google.com/scholar?q={quote_plus(scholar_query)}"


def simplified_lingbuzz_query(query):
    """
    Create a shorter LingBuzz query using content words only.

    LingBuzz search can be noisy with long queries, so this keeps
    the search narrower and more manual.
    """
    content_terms = extract_content_terms(query)

    return " ".join(content_terms[:3])


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


def get_topic_label(work):
    """Return the OpenAlex topic label, if available."""
    primary_topic = work.get("primary_topic") or {}
    topic_name = primary_topic.get("display_name")

    if topic_name:
        return topic_name

    return "No OpenAlex topic label"


# -----------------------------
# Sidebar filters
# -----------------------------

st.sidebar.markdown("### Narrow by linguistic subfield")
st.sidebar.caption("Optional. Leave all unchecked to search across linguistics.")

selected_subfields = []

for subfield in LINGUISTIC_SUBFIELDS.keys():
    if st.sidebar.checkbox(subfield):
        selected_subfields.append(subfield)


# -----------------------------
# User input
# -----------------------------

query = st.text_input(
    "Enter your research topic",
    placeholder="e.g. Turkish ideophones under negation"
)


# -----------------------------
# Main search
# -----------------------------

if st.button("Search") and query:
    if is_query_too_broad(query):
        st.warning(
            "Please provide more specific information. For example, instead of "
            "'syntax' or 'morphology', try 'Turkish word order', "
            "'distributed morphology', 'clitics in syntax', or "
            "'ideophones under negation'."
        )
        st.stop()

    content_terms = extract_content_terms(query)
    inferred_phrases = infer_query_phrases(query)

    if not content_terms:
        st.warning("Please enter more specific keywords.")
        st.stop()

    st.markdown("## Results")

    # -----------------------------
    # Query interpretation
    # -----------------------------

    st.markdown("### How the app interpreted your query")
    st.write(describe_interpreted_query(query))

    st.write("Content terms used for filtering:")
    st.code(", ".join(content_terms))

    if inferred_phrases:
        st.write("Phrase-like combinations used for ranking:")
        st.code(", ".join(inferred_phrases))

    if selected_subfields:
        st.write("Selected subfield filters:")
        st.code(", ".join(selected_subfields))

    st.markdown("---")

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
                min-height: 165px;
            ">
                <h4>OpenAlex</h4>
                <p>Linguistics-filtered ranked results are shown below.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    simple_lingbuzz = simplified_lingbuzz_query(query)

    with col2:
        st.markdown(
            f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 1rem;
                background-color: #f8f9fa;
                min-height: 165px;
            ">
                <h4>LingBuzz</h4>
                <p>Manual follow-up search using:</p>
                <p><code>{simple_lingbuzz}</code></p>
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
                min-height: 165px;
            ">
                <h4>Google Scholar</h4>
                <p>Broader scholarly search with a linguistics bias.</p>
                <a href="{google_scholar_search_url(query, selected_subfields)}" target="_blank">
                    Search Google Scholar
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("---")

    # -----------------------------
    # OpenAlex results
    # -----------------------------

    with st.spinner("Searching OpenAlex..."):
        try:
            works = search_openalex_relevant(
                query,
                selected_subfields=selected_subfields,
                max_results=10
            )
        except Exception as error:
            st.error(f"OpenAlex search failed: {error}")
            st.stop()

    if not works:
        st.warning(
            "No linguistics-related OpenAlex works found whose abstract contains "
            "enough of the content terms and matches the selected subfield filters. "
            "Try fewer filters, add a language, add a construction, or use a more "
            "specific topic such as 'Turkish morphology', 'ideophones under negation', "
            "or 'clitics in syntax'."
        )
        st.stop()

    st.markdown("### Top 10 linguistics-related OpenAlex results")

    for index, work in enumerate(works, start=1):
        title = work.get("title") or "Untitled"
        year = work.get("publication_year") or "n.d."
        cited_by = work.get("cited_by_count", 0)
        score = work.get("custom_relevance_score", 0)
        author_text = get_author_text(work)
        link = get_work_link(work)
        abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
        topic_label = get_topic_label(work)

        abstract_matches = count_content_term_matches(abstract, content_terms)
        matched_subfields = subfield_match_labels(work, selected_subfields)

        with st.container():
            st.markdown(f"#### {index}. {title}")
            st.markdown(f"**Authors:** {author_text}")
            st.markdown(
                f"**Year:** {year} | **Cited by:** {cited_by} | "
                f"**Relevance score:** {score:.2f}"
            )
            st.markdown(f"**OpenAlex topic:** {topic_label}")
            st.markdown(
                f"**Matched content terms in abstract:** {abstract_matches}"
            )

            if matched_subfields:
                st.markdown(
                    f"**Matched subfield(s):** {', '.join(matched_subfields)}"
                )

            if link:
                st.markdown(f"[Open work]({link})")

            if abstract:
                with st.expander("Abstract"):
                    st.write(abstract)

            st.divider() on
