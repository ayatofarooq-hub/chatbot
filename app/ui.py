"""Streamlit interface for the internal Iraqi legal assistant."""

import httpx
import ollama
import streamlit as st
from chromadb.errors import NotFoundError

try:
    from .build_index import COLLECTION_NAME
    from .rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
    from .search_index import search
    from .ui_components import (
        SUGGESTED_QUESTIONS,
        inject_design_system,
        render_global_header,
        render_history_items,
        render_insight_card,
        render_navigation,
        render_panel_heading,
        render_source_cards,
        render_welcome,
        render_workspace_toolbar,
    )
except ImportError:
    try:
        from app.build_index import COLLECTION_NAME
        from app.rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
        from app.search_index import search
        from app.ui_components import (
            SUGGESTED_QUESTIONS,
            inject_design_system,
            render_global_header,
            render_history_items,
            render_insight_card,
            render_navigation,
            render_panel_heading,
            render_source_cards,
            render_welcome,
            render_workspace_toolbar,
        )
    except ImportError:
        from build_index import COLLECTION_NAME
        from rag_answer import CITATION_PATTERN, generate_answer, get_quick_response
        from search_index import search
        from ui_components import (
            SUGGESTED_QUESTIONS,
            inject_design_system,
            render_global_header,
            render_history_items,
            render_insight_card,
            render_navigation,
            render_panel_heading,
            render_source_cards,
            render_welcome,
            render_workspace_toolbar,
        )


PAGE_TITLE = "المساعد القانوني العراقي"
RETRIEVED_SNIPPETS_TITLE = "النصوص المسترجعة من قاعدة المعرفة"


def configure_page() -> None:
    """Configure Streamlit and load the shared PDF-derived design system."""

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="⚖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_design_system()


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
            {"source_file": citation[0], "page_number": citation[1]}
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
        snippets.append(
            {
                "rank": index,
                "source_file": metadata.get("source_file", "غير معروف"),
                "page_number": metadata.get("page_number", "غير معروف"),
                "document_title": metadata.get("document_title", ""),
                "legal_reference": metadata.get("legal_reference", ""),
                "article_reference": metadata.get("article_reference", ""),
                "section_title": metadata.get("section_title", ""),
                "source_type": metadata.get("source_type", ""),
                "distance": (
                    distances[index - 1] if index <= len(distances) else None
                ),
                "text": document,
            }
        )
    return snippets


def render_citations(citations: list[dict]) -> None:
    """Display citations below an answer."""

    if not citations:
        st.caption("لم تتضمن الإجابة استشهادات.")
        return
    st.markdown("##### المصادر والاستشهادات")
    for citation in citations:
        st.markdown(
            f"- **{citation['source_file']}**، الصفحة "
            f"**{citation['page_number']}**"
        )


def render_vetting_warnings(warnings: list[str]) -> None:
    """Display citation-vetting warnings without suppressing the answer."""

    if not warnings:
        return
    st.warning(
        "لم تجتز الإجابة جميع فحوصات الاستشهادات. "
        "راجع الملاحظات الآتية قبل الاعتماد عليها."
    )
    for warning in warnings:
        st.markdown(f"- {warning}")


def render_snippets(snippets: list[dict]) -> None:
    """Display full retrieved passages in a collapsed evidence section."""

    with st.expander(RETRIEVED_SNIPPETS_TITLE):
        if not snippets:
            st.caption("لا توجد نصوص مسترجعة.")
            return
        for snippet in snippets:
            reference = snippet.get("legal_reference")
            reference_label = (
                f" · {reference}" if reference else ""
            )
            st.markdown(
                f"**المقطع {snippet['rank']} · {snippet['source_file']} · "
                f"الصفحة {snippet['page_number']}{reference_label}**"
            )
            if snippet["distance"] is not None:
                st.caption(f"المسافة: {snippet['distance']:.6f}")
            st.text(snippet["text"])
            if snippet["rank"] < len(snippets):
                st.divider()


def render_assistant_message(message: dict) -> None:
    """Display one assistant answer and all supporting information."""

    st.markdown(message["content"])
    render_vetting_warnings(message.get("warnings", []))
    render_citations(message.get("citations", []))
    render_snippets(message.get("snippets", []))


def initialize_state() -> None:
    """Initialize browser-session conversation state."""

    if "messages" not in st.session_state:
        st.session_state.messages = []


