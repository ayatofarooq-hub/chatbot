const storageKey = "iraqi-legal-assistant-conversations";
const decisionDraftKey = "iraqi-legal-assistant-decision-draft";

const elements = {
  assistantNav: document.querySelector("#assistant-nav-button"),
  assistantView: document.querySelector("#assistant-view"),
  chatScroll: document.querySelector("#chat-scroll"),
  clearHistory: document.querySelector("#clear-history"),
  conversationTitle: document.querySelector("#conversation-title"),
  decisionContent: document.querySelector("#decision-content"),
  decisionDropzone: document.querySelector("#decision-dropzone"),
  decisionFile: document.querySelector("#decision-file"),
  decisionForm: document.querySelector("#decision-form"),
  decisionMinistry: document.querySelector("#decision-ministry"),
  decisionNav: document.querySelector("#new-decision-button"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionView: document.querySelector("#decision-view"),
  form: document.querySelector("#question-form"),
  historyList: document.querySelector("#history-list"),
  historySearch: document.querySelector("#history-search"),
  input: document.querySelector("#question-input"),
  insightList: document.querySelector("#insight-list"),
  messages: document.querySelector("#messages"),
  mobileMenu: document.querySelector("#mobile-menu"),
  nav: document.querySelector("#primary-nav"),
  newChatInline: document.querySelector("#new-chat-inline"),
  priorityOptions: document.querySelector("#priority-options"),
  referenceCount: document.querySelector("#reference-count"),
  removeFile: document.querySelector("#remove-file"),
  saveDraft: document.querySelector("#save-draft"),
  sendButton: document.querySelector("#send-button"),
  sourceList: document.querySelector("#source-list"),
  suggestions: document.querySelector("#suggestions"),
  toast: document.querySelector("#toast"),
  uploadedFile: document.querySelector("#uploaded-file"),
  uploadedFileMeta: document.querySelector("#uploaded-file-meta"),
  uploadedFileName: document.querySelector("#uploaded-file-name"),
  welcome: document.querySelector("#welcome"),
  wordCount: document.querySelector("#word-count"),
};

let conversations = loadConversations();
let activeConversationId = conversations[0]?.id ?? null;
let pending = false;
let selectedPriority = "عالية";

function loadConversations() {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || "[]");
    return Array.isArray(stored) ? stored : [];
  } catch {
    return [];
  }
}

function saveConversations() {
  localStorage.setItem(storageKey, JSON.stringify(conversations));
}

function createConversation() {
  const conversation = {
    id: crypto.randomUUID(),
    title: "محادثة قانونية جديدة",
    createdAt: new Date().toISOString(),
    messages: [],
    evidence: { snippets: [], warnings: [], citations: [] },
  };
  conversations.unshift(conversation);
  activeConversationId = conversation.id;
  saveConversations();
  render();
  elements.input.focus();
  return conversation;
}

function showView(viewName) {
  const showAssistant = viewName === "assistant";
  elements.assistantView.hidden = !showAssistant;
  elements.decisionView.hidden = showAssistant;
  elements.assistantNav.classList.toggle("active", showAssistant);
  elements.decisionNav.classList.toggle("active", !showAssistant);
  elements.nav.classList.remove("open");
  document.body.classList.toggle("decision-mode", !showAssistant);
  if (showAssistant) {
    elements.input.focus();
  } else {
    elements.decisionTitle.focus();
  }
}

function activeConversation() {
  return conversations.find(({ id }) => id === activeConversationId) ?? null;
}

function selectConversation(id) {
  activeConversationId = id;
  render();
  elements.nav.classList.remove("open");
}

function removeAllConversations() {
  conversations = [];
  activeConversationId = null;
  saveConversations();
  render();
}

function truncate(value, length) {
  return value.length <= length ? value : `${value.slice(0, length - 3)}...`;
}

