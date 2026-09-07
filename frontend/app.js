import { createUploadManager } from "./components/upload/useUploadManager.js?v=20260712-upload-settings";
import { createSettingsModule } from "./components/settings/SettingsPage.js?v=20260712-upload-settings";

const storageKey = "iraqi-legal-assistant-conversations";
const storageBackupKey = "iraqi-legal-assistant-conversations-backup";
const activeConversationStorageKey = "iraqi-legal-assistant-active-conversation";
const chatHistoryEndpoint = "/api/chat-history";
const decisionDraftKey = "iraqi-legal-assistant-decision-draft";

const elements = {
  aiCharacter: document.querySelector("#ai-character"),
  aiCharacterStatus: document.querySelector("#ai-character-status"),
  aiVoiceToggle: document.querySelector("#ai-voice-toggle"),
  aiSpeechStop: document.querySelector("#ai-speech-stop"),
  aiSpeechReplay: document.querySelector("#ai-speech-replay"),
  aiAudioSettings: document.querySelector("#ai-audio-settings"),
  aiCharacterSliders: document.querySelector("#ai-character-sliders"),
  aiMotionToggle: document.querySelector("#ai-motion-toggle"),
  aiSpeechRate: document.querySelector("#ai-speech-rate"),
  aiSpeechVolume: document.querySelector("#ai-speech-volume"),
  aiSpeechRateValue: document.querySelector("#ai-speech-rate-value"),
  aiSpeechVolumeValue: document.querySelector("#ai-speech-volume-value"),
  assistantNav: document.querySelector("#assistant-nav-button"),
  assistantView: document.querySelector("#assistant-view"),
  capacityRoot: document.querySelector("#file-capacity"),
  chatSidebar: document.querySelector("#chat-history-sidebar"),
  chatSidebarBackdrop: document.querySelector("#chat-sidebar-backdrop"),
  chatSidebarClose: document.querySelector("#chat-sidebar-close"),
  chatScroll: document.querySelector("#chat-scroll"),
  clearHistory: document.querySelector("#clear-history"),
  conversationTitle: document.querySelector("#conversation-title"),
  countRoot: document.querySelector("#upload-count"),
  currentFilesSubtitle: document.querySelector("#current-files-subtitle"),
  decisionContent: document.querySelector("#decision-content"),
  decisionForm: document.querySelector("#decision-form"),
  decisionMinistry: document.querySelector("#decision-ministry"),
  decisionNav: document.querySelector("#new-decision-button"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionView: document.querySelector("#decision-view"),
  reviewNav: document.querySelector("#review-nav-button"),
  reviewView: document.querySelector("#review-view"),
  reviewList: document.querySelector("#review-list"),
  reviewDetail: document.querySelector("#review-detail"),
  settingsNav: document.querySelector("#settings-nav-button"),
  settingsView: document.querySelector("#settings-view"),
  dropzoneRoot: document.querySelector("#upload-dropzone-root"),
  errorsRoot: document.querySelector("#upload-errors"),
  exportButton: document.querySelector("#export-button"),
  exportDropdown: document.querySelector("#export-dropdown"),
  form: document.querySelector("#question-form"),
  historyList: document.querySelector("#history-list"),
  historySearch: document.querySelector("#history-search"),
  input: document.querySelector("#question-input"),
  insightList: document.querySelector("#insight-list"),
  landingForm: document.querySelector("#landing-form"),
  landingInput: document.querySelector("#landing-input"),
  landingRecordingControls: document.querySelector("#landing-recording-controls"),
  landingSend: document.querySelector("#landing-send"),
  landingSuggestions: document.querySelector("#landing-suggestions"),
  landingWelcomeSubtitle: document.querySelector("#landing-welcome-subtitle"),
  landingWelcomeTitle: document.querySelector("#landing-welcome-title"),
  landingVoiceButton: document.querySelector("#landing-voice-button"),
  landingView: document.querySelector("#landing-view"),
  listRoot: document.querySelector("#upload-file-list"),
  logoutButton: document.querySelector("#logout-button"),
  messages: document.querySelector("#messages"),
  mobileMenu: document.querySelector("#mobile-menu"),
  microphonePicker: document.querySelector("#microphone-picker"),
  microphoneSelect: document.querySelector("#microphone-select"),
  nav: document.querySelector("#primary-nav"),
  newChatInline: document.querySelector("#new-chat-inline"),
  priorityOptions: document.querySelector("#priority-options"),
  profileAvatar: document.querySelector("#profile-avatar"),
  profileName: document.querySelector("#profile-name"),
  profileRole: document.querySelector("#profile-role"),
  qualityCountRoot: document.querySelector("#upload-quality-count"),
  qualityLabelRoot: document.querySelector("#upload-quality-label"),
  referenceCount: document.querySelector("#reference-count"),
  saveDraft: document.querySelector("#save-draft"),
  sendButton: document.querySelector("#send-button"),
  sidebarProfileAvatar: document.querySelector("#sidebar-profile-avatar"),
  sidebarProfileName: document.querySelector("#sidebar-profile-name"),
  sidebarProfileRole: document.querySelector("#sidebar-profile-role"),
  sourceList: document.querySelector("#source-list"),
  statsRoot: document.querySelector("#upload-stats-root"),
  suggestions: document.querySelector("#suggestions"),
  toast: document.querySelector("#toast"),
  voiceButton: document.querySelector("#voice-button"),
  welcome: document.querySelector("#welcome"),
  welcomeSubtitle: document.querySelector("#welcome-subtitle"),
  welcomeTitle: document.querySelector("#welcome-title"),
  wordCount: document.querySelector("#word-count"),
};
const landingVoiceIconMarkup = elements.landingVoiceButton?.innerHTML || "";
const voiceIconMarkup = elements.voiceButton?.innerHTML || "";
const stopRecordingIconMarkup = `
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <rect x="7.5" y="7.5" width="9" height="9" rx="1.5" fill="currentColor" stroke="none"></rect>
  </svg>
`;

let conversations = loadConversations();
let activeConversationId = loadActiveConversationId(conversations);
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
let recordingButton = elements.voiceButton;
let recordingInput = elements.input;
let discardRecording = false;
let landingVoiceLevel = 0;
const maximumRecordingMs = 60_000;
const minimumRecordingMs = 2_000;
const microphoneStorageKey = "jalssa-selected-microphone";
const aiVoiceStorageKey = "jalssa-ai-arabic-voice-enabled";
let pending = false;
let aiVoiceEnabled = localStorage.getItem(aiVoiceStorageKey) !== "false";
let aiSpeechSequence = 0;
let aiSpeechActive = false;
let aiSpeechAudio = null;
let aiSpeechObjectUrl = null;
let aiSpeechAbortController = null;
let localTtsAvailable = null;
let aiSpeechRate = Number(localStorage.getItem("jalssa-ai-speech-rate")) || 1;
let aiSpeechVolume = Number(localStorage.getItem("jalssa-ai-speech-volume"));
if (!Number.isFinite(aiSpeechVolume)) aiSpeechVolume = 1;
let aiMotionEnabled = localStorage.getItem("jalssa-avatar-motion") !== "false";
let lastSpokenAnswer = "";
let selectedPriority = "Ø¹Ø§Ù„ÙŠØ©";
const initialPromptKey = "iraqi-legal-assistant-initial-prompt";

const cp1252Bytes = new Map([
  ["€", 0x80], ["‚", 0x82], ["ƒ", 0x83], ["„", 0x84], ["…", 0x85],
  ["†", 0x86], ["‡", 0x87], ["ˆ", 0x88], ["‰", 0x89], ["Š", 0x8a],
  ["‹", 0x8b], ["Œ", 0x8c], ["Ž", 0x8e], ["‘", 0x91], ["’", 0x92],
  ["“", 0x93], ["”", 0x94], ["•", 0x95], ["–", 0x96], ["—", 0x97],
  ["˜", 0x98], ["™", 0x99], ["š", 0x9a], ["›", 0x9b], ["œ", 0x9c],
  ["ž", 0x9e], ["Ÿ", 0x9f],
]);
const mojibakePattern = /(?:Ø|Ù|Û|Ã|Â|â€|â€¦|â†|â‡|ï¼|ðŸ|�)/;

function repairMojibake(value) {
  if (typeof value !== "string" || !mojibakePattern.test(value)) return value;
  const bytes = [];
  for (const character of value) {
    const code = character.charCodeAt(0);
    if (code <= 0xff) {
      bytes.push(code);
    } else if (cp1252Bytes.has(character)) {
      bytes.push(cp1252Bytes.get(character));
    } else {
      return value;
    }
  }
  try {
    const repaired = new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array(bytes));
    return repaired.includes("�") ? value : repaired;
  } catch {
    return value;
  }
}

