"""Reusable presentation components for the Streamlit legal assistant."""

from html import escape

import streamlit as st


COLORS = {
    "green": "#145A38",
    "green_dark": "#0D472D",
    "green_soft": "#EAF5EE",
    "gold": "#C9A408",
    "ink": "#17211B",
    "muted": "#7A847E",
    "border": "#E5EAE7",
    "surface": "#FFFFFF",
    "background": "#F7F9F8",
}

SUGGESTED_QUESTIONS = (
    "لخص أهم الأحكام القانونية ذات الصلة",
    "قارن بين النصوص والوثائق المسترجعة",
    "ما هي الجهات أو الأطراف المعنية؟",
    "استخرج الالتزامات والإجراءات المطلوبة",
)


def inject_design_system() -> None:
    """Apply the PDF-derived visual system and responsive layout rules."""

    st.markdown(
        """
        <style>
        :root {
            --gov-green: #145A38;
            --gov-green-dark: #0D472D;
            --gov-green-soft: #EAF5EE;
            --gov-gold: #C9A408;
            --ink: #17211B;
            --muted: #7A847E;
            --border: #E5EAE7;
            --surface: #FFFFFF;
            --canvas: #F7F9F8;
            --shadow: 0 8px 24px rgba(20, 66, 43, 0.06);
        }

        html, body, [class*="st-"], [data-testid="stAppViewContainer"] {
            direction: rtl;
            text-align: right;
        }

        html, body {
            font-family: "Segoe UI", Tahoma, Arial, sans-serif;
        }

        [data-testid="stAppViewContainer"] {
            background: var(--canvas);
        }

        [data-testid="stHeader"] {
            height: 0;
            background: transparent;
        }

        [data-testid="stToolbar"] {
            display: none;
        }

        [data-testid="stSidebar"] {
            left: auto;
            right: 0;
            width: 260px !important;
            min-width: 260px !important;
            background: linear-gradient(180deg, var(--gov-green) 0%, var(--gov-green-dark) 100%);
            border: 0;
        }

        [data-testid="stSidebar"] > div:first-child {
            width: 260px;
            padding: 1.2rem 1rem;
        }

        [data-testid="stSidebar"] * {
            color: #FFFFFF;
        }

        [data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.12);
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            min-height: 3.25rem;
            justify-content: flex-start;
            padding-inline: 1rem;
            border: 0;
            border-radius: 0.75rem;
            background: transparent;
            color: #FFFFFF;
            font-weight: 700;
        }

        [data-testid="stSidebar"] .stButton > button:hover,
        [data-testid="stSidebar"] .stButton > button:focus {
            background: var(--gov-gold);
            color: #FFFFFF;
        }

        [data-testid="stAppViewContainer"] > .main {
            margin-right: 260px;
        }

        .block-container {
            max-width: none;
            padding: 0 1.25rem 7.5rem;
        }

        .gov-header {
            min-height: 82px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
            margin: 0 -1.25rem 1rem;
            padding: 0 1.5rem;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
        }

        .gov-brand {
            color: var(--gov-green);
            font-size: 1.15rem;
            font-weight: 800;
            white-space: nowrap;
        }

        .gov-search {
            width: min(420px, 45vw);
            padding: 0.8rem 1rem;
            color: #A0A7A3;
            background: #FAFBFA;
            border: 1px solid #F0F2F1;
            border-radius: 0.75rem;
        }

        .gov-profile {
            display: flex;
            align-items: center;
            gap: 0.65rem;
        }

        .gov-avatar {
            display: grid;
            place-items: center;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            color: #FFFFFF;
            background: var(--gov-green);
            font-weight: 800;
        }

        .panel-heading {
            min-height: 56px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 0 -0.65rem 1rem;
            padding: 0 0.8rem 0.8rem;
            border-bottom: 1px solid var(--border);
        }

        .panel-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 800;
        }

        .count-pill {
            padding: 0.25rem 0.55rem;
            color: var(--muted);
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 999px;
            font-size: 0.72rem;
        }

        .workspace-toolbar {
            min-height: 66px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0 -0.65rem 1rem;
            padding: 0 0.8rem 0.8rem;
            border-bottom: 1px solid var(--border);
        }

        .workspace-title {
            color: var(--ink);
            font-size: 1.08rem;
            font-weight: 800;
        }

        .workspace-meta {
            margin-top: 0.2rem;
            color: var(--muted);
            font-size: 0.75rem;
        }

        .online-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            margin-left: 0.3rem;
            border-radius: 50%;
            background: #23B26D;
        }

        .toolbar-actions {
            color: var(--muted);
            font-size: 0.8rem;
            white-space: nowrap;
        }

        .welcome-state {
            max-width: 640px;
            margin: 3.4rem auto 2rem;
            text-align: center;
        }

        .shield-mark {
            display: grid;
            place-items: center;
            width: 76px;
            height: 76px;
            margin: 0 auto 1.2rem;
            border: 5px solid #FFFFFF;
            border-radius: 50%;
            color: #FFFFFF;
            background: var(--gov-green);
            box-shadow: 0 7px 20px rgba(20, 90, 56, 0.22);
            font-size: 1.65rem;
            font-weight: 900;
        }

        .welcome-state h1 {
            margin: 0 0 0.65rem;
            color: var(--ink);
            font-size: clamp(1.6rem, 3vw, 2.2rem);
        }

        .welcome-state p {
            margin: 0 auto;
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.9;
        }

        .history-item {
            margin-bottom: 0.55rem;
            padding: 0.95rem 1rem;
            color: var(--ink);
            background: transparent;
            border: 1px solid transparent;
            border-radius: 0.8rem;
            font-size: 0.88rem;
            font-weight: 650;
        }

        .history-item.active {
            background: #CDEED9;
            border-color: #ACDFC0;
        }

        .history-date {
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.7rem;
            font-weight: 400;
        }

        .source-card {
            margin-bottom: 0.8rem;
            padding: 1rem;
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 0.8rem;
            box-shadow: 0 4px 14px rgba(20, 66, 43, 0.04);
        }

        .source-file {
            color: var(--gov-gold);
            font-size: 0.78rem;
            font-weight: 800;
        }

        .source-title {
            margin-top: 0.35rem;
            color: var(--ink);
            font-size: 0.88rem;
            font-weight: 750;
            line-height: 1.6;
        }

        .source-meta {
            margin-top: 0.45rem;
            color: var(--muted);
            font-size: 0.7rem;
        }

        .insight-card {
            margin-top: 1rem;
            padding: 1rem;
            background: #F0F8F3;
            border: 1px solid #DDEEE3;
            border-radius: 0.8rem;
        }

        .insight-title {
            margin-bottom: 0.55rem;
            color: var(--ink);
            font-size: 0.85rem;
            font-weight: 800;
        }

        .insight-card li {
            margin-bottom: 0.4rem;
            color: #47544C;
            font-size: 0.76rem;
            line-height: 1.65;
        }

        [data-testid="stChatMessage"] {
            max-width: 760px;
            margin: 0.75rem auto;
            padding: 1rem 1.15rem;
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 0.9rem;
            box-shadow: 0 5px 15px rgba(20, 66, 43, 0.04);
        }

        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
            margin-right: 0;
            background: var(--gov-green);
            border-color: var(--gov-green);
        }

        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) * {
            color: #FFFFFF;
        }

        [data-testid="stChatInput"] {
            max-width: 760px;
            margin: 0 auto;
            background: #FFFFFF;
            border: 1px solid var(--border);
            border-radius: 0.95rem;
            box-shadow: 0 10px 28px rgba(20, 66, 43, 0.12);
        }

        [data-testid="stChatInput"] textarea {
            direction: rtl;
            text-align: right;
        }

        div[data-testid="stButton"] > button {
            min-height: 2.65rem;
            border: 1px solid var(--border);
            border-radius: 999px;
            color: var(--ink);
            background: #FFFFFF;
            font-size: 0.78rem;
        }

        div[data-testid="stButton"] > button:hover {
            color: var(--gov-green);
            border-color: var(--gov-green);
        }

        [data-testid="stExpander"] {
            background: #FAFBFA;
            border: 1px solid var(--border);
            border-radius: 0.75rem;
        }

        code, pre {
            direction: rtl;
            text-align: right;
            white-space: pre-wrap;
        }

        @media (max-width: 1100px) {
            [data-testid="stSidebar"] {
                left: 0;
                right: auto;
            }

            [data-testid="stAppViewContainer"] > .main {
                margin-right: 0;
            }

            .gov-profile {
                display: none;
            }

            .gov-search {
                width: min(55vw, 380px);
            }
        }

        @media (max-width: 760px) {
            .block-container {
                padding-inline: 0.75rem;
            }

            .gov-header {
                min-height: 70px;
                margin-inline: -0.75rem;
                padding-inline: 1rem;
            }

            .gov-search {
                display: none;
            }

            .gov-brand {
                white-space: normal;
                font-size: 1rem;
            }

            .welcome-state {
                margin-top: 2rem;
            }

            .toolbar-actions {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_global_header() -> None:
    """Render the white global header shown across the PDF screen."""

    st.markdown(
        """
        <header class="gov-header">
            <div class="gov-brand">مجلس الوزراء - المساعد القانوني</div>
            <div class="gov-search">⌕ &nbsp; البحث في الوثائق والتشريعات...</div>
            <div class="gov-profile">
                <div>
                    <div style="font-weight:800;color:#17211B;">المستخدم الداخلي</div>
                    <div style="font-size:.72rem;color:#7A847E;">الدائرة القانونية</div>
                </div>
                <div class="gov-avatar">ق</div>
            </div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_navigation() -> bool:
    """Render the green navigation rail and return whether reset was requested."""

    with st.sidebar:
        st.markdown(
            """
            <div style="padding:.5rem .4rem 1.4rem;">
                <div style="font-size:.76rem;opacity:.75;">مجلس الوزراء</div>
                <div style="font-size:1.28rem;font-weight:850;margin-top:.2rem;">
                    نظام إدارة القرارات
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style="padding:.9rem 1rem;margin-bottom:.6rem;border-radius:.75rem;
                        background:#C9A408;font-weight:800;">
                ◫ &nbsp; المساعد الذكي
            </div>
            """,
            unsafe_allow_html=True,
        )
        reset_requested = st.button("＋  محادثة جديدة", use_container_width=True)
        st.markdown("---")
        st.caption("مركز الدعم")
        st.caption("سياسة الاستخدام الداخلي")
        st.markdown(
            """
            <div style="position:fixed;bottom:1.5rem;color:#F0B6B6;font-weight:700;">
                تسجيل الخروج &nbsp; ↪
            </div>
            """,
            unsafe_allow_html=True,
        )
    return reset_requested


def render_panel_heading(title: str, badge: str | None = None) -> None:
    """Render a panel heading with an optional count badge."""

    badge_html = f'<span class="count-pill">{escape(badge)}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="panel-heading">
            <span class="panel-title">{escape(title)}</span>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_workspace_toolbar(title: str) -> None:
    """Render the active chat title and model status."""

    st.markdown(
        f"""
        <div class="workspace-toolbar">
            <div>
                <div class="workspace-title">{escape(title)}</div>
                <div class="workspace-meta">
                    <span class="online-dot"></span>
                    نشط الآن · ذكاء اصطناعي محلي
                </div>
            </div>
            <div class="toolbar-actions">تصدير الاستجابة &nbsp; ⇩ &nbsp;&nbsp; تصفية ⌄</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_welcome() -> None:
    """Render the central assistant welcome state."""

    st.markdown(
        """
        <section class="welcome-state">
            <div class="shield-mark">✓</div>
            <h1>مرحباً بك في المساعد القانوني</h1>
            <p>
                أنا مساعدك الذكي لتحليل القوانين واللوائح والوثائق العراقية.
                اطرح سؤالك وسأعرض الإجابة مع المراجع المسترجعة والتنبيهات اللازمة.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_history_items(messages: list[dict]) -> None:
    """Render conversation-history cards based on the current session."""

    user_messages = [
        message["content"]
        for message in messages
        if message.get("role") == "user"
    ]
    if not user_messages:
        st.markdown(
            '<div style="color:#7A847E;font-size:.8rem;padding:1rem;">'
            "لا توجد محادثات بعد.</div>",
            unsafe_allow_html=True,
        )
        return

    for index, content in enumerate(reversed(user_messages[-5:])):
        title = content if len(content) <= 48 else f"{content[:45]}..."
        active = " active" if index == 0 else ""
        st.markdown(
            f"""
            <div class="history-item{active}">
                {escape(title)}
                <div class="history-date">المحادثة الحالية</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_source_cards(snippets: list[dict]) -> None:
    """Render retrieved passages as compact official-document cards."""

    if not snippets:
        st.markdown(
            '<div style="color:#7A847E;font-size:.8rem;padding:1rem 0;">'
            "ستظهر المراجع المسترجعة هنا بعد طرح السؤال.</div>",
            unsafe_allow_html=True,
        )
        return

    for snippet in snippets[:3]:
        text = " ".join(str(snippet.get("text", "")).split())
        summary = text if len(text) <= 115 else f"{text[:112]}..."
        source_file = str(snippet.get("source_file", "غير معروف"))
        page_number = str(snippet.get("page_number", "غير معروف"))
        legal_reference = str(snippet.get("legal_reference", "")).strip()
        source_meta = (
            legal_reference
            if legal_reference
            else f"الصفحة {page_number}"
        )
        st.markdown(
            f"""
            <article class="source-card">
                <div class="source-file">{escape(source_file)}</div>
                <div class="source-title">{escape(summary)}</div>
                <div class="source-meta">{escape(source_meta)}</div>
            </article>
            """,
            unsafe_allow_html=True,
        )


def render_insight_card(warnings: list[str], citations: list[dict]) -> None:
    """Render a compact analysis card inspired by the PDF insight panel."""

    items = []
    if citations:
        items.append(f"تم العثور على {len(citations)} استشهادات في الإجابة.")
    if warnings:
        items.append(f"توجد {len(warnings)} ملاحظات تحتاج إلى مراجعة.")
    if not items:
        items.append("ستظهر نتائج التحقق والتحليل هنا بعد إنشاء الإجابة.")

    item_html = "".join(f"<li>{escape(item)}</li>" for item in items)
    st.markdown(
        f"""
        <section class="insight-card">
            <div class="insight-title">⌾ &nbsp; رؤى التحقق الآلي</div>
            <ul>{item_html}</ul>
        </section>
        """,
        unsafe_allow_html=True,
    )