function formatTime(date = new Date()) {
  return new Intl.DateTimeFormat("ar-IQ", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function makeElement(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render() {
  renderHistory();
  renderConversation();
  renderEvidence();
}

function renderHistory() {
  const searchTerm = elements.historySearch.value.trim().toLowerCase();
  elements.historyList.replaceChildren();
  const filtered = conversations.filter(({ title }) =>
    title.toLowerCase().includes(searchTerm),
  );

  if (!filtered.length) {
    elements.historyList.append(
      makeElement("div", "empty-panel", "لا توجد محادثات محفوظة."),
    );
    return;
  }

  filtered.forEach((conversation) => {
    const button = makeElement(
      "button",
      `history-entry${conversation.id === activeConversationId ? " active" : ""}`,
    );
    button.type = "button";
    const title = makeElement("strong", "", truncate(conversation.title, 45));
    const date = makeElement(
      "span",
      "",
      new Intl.DateTimeFormat("ar-IQ", {
        day: "numeric",
        month: "short",
      }).format(new Date(conversation.createdAt)),
    );
    button.append(title, date);
    button.addEventListener("click", () => selectConversation(conversation.id));
    elements.historyList.append(button);
  });
}

function renderConversation() {
  const conversation = activeConversation();
  elements.messages.replaceChildren();
  elements.conversationTitle.textContent =
    conversation?.title ?? "محادثة قانونية جديدة";

  const hasMessages = Boolean(conversation?.messages.length);
  elements.welcome.hidden = hasMessages;
  elements.suggestions.hidden = hasMessages;

  if (!conversation) return;

  conversation.messages.forEach((message) => {
    const article = makeElement("article", `message ${message.role}`);
    const content = makeElement("div", "message-content", message.content);
    article.append(content);

    if (message.warnings?.length) {
      const warningBox = makeElement("div", "warnings");
      warningBox.append(
        makeElement("strong", "", "تحذيرات التحقق من الاستشهادات"),
      );
      const list = document.createElement("ul");
      message.warnings.forEach((warning) => {
        list.append(makeElement("li", "", warning));
      });
      warningBox.append(list);
      article.append(warningBox);
    }

    if (message.citations?.length) {
      const citations = makeElement("div", "citations");
      citations.append(makeElement("strong", "", "المصادر: "));
      citations.append(
        document.createTextNode(
          message.citations
            .map(
              ({ source_file, page_number }) =>
                `${source_file}، الصفحة ${page_number}`,
            )
            .join(" · "),
        ),
      );
      article.append(citations);
    }

    article.append(
      makeElement("span", "message-meta", message.time || formatTime()),
    );
    elements.messages.append(article);
  });

  requestAnimationFrame(() => {
    elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
  });
}

function renderEvidence() {
  const evidence = activeConversation()?.evidence ?? {
    snippets: [],
    warnings: [],
    citations: [],
  };

  elements.referenceCount.textContent = `${evidence.snippets.length} مراجع`;
  elements.sourceList.replaceChildren();

  if (!evidence.snippets.length) {
    elements.sourceList.append(
      makeElement(
        "div",
        "empty-panel",
        "ستظهر المراجع المسترجعة هنا بعد طرح السؤال.",
      ),
    );
  } else {
    evidence.snippets.slice(0, 3).forEach((snippet) => {
      const card = makeElement("article", "source-card");
      card.append(
        makeElement(
          "div",
          "source-name",
          snippet.source_file || "مصدر غير معروف",
        ),
        makeElement("p", "", truncate(normalizeWhitespace(snippet.text), 135)),
        makeElement(
          "small",
          "",
          `الصفحة ${snippet.page_number ?? "غير معروف"}`,
        ),
      );
      elements.sourceList.append(card);
    });
  }

  elements.insightList.replaceChildren();
  const insights = [];
  if (evidence.citations.length) {
    insights.push(`تم العثور على ${evidence.citations.length} استشهادات.`);
  }
  if (evidence.warnings.length) {
    insights.push(`توجد ${evidence.warnings.length} ملاحظات تحتاج إلى مراجعة.`);
  }
  if (!insights.length) {
    insights.push("ستظهر نتائج التحقق والاستشهادات هنا بعد إنشاء الإجابة.");
  }
  insights.forEach((insight) => {
    elements.insightList.append(makeElement("li", "", insight));
  });
}

function normalizeWhitespace(value = "") {
  return String(value).replace(/\s+/g, " ").trim();
}

function countWords(value) {
  const normalized = normalizeWhitespace(value);
  return normalized ? normalized.split(" ").length : 0;
}

function updateWordCount() {
  elements.wordCount.textContent =
    `عدد الكلمات: ${countWords(elements.decisionContent.value)} كلمة`;
}

function currentDecisionDraft() {
  return {
    ministry: elements.decisionMinistry.value,
    priority: selectedPriority,
    title: elements.decisionTitle.value,
    content: elements.decisionContent.value,
  };
}

function saveDecisionDraft(showConfirmation = true) {
  localStorage.setItem(decisionDraftKey, JSON.stringify(currentDecisionDraft()));
  if (showConfirmation) {
    showToast("تم حفظ مسودة القرار محلياً.");
  }
}

function loadDecisionDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(decisionDraftKey) || "null");
    if (!draft) return;
    elements.decisionMinistry.value = draft.ministry || elements.decisionMinistry.value;
    elements.decisionTitle.value = draft.title || "";
    elements.decisionContent.value = draft.content || "";
    selectedPriority = draft.priority || "عالية";
    elements.priorityOptions.querySelectorAll("button").forEach((button) => {
      button.classList.toggle(
        "selected",
        button.dataset.priority === selectedPriority,
      );
    });
    updateWordCount();
  } catch {
    localStorage.removeItem(decisionDraftKey);
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} كيلوبايت`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} ميغابايت`;
}