function repairTextTree(root = document.body) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    node.nodeValue = repairMojibake(node.nodeValue);
  });
  root.querySelectorAll?.("[aria-label], [title], [placeholder]").forEach((node) => {
    ["aria-label", "title", "placeholder"].forEach((attribute) => {
      if (node.hasAttribute(attribute)) {
        node.setAttribute(attribute, repairMojibake(node.getAttribute(attribute)));
      }
    });
  });
}

const aiCharacterLabels = {
  idle: "جاهز للمساعدة",
  greeting: "أهلاً بك",
  listening: "أستمع إليك",
  thinking: "أراجع المصادر القانونية",
  talking: "أشرح الإجابة الآن",
  success: "اكتملت الإجابة",
  error: "تعذر إكمال الطلب",
};

function setAiCharacterState(state = "idle", label = "") {
  if (!elements.aiCharacter) return;
  elements.aiCharacter.dataset.state = state;
  if (elements.aiCharacterStatus) {
    elements.aiCharacterStatus.textContent = label || aiCharacterLabels[state] || aiCharacterLabels.idle;
  }
}

function speechChunks(value, maximumLength = 230) {
  const cleaned = normalizeWhitespace(repairMojibake(value))
    .replace(/https?:\/\/\S+/giu, " ")
    .replace(/\[[^\]]*\]/gu, " ")
    .replace(/[*_`#>]+/gu, " ");
  const sentences = cleaned.match(/[^.!؟؛]+[.!؟؛]?/gu) || [cleaned];
  const chunks = [];
  let current = "";
  sentences.forEach((sentence) => {
    const next = `${current} ${sentence}`.trim();
    if (next.length <= maximumLength) {
      current = next;
      return;
    }
    if (current) chunks.push(current);
    current = sentence.trim();
  });
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

function updateAiVoiceButton() {
  if (!elements.aiVoiceToggle) return;
  elements.aiVoiceToggle.setAttribute("aria-pressed", String(aiVoiceEnabled));
  const label = aiVoiceEnabled ? "إيقاف صوت المساعد" : "تشغيل صوت المساعد";
  elements.aiVoiceToggle.setAttribute("aria-label", label);
  elements.aiVoiceToggle.title = label;
}

function stopAiSpeech({ resumeRotation = true } = {}) {
  aiSpeechSequence += 1;
  aiSpeechActive = false;
  aiSpeechAbortController?.abort();
  aiSpeechAbortController = null;
  window.dispatchEvent(new CustomEvent("avatar:speech-stop"));
  if (aiSpeechAudio) {
    aiSpeechAudio.pause();
    aiSpeechAudio.removeAttribute("src");
    aiSpeechAudio.load();
    aiSpeechAudio = null;
  }
  if (aiSpeechObjectUrl) {
    URL.revokeObjectURL(aiSpeechObjectUrl);
    aiSpeechObjectUrl = null;
  }
  if (resumeRotation) {
    setAiCharacterState("idle", aiVoiceEnabled ? "جاهز للمساعدة" : "الصوت متوقف");
  }
}

async function playLocalSpeechChunk(text, sequence) {
  aiSpeechAbortController = new AbortController();
  const response = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language: "ar", rate: aiSpeechRate }),
    signal: aiSpeechAbortController.signal,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Local TTS failed (${response.status}).`);
  }
  const blob = await response.blob();
  if (sequence !== aiSpeechSequence || !aiVoiceEnabled) return;
  aiSpeechObjectUrl = URL.createObjectURL(blob);
  const audio = new Audio(aiSpeechObjectUrl);
  audio.volume = aiSpeechVolume;
  aiSpeechAudio = audio;
  try {
    await new Promise((resolve, reject) => {
      audio.onended = resolve;
      audio.onerror = () => reject(new Error("The browser could not play local speech."));
      audio.play().then(() => {
        window.dispatchEvent(new CustomEvent("avatar:volume", { detail: { volume: aiSpeechVolume } }));
        window.dispatchEvent(new CustomEvent("avatar:speech-start", { detail: { audio } }));
      }).catch(reject);
    });
  } finally {
    window.dispatchEvent(new CustomEvent("avatar:speech-stop"));
    if (aiSpeechAudio === audio) aiSpeechAudio = null;
    if (aiSpeechObjectUrl) {
      URL.revokeObjectURL(aiSpeechObjectUrl);
      aiSpeechObjectUrl = null;
    }
  }
}

function speakArabicAnswer(value) {
  if (!aiVoiceEnabled || !localTtsAvailable) {
    return;
  }
  lastSpokenAnswer = value;
  const chunks = speechChunks(value);
  if (!chunks.length) return;

  stopAiSpeech({ resumeRotation: false });
  const sequence = aiSpeechSequence;
  aiSpeechActive = true;
  setAiCharacterState("talking");

  const speakNext = async () => {
    if (sequence !== aiSpeechSequence || !aiVoiceEnabled) return;
    const text = chunks.shift();
    if (!text) {
      aiSpeechActive = false;
      setAiCharacterState("idle");
      return;
    }
    try {
      await playLocalSpeechChunk(text, sequence);
      if (sequence === aiSpeechSequence) speakNext();
    } catch (_error) {
      if (_error?.name === "AbortError") return;
      localTtsAvailable = false;
      if (sequence !== aiSpeechSequence) return;
      aiSpeechActive = false;
      setAiCharacterState("error", "تعذر تشغيل الصوت المحلي");
    }
  };
  speakNext();
}

