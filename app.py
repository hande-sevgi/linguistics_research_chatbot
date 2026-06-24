import requests
import streamlit as st

st.set_page_config(
    page_title="Linguistics Research Assistant",
    page_icon="📚",
    layout="centered"
)

st.title("Linguistics Research Assistant")
st.caption("Search open scholarly metadata from OpenAlex for linguistics-related works.")

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

query = st.text_input("Enter keywords, e.g. Turkish ideophones negation")

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
