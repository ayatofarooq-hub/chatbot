import { createUploadManager } from "./components/upload/useUploadManager.js";
import { createSettingsModule } from "./components/settings/SettingsPage.js";

const storageKey = "iraqi-legal-assistant-conversations";
const decisionDraftKey = "iraqi-legal-assistant-decision-draft";

const elements = {
  assistantNav: document.querySelector("#assistant-nav-button"),
  assistantView: document.querySelector("#assistant-view"),
  capacityRoot: document.querySelector("#file-capacity"),
  chatScroll: document.querySelector("#chat-scroll"),
  clearHistory: document.querySelector("#clear-history"),
  conversationTitle: document.querySelector("#conversation-title"),
  countRoot: document.querySelector("#upload-count"),
  decisionContent: document.querySelector("#decision-content"),
  decisionForm: document.querySelector("#decision-form"),
  decisionMinistry: document.querySelector("#decision-ministry"),
  decisionNav: document.querySelector("#new-decision-button"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionView: document.querySelector("#decision-view"),
  settingsNav: document.querySelector("#settings-nav-button"),
  settingsView: document.querySelector("#settings-view"),
  dropzoneRoot: document.querySelector("#upload-dropzone-root"),
  errorsRoot: document.querySelector("#upload-errors"),
  form: document.querySelector("#question-form"),
  historyList: document.querySelector("#history-list"),
  historySearch: document.querySelector("#history-search"),
  input: document.querySelector("#question-input"),
  insightList: document.querySelector("#insight-list"),
  landingForm: document.querySelector("#landing-form"),
  landingInput: document.querySelector("#landing-input"),
  landingSend: document.querySelector("#landing-send"),
  landingSuggestions: document.querySelector("#landing-suggestions"),
  landingView: document.querySelector("#landing-view"),
  listRoot: document.querySelector("#upload-file-list"),
  messages: document.querySelector("#messages"),
  mobileMenu: document.querySelector("#mobile-menu"),
  microphonePicker: document.querySelector("#microphone-picker"),
  microphoneSelect: document.querySelector("#microphone-select"),
  nav: document.querySelector("#primary-nav"),
  newChatInline: document.querySelector("#new-chat-inline"),
  priorityOptions: document.querySelector("#priority-options"),
  qualityCountRoot: document.querySelector("#upload-quality-count"),
  qualityLabelRoot: document.querySelector("#upload-quality-label"),
  referenceCount: document.querySelector("#reference-count"),
  saveDraft: document.querySelector("#save-draft"),
  sendButton: document.querySelector("#send-button"),
  sourceList: document.querySelector("#source-list"),
  statsRoot: document.querySelector("#upload-stats-root"),
  suggestions: document.querySelector("#suggestions"),
  toast: document.querySelector("#toast"),
  voiceButton: document.querySelector("#voice-button"),
  welcome: document.querySelector("#welcome"),
  wordCount: document.querySelector("#word-count"),
};

let conversations = loadConversations();
let activeConversationId = conversations[0]?.id ?? null;
let mediaRecorder = null;
let microphoneStream = null;
let recordingChunks = [];
let recordingTimer = null;
let recordingStartedAt = 0;
let recordingActive = false;
let pcmContext = null;
let pcmSource = null;
let pcmProcessor = null;
let pcmChunks = [];
const maximumRecordingMs = 60_000;
const minimumRecordingMs = 2_000;
const microphoneStorageKey = "jalssa-selected-microphone";
let pending = false;
let selectedPriority = "عالية";
const initialPromptKey = "iraqi-legal-assistant-initial-prompt";

const uploadManager = createUploadManager({
  dropzoneRoot: elements.dropzoneRoot,
  errorsRoot: elements.errorsRoot,
  listRoot: elements.listRoot,
  statsRoot: elements.statsRoot,
  countRoot: elements.countRoot,
  capacityRoot: elements.capacityRoot,
  qualityCountRoot: elements.qualityCountRoot,
  qualityLabelRoot: elements.qualityLabelRoot,
  showToast,
});

const settingsModule = createSettingsModule({
  root: document.querySelector("#settings-root"),
  modalRoot: document.querySelector("#modal-root"),
  showToast,
});

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
  const showLanding = viewName === "landing";
  const showAssistant = viewName === "assistant";
  const showDecision = viewName === "decision";
  const showSettings = viewName === "settings";
  elements.landingView.hidden = !showLanding;
  elements.assistantView.hidden = !showAssistant;
  elements.decisionView.hidden = !showDecision;
  elements.settingsView.hidden = !showSettings;
  elements.assistantNav.classList.toggle("active", showAssistant || showLanding);
  elements.decisionNav.classList.toggle("active", showDecision);
  elements.settingsNav.classList.toggle("active", showSettings);
  elements.nav.classList.remove("open");
  document.body.classList.toggle("decision-mode", showDecision);
  if (showLanding) {
    elements.landingInput.focus();
  } else if (showAssistant) {
    elements.input.focus();
    consumeInitialPrompt();
  } else if (showDecision) {
    elements.dropzoneRoot.querySelector(".upload-dropzone")?.focus();
  } else if (showSettings) {
    settingsModule.open();
  }
}