async function initializeAiCharacter() {
  if (!elements.aiCharacter) return;
  if (elements.aiSpeechRate) elements.aiSpeechRate.value = String(aiSpeechRate);
  if (elements.aiSpeechVolume) elements.aiSpeechVolume.value = String(aiSpeechVolume);
  if (elements.aiSpeechRateValue) elements.aiSpeechRateValue.value = `${aiSpeechRate.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}×`;
  if (elements.aiSpeechVolumeValue) elements.aiSpeechVolumeValue.value = `${Math.round(aiSpeechVolume * 100)}%`;
  elements.aiMotionToggle?.setAttribute("aria-pressed", String(aiMotionEnabled));
  try {
    const response = await fetch("/api/tts/status");
    const status = response.ok ? await response.json() : {};
    localTtsAvailable = Boolean(status.available);
  } catch (_error) {
    localTtsAvailable = false;
  }
  if (!localTtsAvailable) {
    aiVoiceEnabled = false;
    elements.aiVoiceToggle.disabled = true;
    setAiCharacterState("idle", "الصوت غير متاح");
  }
  updateAiVoiceButton();
  elements.aiVoiceToggle?.addEventListener("click", () => {
    aiVoiceEnabled = !aiVoiceEnabled;
    localStorage.setItem(aiVoiceStorageKey, String(aiVoiceEnabled));
    updateAiVoiceButton();
    if (!aiVoiceEnabled) {
      stopAiSpeech();
      return;
    }
    setAiCharacterState("greeting", "تم تشغيل الصوت العربي");
    speakArabicAnswer("تم تشغيل صوت المساعد العربي.");
  });
  elements.aiSpeechStop?.addEventListener("click", () => stopAiSpeech());
  elements.aiSpeechReplay?.addEventListener("click", () => {
    if (lastSpokenAnswer) speakArabicAnswer(lastSpokenAnswer);
  });
  elements.aiAudioSettings?.addEventListener("click", () => {
    const opening = elements.aiCharacterSliders?.hidden ?? true;
    if (elements.aiCharacterSliders) elements.aiCharacterSliders.hidden = !opening;
    elements.aiAudioSettings.setAttribute("aria-expanded", String(opening));
  });
  elements.aiSpeechRate?.addEventListener("input", () => {
    aiSpeechRate = Number(elements.aiSpeechRate.value) || 1;
    localStorage.setItem("jalssa-ai-speech-rate", String(aiSpeechRate));
    if (elements.aiSpeechRateValue) elements.aiSpeechRateValue.value = `${aiSpeechRate.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}×`;
  });
  elements.aiSpeechVolume?.addEventListener("input", () => {
    aiSpeechVolume = Number(elements.aiSpeechVolume.value);
    localStorage.setItem("jalssa-ai-speech-volume", String(aiSpeechVolume));
    if (elements.aiSpeechVolumeValue) elements.aiSpeechVolumeValue.value = `${Math.round(aiSpeechVolume * 100)}%`;
    if (aiSpeechAudio) aiSpeechAudio.volume = aiSpeechVolume;
    window.dispatchEvent(new CustomEvent("avatar:volume", { detail: { volume: aiSpeechVolume } }));
  });
  elements.aiMotionToggle?.addEventListener("click", () => {
    aiMotionEnabled = !aiMotionEnabled;
    localStorage.setItem("jalssa-avatar-motion", String(aiMotionEnabled));
    elements.aiMotionToggle.setAttribute("aria-pressed", String(aiMotionEnabled));
    window.dispatchEvent(new CustomEvent("avatar:motion", { detail: { enabled: aiMotionEnabled } }));
  });
}

function repairConversationText(message) {
  if (!message || typeof message !== "object") return message;
  if (Array.isArray(message)) return message.map(repairConversationText);
  return Object.fromEntries(
    Object.entries(message).map(([key, value]) => {
      if (typeof value === "string") return [key, repairMojibake(value)];
      if (value && typeof value === "object") return [key, repairConversationText(value)];
      return [key, value];
    }),
  );
}

const uploadManager = createUploadManager({
  dropzoneRoot: elements.dropzoneRoot,
  errorsRoot: elements.errorsRoot,
  listRoot: elements.listRoot,
  statsRoot: elements.statsRoot,
  countRoot: elements.countRoot,
  capacityRoot: elements.capacityRoot,
  subtitleRoot: elements.currentFilesSubtitle,
  qualityCountRoot: elements.qualityCountRoot,
  qualityLabelRoot: elements.qualityLabelRoot,
  showToast,
});

const settingsModule = createSettingsModule({
  root: document.querySelector("#settings-root"),
  modalRoot: document.querySelector("#modal-root"),
  showToast,
  onAuthenticated: refreshSession,
});

const roleNames = {
  super_admin: "Ù…Ø¯ÙŠØ± Ø¹Ø§Ù…",
  admin: "Ù…Ø¯ÙŠØ± Ø§Ù„Ù†Ø¸Ø§Ù…",
  viewer: "Ù…Ø±Ø§Ø¬Ø¹",
};

let reviewItems = [];
let activeReviewId = null;

function applyWelcomePhrase(welcomePhrase) {
  const phrase = repairMojibake(welcomePhrase?.phrase || "");
  const ministry = repairMojibake(welcomePhrase?.ministry || "");
  if (!phrase) return;
  if (elements.welcomeTitle) elements.welcomeTitle.textContent = phrase;
  if (elements.landingWelcomeTitle) elements.landingWelcomeTitle.textContent = phrase;
  if (ministry) {
    if (elements.welcomeSubtitle) elements.welcomeSubtitle.textContent = ministry;
    if (elements.landingWelcomeSubtitle) elements.landingWelcomeSubtitle.textContent = ministry;
  }
}

async function refreshSession() {
  try {
    const response = await fetch("/api/auth/session", { credentials: "same-origin" });
    const payload = await response.json();
    const administrator = payload.authenticated ? payload.administrator : null;
    const loginRequired = payload.login_required !== false;
    const displayName = administrator?.display_name || administrator?.username || "ØºÙŠØ± Ù…Ø³Ø¬Ù„";
    const displayRole = administrator
      ? (roleNames[administrator.role] || administrator.role)
      : "ÙŠÙ„Ø²Ù… ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„";
    const displayAvatar = administrator
      ? displayName.trim().charAt(0).toLocaleUpperCase("ar")
      : "ØŸ";
    if (elements.profileName) elements.profileName.textContent = repairMojibake(displayName);
    if (elements.profileRole) elements.profileRole.textContent = repairMojibake(displayRole);
    if (elements.profileAvatar) elements.profileAvatar.textContent = repairMojibake(displayAvatar);
    if (elements.sidebarProfileName) elements.sidebarProfileName.textContent = repairMojibake(displayName);
    if (elements.sidebarProfileRole) elements.sidebarProfileRole.textContent = repairMojibake(displayRole);
    if (elements.sidebarProfileAvatar) elements.sidebarProfileAvatar.textContent = repairMojibake(displayAvatar);
    applyWelcomePhrase(payload.welcome_phrase);
    document.body.classList.toggle("authenticated", Boolean(administrator));
    document.body.classList.remove("auth-gate-pending");
    document.body.classList.toggle(
      "auth-gate-active",
      loginRequired && !administrator,
    );
    return { administrator, loginRequired };
  } catch {
    if (elements.profileName) elements.profileName.textContent = "ØªØ¹Ø°Ø± Ø§Ù„ØªØ­Ù‚Ù‚";
    if (elements.profileRole) elements.profileRole.textContent = "Ø§Ù„Ø®Ø§Ø¯Ù… ØºÙŠØ± Ù…ØªØ§Ø­";
    if (elements.profileAvatar) elements.profileAvatar.textContent = "!";
    if (elements.sidebarProfileName) elements.sidebarProfileName.textContent = "ØªØ¹Ø°Ø± Ø§Ù„ØªØ­Ù‚Ù‚";
    if (elements.sidebarProfileRole) elements.sidebarProfileRole.textContent = "Ø§Ù„Ø®Ø§Ø¯Ù… ØºÙŠØ± Ù…ØªØ§Ø­";
    if (elements.sidebarProfileAvatar) elements.sidebarProfileAvatar.textContent = "!";
    document.body.classList.remove("authenticated");
    document.body.classList.remove("auth-gate-pending");
    document.body.classList.add("auth-gate-active");
    return { administrator: null, loginRequired: true };
  }
}

async function bootstrapAuthentication() {
  const { administrator, loginRequired } = await refreshSession();
  if (loginRequired && !administrator) settingsModule.requireLogin();
}