def active_conversation_title() -> str:
    """Return a short title based on the first user question."""

    for message in st.session_state.messages:
        if message.get("role") == "user":
            content = message["content"]
            return content if len(content) <= 46 else f"{content[:43]}..."
    return "محادثة قانونية جديدة"


def latest_assistant_message() -> dict:
    """Return the newest assistant message, or an empty display payload."""

    for message in reversed(st.session_state.messages):
        if message.get("role") == "assistant":
            return message
    return {"snippets": [], "warnings": [], "citations": []}


def render_history() -> None:
    """Render all messages in the central workspace."""

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
            "warnings": [],
            "citations": [],
            "snippets": [],
        }

    results = search(question)
    answer_result = generate_answer(question, results)
    return {
        "role": "assistant",
        "content": answer_result.content,
        "warnings": answer_result.warnings,
        "citations": extract_citations(answer_result.content),
        "snippets": extract_snippets(results),
    }


def show_error(error: Exception) -> None:
    """Display a concise Arabic diagnostic message."""

    if isinstance(error, NotFoundError):
        st.error(
            f"المجموعة '{COLLECTION_NAME}' غير موجودة. "
            "شغّل python app/build_index.py أولاً."
        )
    elif isinstance(error, (ConnectionError, httpx.ConnectError)):
        st.error("تعذر الاتصال بخدمة Ollama. تأكد من تشغيلها.")
    elif isinstance(error, httpx.TimeoutException):
        st.error(
            "انتهت مهلة طلب Ollama. تحقق من موارد الجهاز أو استخدم نموذجاً أصغر."
        )
    elif isinstance(error, ollama.ResponseError):
        st.error(f"فشل طلب Ollama: {error}")
    else:
        st.error(f"تعذر إنشاء الإجابة: {error}")


def render_evidence_panel() -> None:
    """Render the PDF's related-decisions and analysis panel."""

    latest = latest_assistant_message()
    snippets = latest.get("snippets", [])
    render_panel_heading(
        "قرارات ووثائق ذات صلة",
        f"{len(snippets)} مراجع" if snippets else None,
    )
    render_source_cards(snippets)
    render_insight_card(
        latest.get("warnings", []),
        latest.get("citations", []),
    )
    st.markdown("###### أدوات إضافية")
    st.file_uploader(
        "تحميل وثيقة للمراجعة",
        type=["txt", "pdf"],
        disabled=True,
        help="إضافة الوثائق تتم حالياً من خلال واجهة إدارة الوثائق.",
    )


def render_conversation_panel() -> None:
    """Render the PDF's conversation-history panel."""

    render_panel_heading("سجل المحادثات")
    st.text_input(
        "بحث في المحادثات",
        placeholder="بحث في المحفوظات...",
        label_visibility="collapsed",
        disabled=True,
    )
    st.caption("الأحدث")
    render_history_items(st.session_state.messages)
    st.divider()
    if st.button("مسح سجل المحادثة", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


def render_workspace() -> str | None:
    """Render the central chat workspace and return a selected suggestion."""

    render_workspace_toolbar(active_conversation_title())
    selected_question = None
    if not st.session_state.messages:
        render_welcome()
        columns = st.columns(2)
        for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
            if columns[index % 2].button(
                suggestion,
                key=f"suggestion-{index}",
                use_container_width=True,
            ):
                selected_question = suggestion
    render_history()
    return selected_question


def main() -> None:
    """Run the complete responsive legal-assistant interface."""

    configure_page()
    initialize_state()
    if render_navigation():
        st.session_state.messages = []
        st.rerun()

    render_global_header()
    evidence_column, workspace_column, history_column = st.columns(
        [0.92, 1.55, 0.92],
        gap="large",
    )

    with evidence_column:
        render_evidence_panel()
    with workspace_column:
        suggested_question = render_workspace()
    with history_column:
        render_conversation_panel()

    typed_question = st.chat_input(
        "اسأل عن أي قانون أو لائحة أو وثيقة عراقية..."
    )
    question = typed_question or suggested_question
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with workspace_column:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("جارٍ البحث في الوثائق وإعداد الإجابة..."):
                try:
                    assistant_message = answer_question(question)
                    render_assistant_message(assistant_message)
                    st.session_state.messages.append(assistant_message)
                except Exception as error:
                    show_error(error)


if __name__ == "__main__":
    main()