function transferPromptToChat(question) {
  const cleanQuestion = normalizeWhitespace(question);
  if (!cleanQuestion || pending) return;
  sessionStorage.setItem(initialPromptKey, cleanQuestion);
  elements.landingInput.value = "";
  elements.landingInput.style.height = "";
  history.replaceState(null, "", "#chat");
  showView("assistant");
}

function consumeInitialPrompt() {
  const fromQuery = new URLSearchParams(window.location.search).get("prompt");
  const stored = sessionStorage.getItem(initialPromptKey);
  const prompt = normalizeWhitespace(stored || fromQuery || "");
  if (!prompt || pending) return;

  sessionStorage.removeItem(initialPromptKey);
  if (fromQuery) {
    const url = new URL(window.location.href);
    url.searchParams.delete("prompt");
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash || "#chat"}`);
  }

  elements.input.value = prompt;
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
  elements.form.requestSubmit();
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
    elements.historyList.append(makeElement("div", "empty-panel", "لا توجد محادثات محفوظة."));
    return;
  }

  filtered.forEach((conversation) => {
    const button = makeElement(
      "button",
      `history-entry${conversation.id === activeConversationId ? " active" : ""}`,
    );
    button.type = "button";
    button.append(
      makeElement("strong", "", truncate(conversation.title, 45)),
      makeElement(
        "span",
        "",
        new Intl.DateTimeFormat("ar-IQ", {
          day: "numeric",
          month: "short",
        }).format(new Date(conversation.createdAt)),
      ),
    );
    button.addEventListener("click", () => selectConversation(conversation.id));
    elements.historyList.append(button);
  });
}

function renderConversation() {
  const conversation = activeConversation();
  elements.messages.replaceChildren();
  elements.conversationTitle.textContent = conversation?.title ?? "محادثة قانونية جديدة";

  const hasMessages = Boolean(conversation?.messages.length);
  elements.welcome.hidden = hasMessages;
  elements.suggestions.hidden = hasMessages;

  if (!conversation) return;

  conversation.messages.forEach((message) => {
    const article = makeElement("article", `message ${message.role}`);
    article.append(makeElement("div", "message-content", message.content));

    if (message.warnings?.length) {
      const warningBox = makeElement("div", "warnings");
      warningBox.append(makeElement("strong", "", "تحذيرات التحقق من الاستشهادات"));
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
            .map((citation) => citation.legal_reference || `${citation.source_file}، الصفحة ${citation.page_number}`)
            .join(" · "),
        ),
      );
      article.append(citations);
    }

    article.append(makeElement("span", "message-meta", message.time || formatTime()));
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
    elements.sourceList.append(makeElement("div", "empty-panel", "ستظهر المراجع المسترجعة هنا بعد طرح السؤال."));
  } else {
    evidence.snippets.slice(0, 3).forEach((snippet) => {
      const card = makeElement("article", "source-card");
      const reference = snippet.legal_reference || snippet.article_reference || `الصفحة ${snippet.page_number ?? "غير معروف"}`;
      card.append(
        makeElement("div", "source-name", snippet.document_title || snippet.source_file || "مصدر غير معروف"),
        makeElement("p", "", truncate(normalizeWhitespace(snippet.text), 135)),
        makeElement("small", "", reference),
      );
      elements.sourceList.append(card);
    });
  }

  elements.insightList.replaceChildren();
  const insights = [];
  if (evidence.citations.length) insights.push(`تم العثور على ${evidence.citations.length} استشهادات.`);
  if (evidence.warnings.length) insights.push(`توجد ${evidence.warnings.length} ملاحظات تحتاج إلى مراجعة.`);
  if (!insights.length) insights.push("ستظهر نتائج التحقق والاستشهادات هنا بعد إنشاء الإجابة.");
  insights.forEach((insight) => elements.insightList.append(makeElement("li", "", insight)));
}

function normalizeWhitespace(value = "") {
  return String(value).replace(/\s+/g, " ").trim();
}

function countWords(value) {
  const normalized = normalizeWhitespace(value);
  return normalized ? normalized.split(" ").length : 0;
}

function updateWordCount() {
  if (!elements.wordCount || !elements.decisionContent) return;
  elements.wordCount.textContent = `عدد الكلمات: ${countWords(elements.decisionContent.value)} كلمة`;
}

function currentDecisionDraft() {
  return {
    ministry: elements.decisionMinistry?.value || "",
    priority: selectedPriority,
    title: elements.decisionTitle?.value || "",
    content: elements.decisionContent?.value || "",
    files: uploadManager.getFiles().map((item) => ({
      name: item.file.name,
      size: item.file.size,
      status: item.status,
    })),
  };
}

function saveDecisionDraft(showConfirmation = true) {
  localStorage.setItem(decisionDraftKey, JSON.stringify(currentDecisionDraft()));
  if (showConfirmation) showToast("تم حفظ مسودة القرار محلياً.");
}

function loadDecisionDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(decisionDraftKey) || "null");
    if (!draft) return;
    if (elements.decisionMinistry) elements.decisionMinistry.value = draft.ministry || elements.decisionMinistry.value;
    if (elements.decisionTitle) elements.decisionTitle.value = draft.title || "";
    if (elements.decisionContent) elements.decisionContent.value = draft.content || "";
    selectedPriority = draft.priority || "عالية";
    elements.priorityOptions?.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("selected", button.dataset.priority === selectedPriority);
    });
    updateWordCount();
  } catch {
    localStorage.removeItem(decisionDraftKey);
  }
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
  if (!conversation.messages.length) conversation.title = truncate(cleanQuestion, 48);
  conversation.messages.push({ role: "user", content: cleanQuestion, time: formatTime() });
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
      body: JSON.stringify({ question: cleanQuestion, include_snippets: true }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "تعذر إنشاء الإجابة.");

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

function supportedAudioType() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function encodeWav(chunks, sampleRate) {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(buffer);
  const writeText = (offset, text) => {
    for (let index = 0; index < text.length; index += 1) {
      view.setUint8(offset + index, text.charCodeAt(index));
    }
  };
  writeText(0, "RIFF");
  view.setUint32(4, 36 + sampleCount * 2, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  chunks.forEach((chunk) => {
    chunk.forEach((sample) => {
      const clamped = Math.max(-1, Math.min(1, sample));
      view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
      offset += 2;
    });
  });
  return new Blob([buffer], { type: "audio/wav" });
}

async function refreshMicrophoneOptions(activeDeviceId = "") {
  const devices = (await navigator.mediaDevices.enumerateDevices())
    .filter((device) => device.kind === "audioinput");
  if (!devices.length) return;

  const savedDeviceId = localStorage.getItem(microphoneStorageKey) || "";
  elements.microphoneSelect.replaceChildren();
  devices.forEach((device, index) => {
    const option = new Option(device.label || `ميكروفون ${index + 1}`, device.deviceId);
    elements.microphoneSelect.add(option);
  });
  const preferredId = savedDeviceId || activeDeviceId;
  if (preferredId && devices.some((device) => device.deviceId === preferredId)) {
    elements.microphoneSelect.value = preferredId;
  }
  elements.microphonePicker.hidden = devices.length < 2;
}

function resetRecorder() {
  window.clearTimeout(recordingTimer);
  recordingTimer = null;
  microphoneStream?.getTracks().forEach((track) => track.stop());
  microphoneStream = null;
  pcmSource?.disconnect();
  pcmProcessor?.disconnect();
  pcmSource = null;
  pcmProcessor = null;
  pcmContext?.close();
  pcmContext = null;
  pcmChunks = [];
  recordingActive = false;
  mediaRecorder = null;
  recordingChunks = [];
  recordingStartedAt = 0;
  elements.voiceButton.classList.remove("recording", "transcribing");
  elements.voiceButton.disabled = false;
  elements.voiceButton.textContent = "●";
  elements.voiceButton.setAttribute("aria-label", "بدء الإدخال الصوتي");
}

async function transcribeRecording(blob) {
  elements.voiceButton.classList.remove("recording");
  elements.voiceButton.classList.add("transcribing");
  elements.voiceButton.disabled = true;
  elements.voiceButton.textContent = "…";
  elements.voiceButton.setAttribute("aria-label", "جارٍ تحويل الصوت إلى نص");

  const formData = new FormData();
  const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "mp4" : "webm";
  formData.append("audio", blob, `recording.${extension}`);

  try {
    const response = await fetch("/transcribe", { method: "POST", body: formData });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "تعذر تحويل الصوت إلى نص.");
    const separator = elements.input.value.trim() ? " " : "";
    elements.input.value = `${elements.input.value.trimEnd()}${separator}${payload.text}`;
    elements.input.dispatchEvent(new Event("input"));
    elements.input.focus();
  } catch (error) {
    showToast(error.message || "تعذر تحويل الصوت إلى نص.");
  } finally {
    resetRecorder();
  }
}

function finishRecording() {
  if (!recordingActive) return;
  recordingActive = false;
  const recordingDuration = Date.now() - recordingStartedAt;
  window.clearTimeout(recordingTimer);

  if (pcmContext) {
    const blob = encodeWav(pcmChunks, pcmContext.sampleRate);
    pcmSource?.disconnect();
    pcmProcessor?.disconnect();
    microphoneStream?.getTracks().forEach((track) => track.stop());
    microphoneStream = null;
    pcmContext.close();
    pcmContext = null;
    pcmSource = null;
    pcmProcessor = null;
    pcmChunks = [];
    if (recordingDuration < minimumRecordingMs) {
      resetRecorder();
      showToast("التسجيل قصير جداً. تحدث لمدة ثانيتين على الأقل.");
      return;
    }
    transcribeRecording(blob);
    return;
  }

  if (mediaRecorder?.state === "recording") mediaRecorder.stop();
}

async function toggleRecording() {
  if (recordingActive) {
    finishRecording();
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    showToast("التسجيل الصوتي غير مدعوم في هذا المتصفح.");
    return;
  }

  try {
    const selectedDeviceId = localStorage.getItem(microphoneStorageKey);
    try {
      microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : true,
      });
    } catch (error) {
      if (!selectedDeviceId || error?.name !== "OverconstrainedError") throw error;
      localStorage.removeItem(microphoneStorageKey);
      microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    const audioTrack = microphoneStream.getAudioTracks()[0];
    if (!audioTrack || audioTrack.readyState !== "live") {
      throw new Error("microphone-unavailable");
    }
    await refreshMicrophoneOptions(audioTrack.getSettings().deviceId || "");

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      pcmContext = new AudioContextClass();
      await pcmContext.resume();
      pcmSource = pcmContext.createMediaStreamSource(microphoneStream);
      pcmProcessor = pcmContext.createScriptProcessor(4096, 1, 1);
      pcmChunks = [];
      pcmProcessor.addEventListener("audioprocess", (event) => {
        if (!recordingActive) return;
        pcmChunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
      });
      pcmSource.connect(pcmProcessor);
      pcmProcessor.connect(pcmContext.destination);
    } else {
      const mimeType = supportedAudioType();
      mediaRecorder = new MediaRecorder(microphoneStream, mimeType ? { mimeType } : undefined);
      recordingChunks = [];
      mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) recordingChunks.push(event.data);
      });
      mediaRecorder.addEventListener("stop", () => {
        const recordingDuration = Date.now() - recordingStartedAt;
        const blob = new Blob(recordingChunks, { type: mediaRecorder.mimeType || "audio/webm" });
        if (recordingDuration < minimumRecordingMs) {
          resetRecorder();
          showToast("التسجيل قصير جداً. تحدث لمدة ثانيتين على الأقل.");
          return;
        }
        transcribeRecording(blob);
      }, { once: true });
      mediaRecorder.start(250);
    }
    recordingStartedAt = Date.now();
    recordingActive = true;
    elements.voiceButton.classList.add("recording");
    elements.voiceButton.textContent = "■";
    elements.voiceButton.setAttribute("aria-label", "إيقاف التسجيل");
    showToast("بدأ التسجيل. اضغط على المربع الأحمر عند الانتهاء.");
    recordingTimer = window.setTimeout(() => {
      if (recordingActive) finishRecording();
    }, maximumRecordingMs);
  } catch (error) {
    console.error("Microphone startup failed:", error);
    resetRecorder();
    if (error?.name === "NotAllowedError") {
      showToast("تم رفض إذن الميكروفون من المتصفح.");
    } else if (error?.name === "NotReadableError") {
      showToast("الميكروفون مستخدم من تطبيق آخر أو غير متاح للنظام.");
    } else if (error?.name === "OverconstrainedError") {
      showToast("الميكروفون لا يدعم إعدادات التسجيل المطلوبة.");
    } else {
      showToast(`تعذر تشغيل الميكروفون: ${error?.message || "خطأ غير معروف"}`);
    }
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = elements.input.value;
  elements.input.value = "";
  elements.input.style.height = "";
  submitQuestion(question);
});

elements.voiceButton?.addEventListener("click", toggleRecording);
elements.microphoneSelect?.addEventListener("change", () => {
  localStorage.setItem(microphoneStorageKey, elements.microphoneSelect.value);
  showToast("تم اختيار الميكروفون. ابدأ تسجيلاً جديداً.");
});

elements.landingForm.addEventListener("submit", (event) => {
  event.preventDefault();
  transferPromptToChat(elements.landingInput.value);
});

elements.landingInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.landingForm.requestSubmit();
  }
});

elements.landingInput.addEventListener("input", () => {
  elements.landingInput.style.height = "auto";
  elements.landingInput.style.height = `${Math.min(elements.landingInput.scrollHeight, 150)}px`;
});

elements.landingSuggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) transferPromptToChat(button.textContent);
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

elements.assistantNav.addEventListener("click", () => {
  history.replaceState(null, "", window.location.pathname);
  showView("landing");
});
elements.decisionNav.addEventListener("click", () => showView("decision"));
elements.settingsNav.addEventListener("click", () => showView("settings"));
elements.newChatInline.addEventListener("click", createConversation);
elements.clearHistory.addEventListener("click", removeAllConversations);
elements.historySearch.addEventListener("input", renderHistory);
elements.mobileMenu.addEventListener("click", () => elements.nav.classList.toggle("open"));

elements.priorityOptions?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-priority]");
  if (!button) return;
  selectedPriority = button.dataset.priority;
  elements.priorityOptions.querySelectorAll("button").forEach((option) => {
    option.classList.toggle("selected", option === button);
  });
});

elements.decisionContent?.addEventListener("input", updateWordCount);
elements.saveDraft?.addEventListener("click", () => saveDecisionDraft());

elements.decisionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (elements.decisionTitle && elements.decisionContent && (!elements.decisionTitle.value.trim() || !elements.decisionContent.value.trim())) {
    showToast("يرجى إدخال عنوان القرار ونصه الكامل.");
    return;
  }
  saveDecisionDraft(false);
  showToast("واجهة رفع القرار جاهزة. لم يتم إرسال بيانات إلى الخادم.");
});

loadDecisionDraft();
render();
if (window.location.hash === "#chat" || new URLSearchParams(window.location.search).has("prompt")) {
  showView("assistant");
} else {
  showView("landing");
}