async function loadReviews() {
  try {
    const response = await fetch("/api/reviews", { credentials: "same-origin" });
    if (!response.ok) throw new Error("failed");
    const payload = await response.json();
    reviewItems = Array.isArray(payload.items) ? payload.items : [];
    renderReviews();
  } catch {
    reviewItems = [];
    renderReviews();
  }
}

function renderReviews() {
  if (!elements.reviewList) return;
  if (!reviewItems.length) {
    elements.reviewList.innerHTML = '<div class="review-placeholder">لا توجد مراجعات حالياً.</div>';
    return;
  }
  elements.reviewList.innerHTML = reviewItems.map((review) => `
    <button class="review-item ${review.review_id === activeReviewId ? "active" : ""}" type="button" data-review-id="${review.review_id}">
      <strong>${repairMojibake(review.filename || "وثيقة")}</strong>
      <div>${repairMojibake(review.status || "pending")}</div>
    </button>
  `).join("");
  elements.reviewList.querySelectorAll(".review-item").forEach((button) => {
    button.addEventListener("click", () => {
      activeReviewId = button.dataset.reviewId;
      renderReviews();
      renderReviewDetail();
    });
  });
  if (!activeReviewId && reviewItems.length) {
    activeReviewId = reviewItems[0].review_id;
  }
  renderReviewDetail();
}

function renderReviewDetail() {
  const review = reviewItems.find((item) => item.review_id === activeReviewId);
  if (!elements.reviewDetail || !review) {
    if (elements.reviewDetail) elements.reviewDetail.innerHTML = '<div class="review-placeholder">اختر مراجعة لعرض التفاصيل.</div>';
    return;
  }
  const metadataText = JSON.stringify(review.metadata || review.extracted_metadata || {}, null, 2);
  const payloadText = JSON.stringify(review.generated_payload || {}, null, 2);
  const logText = JSON.stringify(review.processing_log || [], null, 2);
  elements.reviewDetail.innerHTML = `
    <h3>${repairMojibake(review.filename || "وثيقة")}</h3>
    <p><strong>الحالة:</strong> ${repairMojibake(review.status || "pending")}</p>
    <p><strong>التحقق:</strong> ${repairMojibake(review.validation_status || "pending")}</p>
    <h4>النص الأصلي</h4>
    <pre>${repairMojibake(review.original_text || "")}</pre>
    <h4>البيانات المستخرجة</h4>
    <textarea id="review-metadata-editor">${repairMojibake(metadataText)}</textarea>
    <h4>JSON الناتج</h4>
    <pre>${repairMojibake(payloadText)}</pre>
    <h4>سجل المعالجة</h4>
    <pre>${repairMojibake(logText)}</pre>
    <div class="review-actions">
      <button type="button" class="secondary" data-action="save">حفظ التعديلات</button>
      <button type="button" data-action="approve">موافقة</button>
      <button type="button" class="reject" data-action="reject">رفض</button>
    </div>
  `;
  elements.reviewDetail.querySelector('[data-action="save"]').addEventListener("click", async () => {
    const editor = elements.reviewDetail.querySelector("#review-metadata-editor");
    let parsed = {};
    try { parsed = JSON.parse(editor.value); } catch { parsed = {}; }
    await fetch("/api/reviews/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ review_id: review.review_id, decision: "approve", reviewer: "admin", reason: "edited metadata", metadata: parsed }),
    });
    await loadReviews();
  });
  elements.reviewDetail.querySelector('[data-action="approve"]').addEventListener("click", async () => {
    await fetch("/api/reviews/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ review_id: review.review_id, decision: "approve", reviewer: "admin", reason: "approved by admin" }),
    });
    await loadReviews();
  });
  elements.reviewDetail.querySelector('[data-action="reject"]').addEventListener("click", async () => {
    await fetch("/api/reviews/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ review_id: review.review_id, decision: "reject", reviewer: "admin", reason: "rejected by admin" }),
    });
    await loadReviews();
  });
}

function loadConversations() {
  const readStoredConversations = (key) => {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const stored = JSON.parse(raw);
    if (!Array.isArray(stored)) return [];
    return stored
      .map(repairConversationText)
      .map((conversation) => ({
        ...conversation,
        timestamp: conversation.timestamp || conversation.createdAt || new Date().toISOString(),
        createdAt: conversation.createdAt || conversation.timestamp || new Date().toISOString(),
        messages: Array.isArray(conversation.messages) ? conversation.messages : [],
        evidence: conversation.evidence || { snippets: [], warnings: [], citations: [], sources: [] },
      }));
  };

  try {
    const primary = readStoredConversations(storageKey);
    if (primary.length) return primary;
  } catch (error) {
    console.warn("Could not read primary chat history:", error);
  }

  try {
    return readStoredConversations(storageBackupKey);
  } catch (error) {
    console.warn("Could not read backup chat history:", error);
    return [];
  }
}

function writeLocalConversations() {
  try {
    const serialized = JSON.stringify(conversations);
    localStorage.setItem(storageKey, serialized);
    localStorage.setItem(storageBackupKey, serialized);
    if (activeConversationId) {
      localStorage.setItem(activeConversationStorageKey, activeConversationId);
    } else {
      localStorage.removeItem(activeConversationStorageKey);
    }
  } catch (error) {
    console.warn("Could not persist chat history:", error);
  }
}

function chatHistoryPayload() {
  return {
    conversations,
    activeConversationId,
    updatedAt: new Date().toISOString(),
  };
}

function hasStoredMessages(items = conversations) {
  return items.some((conversation) => conversation.messages?.length);
}

function storedMessageCount(items = conversations) {
  return items.reduce((total, conversation) => total + (conversation.messages?.length || 0), 0);
}

function persistChatHistoryToServer({ allowEmpty = false } = {}) {
  if (!allowEmpty && !hasStoredMessages()) return;
  const serialized = JSON.stringify(chatHistoryPayload());
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([serialized], { type: "application/json" });
      if (navigator.sendBeacon(chatHistoryEndpoint, blob)) return;
    }
  } catch {
    // Fall back to fetch below.
  }
  fetch(chatHistoryEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: serialized,
    keepalive: true,
  }).catch((error) => console.warn("Could not persist server chat history:", error));
}

function saveConversations(options = {}) {
  writeLocalConversations();
  persistChatHistoryToServer(options);
}

function loadActiveConversationId(items) {
  try {
    const storedId = localStorage.getItem(activeConversationStorageKey);
    if (storedId && items.some(({ id }) => id === storedId)) return storedId;
  } catch {
    // Fall back to the newest conversation when localStorage is unavailable.
  }
  return items[0]?.id ?? null;
}

function createConversation(initialTitle = "") {
  const timestamp = new Date().toISOString();
  const conversation = {
    id: crypto.randomUUID(),
    title: initialTitle ? truncate(initialTitle, 40) : "Ù…Ø­Ø§Ø¯Ø«Ø© Ù‚Ø§Ù†ÙˆÙ†ÙŠØ© Ø¬Ø¯ÙŠØ¯Ø©",
    timestamp,
    createdAt: timestamp,
    messages: [],
    evidence: { snippets: [], warnings: [], citations: [], sources: [] },
  };
  conversations.unshift(conversation);
  activeConversationId = conversation.id;
  saveConversations();
  render();
  elements.input.focus();
  return conversation;
}

function startNewConversation() {
  activeConversationId = null;
  saveConversations();
  render();
  closeChatSidebarOnMobile();
  showView("assistant");
  elements.input.focus();
}

