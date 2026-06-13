"""Simple Streamlit interface for the internal Iraqi legal assistant."""

import ollama
import httpx
import streamlit as st
from chromadb.errors import NotFoundError

try:
    from .build_index import COLLECTION_NAME
    from .rag_answer import (
        CITATION_PATTERN,
        generate_answer,
        get_quick_response,
    )
    from .search_index import search
except ImportError:
    try:
        # Streamlit commonly runs the file without package metadata.
        from app.build_index import COLLECTION_NAME
        from app.rag_answer import (
            CITATION_PATTERN,
            generate_answer,
            get_quick_response,
        )
        from app.search_index import search
    except ImportError:
        # Support direct execution with: python app/ui.py
        from build_index import COLLECTION_NAME
        from rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
        from search_index import search


PAGE_TITLE = "المساعد القانوني العراقي الداخلي"
RETRIEVED_SNIPPETS_TITLE = "المقاطع المسترجعة من قاعدة المعرفة"


def configure_page() -> None:
    """Configure the page and apply a clean right-to-left Arabic layout."""

    st.set_page_config(
        page_title=PAGE_TITLE,
        layout="centered",
    )
    st.markdown(
        """
        <style>
        html, body, [class*="st-"], [data-testid="stAppViewContainer"] {
            direction: rtl;
            text-align: right;
        }

        [data-testid="stChatInput"] textarea {
            direction: rtl;
            text-align: right;
        }

        [data-testid="stChatMessage"] {
            direction: rtl;
            text-align: right;
        }

        code, pre {
            direction: rtl;
            text-align: right;
            white-space: pre-wrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def extract_citations(answer: str) -> list[dict]:
    """Return unique citations in the order they appear in the answer."""

    citations = []
    seen = set()

    for source_file, page_number in CITATION_PATTERN.findall(answer):
        citation = (source_file.strip(), page_number)
        if citation in seen:
            continue

        seen.add(citation)
        citations.append(
            {
                "source_file": citation[0],
                "page_number": citation[1],
            }
        )

    return citations


def extract_snippets(results: dict) -> list[dict]:
    """Convert Chroma query results into display-friendly snippets."""

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    snippets = []

    for index, (document, metadata) in enumerate(
        zip(documents, metadatas),
        start=1,
    ):
        distance = distances[index - 1] if index <= len(distances) else None
        snippets.append(
            {
                "rank": index,
                "source_file": metadata.get("source_file", "غير معروف"),
                "page_number": metadata.get("page_number", "غير معروف"),
                "distance": distance,
                "text": document,
            }
        )

    return snippets


def render_citations(citations: list[dict]) -> None:
    """Display answer citations in a separate section."""

    st.markdown("#### المصادر والاستشهادات")

    if not citations:
        st.caption("لم تتضمن الإجابة استشهادات.")
        return

    for citation in citations:
        st.markdown(
            f"- **{citation['source_file']}**، الصفحة: "
            f"**{citation['page_number']}**"
        )


def render_snippets(snippets: list[dict]) -> None:
    """Display retrieved evidence in a collapsed expandable section."""

    with st.expander(RETRIEVED_SNIPPETS_TITLE):
        if not snippets:
            st.caption("لا توجد مقاطع مسترجعة.")
            return

        for snippet in snippets:
            heading = (
                f"المقطع {snippet['rank']} | "
                f"{snippet['source_file']} | "
                f"الصفحة {snippet['page_number']}"
            )
            st.markdown(f"**{heading}**")

            if snippet["distance"] is not None:
                st.caption(f"المسافة: {snippet['distance']:.6f}")

            st.text(snippet["text"])

            if snippet["rank"] < len(snippets):
                st.divider()


def render_assistant_message(message: dict) -> None:
    """Display one answer and its supporting retrieval information."""

    st.markdown(message["content"])
    render_citations(message.get("citations", []))
    render_snippets(message.get("snippets", []))


def initialize_history() -> None:
    """Create conversation storage for the current browser session."""

    if "messages" not in st.session_state:
        st.session_state.messages = []


def render_history() -> None:
    """Render all user and assistant messages from session state."""

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                render_assistant_message(message)
            else:
                st.markdown(message["content"])


def answer_question(question: str) -> dict:
    """Retrieve context and generate a grounded answer."""

    quick_response = get_quick_response(question)
    if quick_response:
        return {
            "role": "assistant",
            "content": quick_response,
            "citations": [],
            "snippets": [],
        }

    results = search(question)
    answer = generate_answer(question, results)

    return {
        "role": "assistant",
        "content": answer,
        "citations": extract_citations(answer),
        "snippets": extract_snippets(results),
    }


def show_error(error: Exception) -> None:
    """Display a concise Arabic diagnostic message."""

    if isinstance(error, NotFoundError):
        st.error(
            f"المجموعة '{COLLECTION_NAME}' غير موجودة. "
            "شغّل python app/build_index.py أولاً."
        )
    elif isinstance(error, ConnectionError):
        st.error("تعذر الاتصال بخدمة Ollama. تأكد من تشغيلها.")
    elif isinstance(error, httpx.TimeoutException):
        st.error(
            "انتهت مهلة طلب Ollama. تحقق من موارد الجهاز أو استخدم نموذجاً أصغر."
        )
    elif isinstance(error, ollama.ResponseError):
        st.error(f"فشل طلب Ollama: {error}")
    else:
        st.error(f"تعذر إنشاء الإجابة: {error}")


def main() -> None:
    """Run the Streamlit chat interface."""

    configure_page()
    initialize_history()

    st.title(PAGE_TITLE)
    st.caption("نظام داخلي للاستدلال من قاعدة المعرفة القانونية المحلية.")

    render_history()

    question = st.chat_input("اكتب سؤالك القانوني هنا")
    if not question:
        return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("جارٍ البحث وإعداد الإجابة..."):
            try:
                assistant_message = answer_question(question)
                render_assistant_message(assistant_message)
                st.session_state.messages.append(assistant_message)
            except Exception as error:
                show_error(error)


if __name__ == "__main__":
    main()
