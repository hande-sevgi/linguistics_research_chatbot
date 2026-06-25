# linguistics_terms.py

"""
Controlled vocabulary for the literature-discovery app.

This file keeps linguistics-specific vocabulary separate from app.py.
The goal is not to list every possible linguistic term, but to help the app:

1. reject overly broad one-word searches,
2. allow specialized one-word searches,
3. ignore relation words like "under" and "in",
4. recognize common linguistic phrases,
5. match related forms like pragmatics/pragmatic and ideophones/ideophone.
"""


# -----------------------------
# Very broad one-word searches
# -----------------------------
# These are too broad when used alone.
# Example: "syntax" should trigger "please provide more information."

BROAD_SINGLE_TERMS = {
    "syntax",
    "semantics",
    "phonology",
    "morphology",
    "linguistics",
    "language",
    "grammar",
    "discourse",
    "meaning",
    "words",
    "sentences",
    "speech",
    "communication",
    "acquisition",
    "variation",
    "typology",
    "sociolinguistics",
    "psycholinguistics",
    "phonetics",
}


# -----------------------------
# Stopwords / relation words
# -----------------------------
# These words help express the user's intended relation,
# but they should not count as keywords by themselves.
#
# Example:
# "Turkish ideophones under negation"
# should become:
# "turkish", "ideophones", "negation"
#
# not:
# "turkish", "ideophones", "under", "negation"

STOPWORDS = {
    "the",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "to",
    "a",
    "an",
    "with",
    "by",
    "from",
    "about",
    "into",
    "across",
    "under",
    "over",
    "between",
    "among",
    "through",
    "during",
    "within",
    "without",
    "via",
    "toward",
    "towards",
    "against",
    "at",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "their",
    "his",
    "her",
    "our",
    "your",
    "my",
}


# -----------------------------
# Specialized one-word terms
# -----------------------------
# These are allowed as one-word searches.
# Example: "clitics" or "ideophones" should be allowed.

SPECIALIZED_LINGUISTIC_TERMS = {
    # Morphosyntax
    "accusative",
    "agreement",
    "alignment",
    "anaphor",
    "anaphora",
    "applicative",
    "aspect",
    "binding",
    "case",
    "causative",
    "clitic",
    "clitics",
    "control",
    "dative",
    "ellipsis",
    "ergative",
    "ergativity",
    "evidential",
    "evidentials",
    "focus",
    "genitive",
    "imperative",
    "island",
    "modality",
    "mood",
    "movement",
    "nominative",
    "passive",
    "polarity",
    "raising",
    "reciprocal",
    "reflexive",
    "scrambling",
    "sluicing",
    "tense",
    "topic",
    "valency",
    "voice",

    # Semantics and pragmatics
    "alternatives",
    "anaphora",
    "assertion",
    "conditional",
    "counterfactual",
    "definiteness",
    "deixis",
    "entailment",
    "exhaustivity",
    "implicature",
    "indexicality",
    "mirativity",
    "negation",
    "negative",
    "presupposition",
    "quantification",
    "scalarity",
    "scope",
    "specificity",
    "vagueness",

    # Phonology and phonetics
    "affricate",
    "allophone",
    "assimilation",
    "consonant",
    "deletion",
    "dissimilation",
    "epenthesis",
    "fortition",
    "gemination",
    "harmony",
    "intonation",
    "lenition",
    "nasalization",
    "palatalization",
    "prosody",
    "stress",
    "syllable",
    "tone",
    "vowel",

    # Morphology
    "affix",
    "affixation",
    "allomorph",
    "allomorphy",
    "circumfix",
    "compounding",
    "derivation",
    "infix",
    "inflection",
    "nominalization",
    "prefix",
    "reduplication",
    "suffix",
    "suppletion",
    "verbalization",

    # Lexical / typological / descriptive
    "classifier",
    "classifiers",
    "ideophone",
    "ideophones",
    "particle",
    "particles",
    "serial",
    "switch-reference",

    # Methods / experimental linguistics
    "acceptability",
    "elicitation",
    "judgment",
    "judgments",
    "corpus",
    "experiment",
    "production",
    "comprehension",
}


# -----------------------------
# Multi-word linguistic phrases
# -----------------------------
# These can help future versions of the app recognize phrase-level topics.
# Users do not need quotation marks, but these are useful as a vocabulary list.

PHRASE_TERMS = {
    # Syntax / morphosyntax
    "argument structure",
    "case marking",
    "complement clause",
    "differential object marking",
    "long distance dependency",
    "negative concord",
    "negative polarity item",
    "object agreement",
    "positive polarity item",
    "relative clause",
    "serial verb construction",
    "subject agreement",
    "switch reference",
    "wh movement",
    "wh question",

    # Semantics / pragmatics
    "discourse particle",
    "event structure",
    "focus particle",
    "information structure",
    "modal concord",
    "scope ambiguity",
    "semantic scope",
    "speech act",

    # Phonology / phonetics
    "stress assignment",
    "tone sandhi",
    "vowel harmony",

    # Morphology
    "agreement marker",
    "nominal classification",
}


# -----------------------------
# Variant mappings
# -----------------------------
# These are hand-coded equivalences or near-equivalences that simple
# singular/plural matching may miss.
#
# The app can use this to match:
# "pragmatics" with "pragmatic"
# "negation" with "negative"
# "ideophones" with "ideophone"

TERM_VARIANTS = {
    "pragmatics": {"pragmatic"},
    "pragmatic": {"pragmatics"},

    "semantics": {"semantic"},
    "semantic": {"semantics"},

    "phonetics": {"phonetic"},
    "phonetic": {"phonetics"},

    "negation": {"negative", "negated"},
    "negative": {"negation", "negated"},
    "negated": {"negation", "negative"},

    "ideophone": {"ideophones", "ideophonic"},
    "ideophones": {"ideophone", "ideophonic"},
    "ideophonic": {"ideophone", "ideophones"},

    "clitic": {"clitics"},
    "clitics": {"clitic"},

    "evidential": {"evidentials", "evidentiality"},
    "evidentials": {"evidential", "evidentiality"},
    "evidentiality": {"evidential", "evidentials"},

    "presupposition": {"presuppositional"},
    "presuppositional": {"presupposition"},

    "implicature": {"implicatures"},
    "implicatures": {"implicature"},

    "morphology": {"morphological"},
    "morphological": {"morphology"},

    "phonology": {"phonological"},
    "phonological": {"phonology"},

    "typology": {"typological"},
    "typological": {"typology"},

    "turkish": {"turkic"},
    "turkic": {"turkish"},
}