function showView(viewName) {
  const showLanding = viewName === "landing";
  const showAssistant = viewName === "assistant";
  const showDecision = viewName === "decision";
  const showReview = viewName === "review";
  const showSettings = viewName === "settings";
  elements.landingView.hidden = !showLanding;
  elements.assistantView.hidden = !showAssistant;
  elements.decisionView.hidden = !showDecision;
  elements.reviewView.hidden = !showReview;
  elements.settingsView.hidden = !showSettings;
  elements.assistantNav.classList.toggle("active", showAssistant || showLanding);
  elements.decisionNav.classList.toggle("active", showDecision);
  elements.reviewNav.classList.toggle("active", showReview);
  elements.settingsNav.classList.toggle("active", showSettings);
  elements.nav.classList.remove("open");
  document.body.classList.toggle("decision-mode", showDecision);
  document.body.classList.toggle("chat-sidebar-enabled", showAssistant || showLanding);
  if (!showAssistant && !showLanding) {
    document.body.classList.remove("chat-sidebar-open");
    elements.chatSidebarBackdrop?.classList.remove("visible");
    if (elements.chatSidebarBackdrop) elements.chatSidebarBackdrop.hidden = true;
  }
  if (showLanding) {
    elements.landingInput.focus();
  } else if (showAssistant) {
    elements.input.focus();
    consumeInitialPrompt();
  } else if (showDecision) {
    elements.dropzoneRoot.querySelector(".upload-dropzone")?.focus();
  } else if (showReview) {
    loadReviews();
  } else if (showSettings) {
    settingsModule.open();
  }
}

function isOverlaySidebar() {
  return window.matchMedia("(max-width: 1020px)").matches;
}

function openChatSidebar() {
  document.body.classList.add("chat-sidebar-open");
  if (elements.chatSidebarBackdrop) {
    elements.chatSidebarBackdrop.hidden = false;
    requestAnimationFrame(() => elements.chatSidebarBackdrop.classList.add("visible"));
  }
}

function closeChatSidebarOnMobile() {
  if (!isOverlaySidebar()) return;
  document.body.classList.remove("chat-sidebar-open");
  elements.chatSidebarBackdrop?.classList.remove("visible");
  window.setTimeout(() => {
    if (!document.body.classList.contains("chat-sidebar-open") && elements.chatSidebarBackdrop) {
      elements.chatSidebarBackdrop.hidden = true;
    }
  }, 240);
}

function toggleChatSidebar() {
  if (isOverlaySidebar()) {
    if (document.body.classList.contains("chat-sidebar-open")) {
      closeChatSidebarOnMobile();
    } else {
      openChatSidebar();
    }
    return;
  }

  document.body.classList.toggle("chat-sidebar-collapsed");
}