function displayAttachment(file) {
  if (!file) return;
  elements.uploadedFileName.textContent = file.name;
  elements.uploadedFileMeta.textContent =
    `${formatFileSize(file.size)} · جاهز للمراجعة`;
  elements.uploadedFile.classList.remove("hidden");
}

function setPending(value) {
  pending = value;
  elements.sendButton.disabled = value;
  elements.input.disabled = value;
  elements.sendButton.textContent = value ? "…" : "←";
}

async function submitQuestion(question) {
  if (pending || !question.trim()) return;
  let conversation = activeConversation();
  if (!conversation) conversation = createConversation();

  const cleanQuestion = question.trim();
  if (!conversation.messages.length) {
    conversation.title = truncate(cleanQuestion, 48);
  }
  conversation.messages.push({
    role: "user",
    content: cleanQuestion,
    time: formatTime(),
  });
  saveConversations();
  render();
  setPending(true);

  const loading = makeElement("article", "message assistant", "جارٍ البحث وإعداد الإجابة...");
  loading.id = "loading-message";
  elements.messages.append(loading);
  elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: cleanQuestion,
        include_snippets: true,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "تعذر إنشاء الإجابة.");
    }

    conversation.messages.push({
      role: "assistant",
      content: payload.answer,
      warnings: payload.warnings || [],
      citations: payload.citations || [],
      time: formatTime(),
    });
    conversation.evidence = {
      snippets: payload.snippets || [],
      warnings: payload.warnings || [],
      citations: payload.citations || [],
    };
    saveConversations();
  } catch (error) {
    conversation.messages.push({
      role: "assistant error",
      content: error.message || "تعذر الاتصال بالخادم.",
      time: formatTime(),
    });
    showToast(error.message || "تعذر الاتصال بالخادم.");
  } finally {
    document.querySelector("#loading-message")?.remove();
    setPending(false);
    render();
    elements.input.focus();
  }
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  window.setTimeout(() => elements.toast.classList.remove("visible"), 3500);
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = elements.input.value;
  elements.input.value = "";
  elements.input.style.height = "";
  submitQuestion(question);
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.input.addEventListener("input", () => {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
});

elements.suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) submitQuestion(button.textContent);
});

elements.assistantNav.addEventListener("click", () => showView("assistant"));
elements.decisionNav.addEventListener("click", () => showView("decision"));
elements.newChatInline.addEventListener("click", createConversation);
elements.clearHistory.addEventListener("click", removeAllConversations);
elements.historySearch.addEventListener("input", renderHistory);
elements.mobileMenu.addEventListener("click", () =>
  elements.nav.classList.toggle("open"),
);

elements.priorityOptions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-priority]");
  if (!button) return;
  selectedPriority = button.dataset.priority;
  elements.priorityOptions.querySelectorAll("button").forEach((option) => {
    option.classList.toggle("selected", option === button);
  });
});

elements.decisionContent.addEventListener("input", updateWordCount);
elements.saveDraft.addEventListener("click", () => saveDecisionDraft());

elements.decisionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (
    !elements.decisionTitle.value.trim() ||
    !elements.decisionContent.value.trim()
  ) {
    showToast("يرجى إدخال عنوان القرار ونصه الكامل.");
    return;
  }
  saveDecisionDraft(false);
  showToast("واجهة رفع القرار جاهزة. لم يتم إرسال بيانات إلى الخادم.");
});

elements.decisionFile.addEventListener("change", () => {
  displayAttachment(elements.decisionFile.files[0]);
});

elements.decisionDropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  elements.decisionDropzone.classList.add("dragging");
});

elements.decisionDropzone.addEventListener("dragleave", () => {
  elements.decisionDropzone.classList.remove("dragging");
});

elements.decisionDropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  elements.decisionDropzone.classList.remove("dragging");
  displayAttachment(event.dataTransfer.files[0]);
});

elements.removeFile.addEventListener("click", () => {
  elements.decisionFile.value = "";
  elements.uploadedFile.classList.add("hidden");
});

loadDecisionDraft();
render();