function closeOrCollapseChatSidebar() {
  if (isOverlaySidebar()) {
    closeChatSidebarOnMobile();
  } else {
    document.body.classList.add("chat-sidebar-collapsed");
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
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 180)}px`;
  elements.form.requestSubmit();
}

function activeConversation() {
  return conversations.find(({ id }) => id === activeConversationId) ?? null;
}

function selectConversation(id) {
  activeConversationId = id;
  saveConversations();
  render();
  closeChatSidebarOnMobile();
  showView("assistant");
}

function removeAllConversations() {
  conversations = [];
  activeConversationId = null;
  saveConversations({ allowEmpty: true });
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
  if (text !== undefined) node.textContent = repairMojibake(text);
  return node;
}

function legalSourceLine(source) {
  const parts = [
    source.document_type ? `نوع الوثيقة: ${source.document_type}` : "",
    source.section ? `القسم: ${source.section}` : "",
    source.item_number ? `رقم البند: ${source.item_number}` : "",
  ].filter(Boolean);
  return repairMojibake(parts.join(" · ") || "مصدر النص القانوني");
}

function renderLegalSources(sources = [], className = "message-sources") {
  const wrapper = makeElement("section", className);
  wrapper.append(makeElement("strong", "", "المصادر القانونية"));
  const list = makeElement("ul", "");
  sources.forEach((source) => {
    const item = makeElement("li", "");
    item.append(
      makeElement("small", "", legalSourceLine(source)),
    );
    list.append(item);
  });
  wrapper.append(list);
  return wrapper;
}

function render() {
  renderHistory();
  renderConversation();
  renderEvidence();
}

function renderHistory() {
  elements.historyList.replaceChildren();
  const filtered = conversations.filter(({ messages }) => messages?.length);

  if (!filtered.length) {
    elements.historyList.append(makeElement("div", "empty-panel", "Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ø­Ø§Ø¯Ø«Ø§Øª Ù…Ø­ÙÙˆØ¸Ø©."));
    return;
  }

  groupConversationsByDate(filtered).forEach(({ label, items }) => {
    const group = makeElement("section", "chat-history-group");
    group.append(makeElement("div", "chat-history-group-title", label));

    items.forEach((conversation) => {
      const button = makeElement(
        "button",
        `chat-history-item${conversation.id === activeConversationId ? " active" : ""}`,
      );
      button.type = "button";
      button.title = conversation.title;
      button.append(makeElement("span", "chat-history-item-title", conversation.title));
      button.addEventListener("click", () => selectConversation(conversation.id));
      group.append(button);
    });

    elements.historyList.append(group);
  });
}

function groupConversationsByDate(items) {
  const today = startOfDay(new Date());
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const lastSevenDays = new Date(today);
  lastSevenDays.setDate(today.getDate() - 7);

  const buckets = [
    { label: "Ø§Ù„ÙŠÙˆÙ…", items: [] },
    { label: "Ø§Ù„Ø£Ù…Ø³", items: [] },
    { label: "Ø¢Ø®Ø± Ù§ Ø£ÙŠØ§Ù…", items: [] },
    { label: "Ø§Ù„Ø£Ù‚Ø¯Ù…", items: [] },
  ];

  items.forEach((conversation) => {
    const date = startOfDay(new Date(conversation.timestamp || conversation.createdAt));
    if (date.getTime() === today.getTime()) {
      buckets[0].items.push(conversation);
    } else if (date.getTime() === yesterday.getTime()) {
      buckets[1].items.push(conversation);
    } else if (date >= lastSevenDays) {
      buckets[2].items.push(conversation);
    } else {
      buckets[3].items.push(conversation);
    }
  });

  return buckets.filter(({ items: bucketItems }) => bucketItems.length);
}

function startOfDay(date) {
  const nextDate = Number.isNaN(date.getTime()) ? new Date() : new Date(date);
  nextDate.setHours(0, 0, 0, 0);
  return nextDate;
}

function renderConversation() {
  const conversation = activeConversation();
  elements.messages.replaceChildren();
  elements.conversationTitle.textContent = repairMojibake(conversation?.title ?? "Ù…Ø­Ø§Ø¯Ø«Ø© Ù‚Ø§Ù†ÙˆÙ†ÙŠØ© Ø¬Ø¯ÙŠØ¯Ø©");

  const hasMessages = Boolean(conversation?.messages.length);
  elements.welcome.hidden = hasMessages;
  elements.suggestions.hidden = hasMessages;

  // Enable export button when conversation has messages
  if (elements.exportButton) {
    elements.exportButton.disabled = !hasMessages;
  }

  if (!conversation) return;

  conversation.messages.forEach((message) => {
    const article = makeElement("article", `message ${message.role}`);
    article.append(makeElement("div", "message-content", repairMojibake(message.content)));

    const messageSources = Array.isArray(message.sources) ? message.sources : [];
    if (messageSources.length) {
      article.append(renderLegalSources(messageSources, "message-sources"));
    }

    article.append(makeElement("span", "message-meta", message.time || formatTime()));
    elements.messages.append(article);
  });

  requestAnimationFrame(() => {
    elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;
  });
}

function filterVisibleWarnings(warnings = []) {
  return warnings.filter((warning) => {
    const text = String(warning || "");
    return !(
      text.includes("law_year")
      && (
        text.includes("incomplete citation metadata")
        || text.includes("Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø§Ø³ØªØ´Ù‡Ø§Ø¯ Ù†Ø§Ù‚ØµØ©")
      )
    );
  });
}

function renderEvidence() {
  const evidence = activeConversation()?.evidence ?? {
    snippets: [],
    warnings: [],
    citations: [],
    sources: [],
  };
  const legalSources = Array.isArray(evidence.sources) ? evidence.sources : [];

  const referenceTotal = legalSources.length || evidence.snippets.length;
  elements.referenceCount.textContent = repairMojibake(`${referenceTotal} Ù…Ø±Ø§Ø¬Ø¹`);
  elements.sourceList.replaceChildren();

  if (legalSources.length) {
    legalSources.forEach((source) => {
      const card = makeElement("article", "source-card legal-source-card");
      card.append(
        makeElement("p", "", legalSourceLine(source)),
        makeElement("small", "", repairMojibake(`مصدر النص: ${source.chunk_id || ""}`)),
      );
      elements.sourceList.append(card);
    });
  } else if (!evidence.snippets.length) {
    elements.sourceList.append(makeElement("div", "empty-panel", "Ø³ØªØ¸Ù‡Ø± Ø§Ù„Ù…Ø±Ø§Ø¬Ø¹ Ø§Ù„Ù…Ø³ØªØ±Ø¬Ø¹Ø© Ù‡Ù†Ø§ Ø¨Ø¹Ø¯ Ø·Ø±Ø­ Ø§Ù„Ø³Ø¤Ø§Ù„."));
  } else {
    evidence.snippets.slice(0, 3).forEach((snippet) => {
      const card = makeElement("article", "source-card");
      const reference = repairMojibake(snippet.legal_reference || snippet.article_reference || `Ø§Ù„ØµÙØ­Ø© ${snippet.page_number ?? "ØºÙŠØ± Ù…Ø¹Ø±ÙˆÙ"}`);
      card.append(
        makeElement("div", "source-name", repairMojibake(snippet.document_title || snippet.source_file || "Ù…ØµØ¯Ø± ØºÙŠØ± Ù…Ø¹Ø±ÙˆÙ")),
        makeElement("p", "", truncate(normalizeWhitespace(snippet.text), 135)),
        makeElement("small", "", reference),
      );
      elements.sourceList.append(card);
    });
  }

  elements.insightList.replaceChildren();
  const insights = [];
  if (legalSources.length) insights.push(`تم عرض ${legalSources.length} مصادر قانونية مباشرة.`);
  if (evidence.citations.length) insights.push(`ØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ ${evidence.citations.length} Ø§Ø³ØªØ´Ù‡Ø§Ø¯Ø§Øª.`);
  if (evidence.warnings.length) insights.push(`ØªÙˆØ¬Ø¯ ${evidence.warnings.length} Ù…Ù„Ø§Ø­Ø¸Ø§Øª ØªØ­ØªØ§Ø¬ Ø¥Ù„Ù‰ Ù…Ø±Ø§Ø¬Ø¹Ø©.`);
  if (!insights.length) insights.push("Ø³ØªØ¸Ù‡Ø± Ù†ØªØ§Ø¦Ø¬ Ø§Ù„ØªØ­Ù‚Ù‚ ÙˆØ§Ù„Ø§Ø³ØªØ´Ù‡Ø§Ø¯Ø§Øª Ù‡Ù†Ø§ Ø¨Ø¹Ø¯ Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø¥Ø¬Ø§Ø¨Ø©.");
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
  elements.wordCount.textContent = `Ø¹Ø¯Ø¯ Ø§Ù„ÙƒÙ„Ù…Ø§Øª: ${countWords(elements.decisionContent.value)} ÙƒÙ„Ù…Ø©`;
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
  if (showConfirmation) showToast("ØªÙ… Ø­ÙØ¸ Ù…Ø³ÙˆØ¯Ø© Ø§Ù„Ù‚Ø±Ø§Ø± Ù…Ø­Ù„ÙŠØ§Ù‹.");
}

function loadDecisionDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(decisionDraftKey) || "null");
    if (!draft) return;
    if (elements.decisionMinistry) elements.decisionMinistry.value = draft.ministry || elements.decisionMinistry.value;
    if (elements.decisionTitle) elements.decisionTitle.value = draft.title || "";
    if (elements.decisionContent) elements.decisionContent.value = draft.content || "";
    selectedPriority = draft.priority || "Ø¹Ø§Ù„ÙŠØ©";
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
  elements.sendButton.textContent = value ? "..." : "←";
  if (value) {
    stopAiSpeech({ resumeRotation: false });
    setAiCharacterState("thinking");
  } else if (!aiSpeechActive) {
    setAiCharacterState("idle");
  }
}

async function hydrateServerChatHistory() {
  try {
    const response = await fetch(chatHistoryEndpoint, { credentials: "same-origin" });
    if (!response.ok) return;
    const payload = await response.json();
    const serverConversations = Array.isArray(payload.conversations)
      ? payload.conversations.map(repairConversationText)
      : [];
    if (!hasStoredMessages(serverConversations)) return;
    if (hasStoredMessages(conversations) && storedMessageCount(conversations) >= storedMessageCount(serverConversations)) return;

    conversations = serverConversations.map((conversation) => ({
      ...conversation,
      timestamp: conversation.timestamp || conversation.createdAt || new Date().toISOString(),
      createdAt: conversation.createdAt || conversation.timestamp || new Date().toISOString(),
      messages: Array.isArray(conversation.messages) ? conversation.messages : [],
      evidence: conversation.evidence || { snippets: [], warnings: [], citations: [], sources: [] },
    }));
    activeConversationId = (
      payload.activeConversationId
      && conversations.some(({ id }) => id === payload.activeConversationId)
    )
      ? payload.activeConversationId
      : conversations[0]?.id ?? null;
    writeLocalConversations();
    render();
    if (activeConversation()?.messages.length) showView("assistant");
  } catch (error) {
    console.warn("Could not load server chat history:", error);
  }
}

async function submitQuestion(question) {
  if (pending || !question.trim()) return;
  const cleanQuestion = question.trim();
  let conversation = activeConversation();
  if (!conversation) conversation = createConversation(cleanQuestion);
  if (!conversation.messages.length) conversation.title = truncate(cleanQuestion, 40);
  conversation.timestamp = conversation.timestamp || conversation.createdAt || new Date().toISOString();
  conversation.messages.push({ role: "user", content: cleanQuestion, time: formatTime() });
  saveConversations();
  render();
  setPending(true);

  const loading = makeElement("article", "message assistant", "Ø¬Ø§Ø±Ù Ø§Ù„Ø¨Ø­Ø« ÙˆØ¥Ø¹Ø¯Ø§Ø¯ Ø§Ù„Ø¥Ø¬Ø§Ø¨Ø©...");
  loading.id = "loading-message";
  elements.messages.append(loading);
  elements.chatScroll.scrollTop = elements.chatScroll.scrollHeight;

  try {
    const sourceHint = {
      sources: [
        ...(conversation.evidence?.sources || []),
        ...(conversation.messages || []).flatMap((message) => (
          message.role === "assistant" && Array.isArray(message.sources)
            ? message.sources
            : []
        )),
      ].slice(-5),
    };
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: cleanQuestion,
        include_snippets: true,
        source_hint: sourceHint,
      }),
    });
    const payload = await response.json();
    if (response.status === 401) {
      await refreshSession();
      showView("settings");
      throw new Error("Ø§Ù†ØªÙ‡Øª Ø¬Ù„Ø³Ø© Ø§Ù„Ø¯Ø®ÙˆÙ„. ÙŠØ±Ø¬Ù‰ ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„ Ø«Ù… Ø¥Ø¹Ø§Ø¯Ø© Ø¥Ø±Ø³Ø§Ù„ Ø§Ù„Ø³Ø¤Ø§Ù„.");
    }
    if (!response.ok) throw new Error(payload.detail || "ØªØ¹Ø°Ø± Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø¥Ø¬Ø§Ø¨Ø©.");

    conversation.messages.push({
      role: "assistant",
      content: repairMojibake(payload.answer),
      sources: (payload.sources || []).map(repairConversationText),
      warnings: (payload.warnings || []).map(repairMojibake),
      citations: (payload.citations || []).map(repairConversationText),
      time: formatTime(),
    });
    conversation.evidence = {
      snippets: (payload.snippets || []).map(repairConversationText),
      sources: (payload.sources || []).map(repairConversationText),
      warnings: (payload.warnings || []).map(repairMojibake),
      citations: (payload.citations || []).map(repairConversationText),
    };
    saveConversations();
    speakArabicAnswer(payload.answer);
  } catch (error) {
    conversation.messages.push({
      role: "assistant error",
      content: error.message || "ØªØ¹Ø°Ø± Ø§Ù„Ø§ØªØµØ§Ù„ Ø¨Ø§Ù„Ø®Ø§Ø¯Ù….",
      time: formatTime(),
    });
    saveConversations();
    showToast(error.message || "ØªØ¹Ø°Ø± Ø§Ù„Ø§ØªØµØ§Ù„ Ø¨Ø§Ù„Ø®Ø§Ø¯Ù….");
  } finally {
    document.querySelector("#loading-message")?.remove();
    setPending(false);
    render();
    elements.input.focus();
  }
}

function showToast(message) {
  elements.toast.textContent = repairMojibake(message);
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
    const option = new Option(device.label || `Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ† ${index + 1}`, device.deviceId);
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
  discardRecording = false;
  landingVoiceLevel = 0;
  updateLandingWaveform();
  recordingButton?.classList.remove("recording", "transcribing");
  if (recordingButton) {
    recordingButton.disabled = false;
    if (recordingButton === elements.landingVoiceButton) {
      recordingButton.innerHTML = landingVoiceIconMarkup;
    } else {
      recordingButton.innerHTML = voiceIconMarkup;
    }
    recordingButton.setAttribute("aria-label", "Ø¨Ø¯Ø¡ Ø§Ù„Ø¥Ø¯Ø®Ø§Ù„ Ø§Ù„ØµÙˆØªÙŠ");
  }
  setLandingRecordingUi(false);
  if (!pending && !aiSpeechActive) setAiCharacterState("idle");
}

function updateLandingWaveform(samples = null) {
  if (samples?.length) {
    let squareSum = 0;
    for (let index = 0; index < samples.length; index += 1) {
      squareSum += samples[index] * samples[index];
    }
    const rms = Math.sqrt(squareSum / samples.length);
    const target = Math.min(1, Math.max(0, (rms - 0.008) * 14));
    landingVoiceLevel = landingVoiceLevel * 0.62 + target * 0.38;
  } else {
    landingVoiceLevel = 0;
  }

  const bars = elements.landingRecordingControls?.querySelectorAll(".landing-waveform span");
  if (!bars) return;
  const shape = [0.38, 0.62, 0.86, 0.55, 1, 0.72, 0.44, 0.82, 0.58, 0.94, 0.68, 0.42];
  bars.forEach((bar, index) => {
    const height = 4 + landingVoiceLevel * 32 * shape[index % shape.length];
    bar.style.height = `${height.toFixed(1)}px`;
    bar.style.opacity = `${(0.45 + landingVoiceLevel * 0.55).toFixed(2)}`;
  });
}

async function transcribeRecording(blob) {
  recordingButton.classList.remove("recording");
  recordingButton.classList.add("transcribing");
  recordingButton.disabled = true;
  recordingButton.textContent = "â€¦";
  recordingButton.setAttribute("aria-label", "Ø¬Ø§Ø±Ù ØªØ­ÙˆÙŠÙ„ Ø§Ù„ØµÙˆØª Ø¥Ù„Ù‰ Ù†Øµ");

  const formData = new FormData();
  const extension = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "mp4" : "webm";
  formData.append("audio", blob, `recording.${extension}`);

  try {
    const response = await fetch("/transcribe", { method: "POST", body: formData });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "ØªØ¹Ø°Ø± ØªØ­ÙˆÙŠÙ„ Ø§Ù„ØµÙˆØª Ø¥Ù„Ù‰ Ù†Øµ.");
    const separator = recordingInput.value.trim() ? " " : "";
    recordingInput.value = `${recordingInput.value.trimEnd()}${separator}${payload.text}`;
  } catch (error) {
    showToast(error.message || "ØªØ¹Ø°Ø± ØªØ­ÙˆÙŠÙ„ Ø§Ù„ØµÙˆØª Ø¥Ù„Ù‰ Ù†Øµ.");
  } finally {
    const completedInput = recordingInput;
    resetRecorder();
    window.requestAnimationFrame(() => {
      completedInput?.dispatchEvent(new Event("input"));
      completedInput?.focus();
    });
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
      showToast("Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ù‚ØµÙŠØ± Ø¬Ø¯Ø§Ù‹. ØªØ­Ø¯Ø« Ù„Ù…Ø¯Ø© Ø«Ø§Ù†ÙŠØªÙŠÙ† Ø¹Ù„Ù‰ Ø§Ù„Ø£Ù‚Ù„.");
      return;
    }
    transcribeRecording(blob);
    return;
  }

  if (mediaRecorder?.state === "recording") mediaRecorder.stop();
}

async function toggleRecording(button = elements.voiceButton, input = elements.input) {
  if (recordingActive) {
    finishRecording();
    return;
  }
  recordingButton = button;
  recordingInput = input;
  discardRecording = false;
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
    showToast("Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ø§Ù„ØµÙˆØªÙŠ ØºÙŠØ± Ù…Ø¯Ø¹ÙˆÙ… ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ù…ØªØµÙØ­.");
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
        const samples = new Float32Array(event.inputBuffer.getChannelData(0));
        pcmChunks.push(samples);
        if (recordingButton === elements.landingVoiceButton) updateLandingWaveform(samples);
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
        if (discardRecording) {
          resetRecorder();
          return;
        }
        const recordingDuration = Date.now() - recordingStartedAt;
        const blob = new Blob(recordingChunks, { type: mediaRecorder.mimeType || "audio/webm" });
        if (recordingDuration < minimumRecordingMs) {
          resetRecorder();
          showToast("Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ù‚ØµÙŠØ± Ø¬Ø¯Ø§Ù‹. ØªØ­Ø¯Ø« Ù„Ù…Ø¯Ø© Ø«Ø§Ù†ÙŠØªÙŠÙ† Ø¹Ù„Ù‰ Ø§Ù„Ø£Ù‚Ù„.");
          return;
        }
        transcribeRecording(blob);
      }, { once: true });
      mediaRecorder.start(250);
    }
    recordingStartedAt = Date.now();
    recordingActive = true;
    setAiCharacterState("listening");
    recordingButton.classList.add("recording");
    recordingButton.innerHTML = stopRecordingIconMarkup;
    recordingButton.setAttribute("aria-label", "Ø¥ÙŠÙ‚Ø§Ù Ø§Ù„ØªØ³Ø¬ÙŠÙ„");
    setLandingRecordingUi(recordingButton === elements.landingVoiceButton);
    showToast("Ø¨Ø¯Ø£ Ø§Ù„ØªØ³Ø¬ÙŠÙ„. Ø§Ø¶ØºØ· Ø¹Ù„Ù‰ Ø§Ù„Ù…Ø±Ø¨Ø¹ Ø§Ù„Ø£Ø­Ù…Ø± Ø¹Ù†Ø¯ Ø§Ù„Ø§Ù†ØªÙ‡Ø§Ø¡.");
    recordingTimer = window.setTimeout(() => {
      if (recordingActive) finishRecording();
    }, maximumRecordingMs);
  } catch (error) {
    console.error("Microphone startup failed:", error);
    resetRecorder();
    if (error?.name === "NotAllowedError") {
      showToast("ØªÙ… Ø±ÙØ¶ Ø¥Ø°Ù† Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ† Ù…Ù† Ø§Ù„Ù…ØªØµÙØ­.");
    } else if (error?.name === "NotReadableError") {
      showToast("Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ† Ù…Ø³ØªØ®Ø¯Ù… Ù…Ù† ØªØ·Ø¨ÙŠÙ‚ Ø¢Ø®Ø± Ø£Ùˆ ØºÙŠØ± Ù…ØªØ§Ø­ Ù„Ù„Ù†Ø¸Ø§Ù….");
    } else if (error?.name === "OverconstrainedError") {
      showToast("Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ† Ù„Ø§ ÙŠØ¯Ø¹Ù… Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ù…Ø·Ù„ÙˆØ¨Ø©.");
    } else {
      showToast(`ØªØ¹Ø°Ø± ØªØ´ØºÙŠÙ„ Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ†: ${error?.message || "Ø®Ø·Ø£ ØºÙŠØ± Ù…Ø¹Ø±ÙˆÙ"}`);
    }
  }
}

function setLandingRecordingUi(active) {
  elements.landingForm?.classList.toggle("recording-mode", active);
  if (elements.landingRecordingControls) elements.landingRecordingControls.hidden = !active;
  elements.landingRecordingControls?.classList.remove("transcribing");
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = elements.input.value;
  elements.input.value = "";
  elements.input.style.height = "";
  submitQuestion(question);
});

elements.voiceButton?.addEventListener("click", () => {
  toggleRecording(elements.voiceButton, elements.input);
});
elements.microphoneSelect?.addEventListener("change", () => {
  localStorage.setItem(microphoneStorageKey, elements.microphoneSelect.value);
  showToast("ØªÙ… Ø§Ø®ØªÙŠØ§Ø± Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ†. Ø§Ø¨Ø¯Ø£ ØªØ³Ø¬ÙŠÙ„Ø§Ù‹ Ø¬Ø¯ÙŠØ¯Ø§Ù‹.");
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
  const nextHeight = Math.min(elements.input.scrollHeight, 180);
  elements.input.style.height = `${nextHeight}px`;
  elements.input.style.overflowY = elements.input.scrollHeight > 180 ? "auto" : "hidden";
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
elements.reviewNav?.addEventListener("click", async () => {
  await loadReviews();
  showView("review");
});
elements.settingsNav.addEventListener("click", () => showView("settings"));
elements.logoutButton?.addEventListener("click", async () => {
  try {
    await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "same-origin",
    });
  } finally {
    await refreshSession();
    showView("settings");
  }
});
elements.newChatInline?.addEventListener("click", startNewConversation);
elements.clearHistory?.addEventListener("click", removeAllConversations);
elements.historySearch?.addEventListener("input", renderHistory);
elements.mobileMenu?.addEventListener("click", toggleChatSidebar);
elements.chatSidebarClose?.addEventListener("click", closeOrCollapseChatSidebar);
elements.chatSidebarBackdrop?.addEventListener("click", closeChatSidebarOnMobile);
window.addEventListener("resize", () => {
  if (!isOverlaySidebar()) {
    document.body.classList.remove("chat-sidebar-open");
    elements.chatSidebarBackdrop?.classList.remove("visible");
    if (elements.chatSidebarBackdrop) elements.chatSidebarBackdrop.hidden = true;
  }
});

// Export functionality
elements.exportButton?.addEventListener("click", (event) => {
  event.stopPropagation();
  elements.exportDropdown.hidden = !elements.exportDropdown.hidden;
});

elements.exportDropdown?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-format]");
  if (button) {
    exportConversation(button.dataset.format);
    elements.exportDropdown.hidden = true;
  }
});

document.addEventListener("click", () => {
  elements.exportDropdown.hidden = true;
});

// Landing voice button
elements.landingVoiceButton?.addEventListener("click", async (event) => {
  event.preventDefault();
  await toggleRecording(elements.landingVoiceButton, elements.landingInput);
});

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
    showToast("ÙŠØ±Ø¬Ù‰ Ø¥Ø¯Ø®Ø§Ù„ Ø¹Ù†ÙˆØ§Ù† Ø§Ù„Ù‚Ø±Ø§Ø± ÙˆÙ†ØµÙ‡ Ø§Ù„ÙƒØ§Ù…Ù„.");
    return;
  }
  saveDecisionDraft(false);
  showToast("ÙˆØ§Ø¬Ù‡Ø© Ø±ÙØ¹ Ø§Ù„Ù‚Ø±Ø§Ø± Ø¬Ø§Ù‡Ø²Ø©. Ù„Ù… ÙŠØªÙ… Ø¥Ø±Ø³Ø§Ù„ Ø¨ÙŠØ§Ù†Ø§Øª Ø¥Ù„Ù‰ Ø§Ù„Ø®Ø§Ø¯Ù….");
});

// Export conversation function
async function exportConversation(format = "pdf") {
  const conversation = activeConversation();
  if (!conversation || !conversation.messages.length) {
    showToast("Ù„Ø§ ØªÙˆØ¬Ø¯ Ø±Ø³Ø§Ø¦Ù„ Ù„Ù„ØªØµØ¯ÙŠØ±.");
    return;
  }

  elements.exportButton.disabled = true;
  elements.exportButton.textContent = "â€¦";
  elements.exportButton.setAttribute("aria-label", "Ø¬Ø§Ø±Ù Ø§Ù„ØªØµØ¯ÙŠØ±");

  try {
    const response = await fetch(`/api/export-chat?format=${format}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: conversation.title,
        messages: conversation.messages,
      }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "ÙØ´Ù„ ØªØµØ¯ÙŠØ± Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø©.");
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const filename = `${conversation.title.replace(/[\/\\?%*:|"<>]/g, "_")}.${format === "pdf" ? "pdf" : "txt"}`;

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    showToast("ØªÙ… ØªØµØ¯ÙŠØ± Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø© Ø¨Ù†Ø¬Ø§Ø­.");
  } catch (error) {
    console.error("Export failed:", error);
    showToast(error.message || "ÙØ´Ù„ ØªØµØ¯ÙŠØ± Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø©.");
  } finally {
    elements.exportButton.disabled = false;
    elements.exportButton.textContent = "â‡© ØªØµØ¯ÙŠØ±";
    elements.exportButton.setAttribute("aria-label", "ØªØµØ¯ÙŠØ± Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø©");
  }
}

loadDecisionDraft();
render();
repairTextTree();
initializeAiCharacter();
bootstrapAuthentication();
hydrateServerChatHistory();
window.addEventListener("pagehide", saveConversations);
window.addEventListener("beforeunload", saveConversations);
if (
  window.location.hash === "#chat"
  || new URLSearchParams(window.location.search).has("prompt")
  || activeConversation()?.messages.length
) {
  showView("assistant");
} else {
  showView("landing");
}
