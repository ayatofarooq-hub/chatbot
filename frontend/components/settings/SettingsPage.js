import { applyLanguage, t } from "./i18n.js";

const fields = {
  model: [["chat_model","Active chat model"],["embedding_model","Embedding model"],["ollama_base_url","Ollama base URL"],["request_timeout","Request timeout","number"],["keep_alive","Keep-alive duration"],["max_answer_tokens","Maximum answer tokens","number"],["temperature","Temperature","number"],["top_p","Top P","number"],["context_length","Context length","number"]],
  retrieval: [["chunk_size","Chunk size","number"],["chunk_overlap","Chunk overlap","number"],["semantic_weight","Semantic weight","number"],["keyword_weight","Keyword/BM25 weight","number"],["result_count","Result count","number"],["hybrid_search","Hybrid search","checkbox"],["debug_context","Debug retrieved context","checkbox"],["ocr_enabled","OCR enabled","checkbox"],["ocr_language","OCR language","select",["ara","eng","ara+eng"]]],
  authentication: [["login_enabled","Enable login","checkbox"],["guest_access","Allow guest access","checkbox"],["remember_login","Remember login","checkbox"],["session_timeout_minutes","Session timeout","select",[15,30,60,240,null]],["password_min_length","Minimum password length","number"],["require_numbers","Require numbers","checkbox"],["require_symbols","Require symbols","checkbox"],["require_uppercase","Require uppercase Latin","checkbox"]],
  appearance: [["language","Language","select",["ar","en"]],["theme","Theme","select",["light","dark","system"]],["primary_color","Primary color","select",["green","gold","blue","custom"]],["custom_primary_color","Custom color","color"],["interface_scale","Interface scale","select",["small","medium","large"]]],
  upload: [["max_file_size_mb","Maximum file size (MB)","number"],["max_file_count","Maximum file count","number"],["allow_docx","Allow DOCX","checkbox"],["allow_pdf","Allow PDF","checkbox"],["allow_txt","Allow TXT","checkbox"],["ocr_enabled","OCR enabled","checkbox"],["ocr_language","OCR language","select",["ara","eng","ara+eng"]]],
  notifications: [["browser_notifications","Browser notifications","checkbox"],["processing_completed","Processing completed","checkbox"],["upload_failed","Upload failed","checkbox"],["model_error","Ollama/model error","checkbox"],["index_rebuild_completed","Index rebuild completed","checkbox"],["database_backup_completed","Database backup completed","checkbox"]],
  backup: [["automatic_frequency","Automatic backup","select",[null,"daily","weekly","monthly"]],["local_destination","Local destination"]],
};

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const problem = new Error(payload.error?.detail || "Request failed");
    problem.status = response.status;
    throw problem;
  }
  return payload;
}

export function createSettingsModule({ root, modalRoot, showToast }) {
  let state;
  let dirty = false;
  const json = (method, body) => ({ method, headers: {"Content-Type":"application/json"}, body: JSON.stringify(body) });

  function applyAppearance() {
    applyLanguage(state.appearance.language);
    document.documentElement.dataset.theme = state.appearance.theme;
    document.documentElement.dataset.scale = state.appearance.interface_scale;
    document.documentElement.dataset.primary = state.appearance.primary_color;
    const custom = state.appearance.primary_color === "custom" ? state.appearance.custom_primary_color : "";
    document.documentElement.style.setProperty("--custom-primary", custom || "#145a38");
  }

  function showLogin() {
    modalRoot.innerHTML = `<div class="settings-modal-backdrop"><form class="settings-modal" id="settings-login"><h2>${t("login")}</h2><label>${t("username")}<input name="username" required autocomplete="username"></label><label>${t("password")}<input name="password" type="password" required autocomplete="current-password"></label><p class="field-error"></p><button class="primary-button">${t("login")}</button></form></div>`;
    modalRoot.querySelector("form").onsubmit = async (event) => {
      event.preventDefault();
      try {
        await api("/api/auth/login", json("POST", Object.fromEntries(new FormData(event.currentTarget))));
        modalRoot.replaceChildren(); await load();
      } catch (error) { modalRoot.querySelector(".field-error").textContent = error.message; }
    };
  }

  function control(section, definition) {
    const [key, labelText, type = "text", options] = definition;
    const label = document.createElement("label");
    label.className = `settings-field ${type === "checkbox" ? "checkbox-field" : ""}`;
    const input = type === "select" ? document.createElement("select") : document.createElement("input");
    if (type !== "select") input.type = type;
    if (type === "select") options.forEach((value) => input.add(new Option(value ?? "Never", value ?? "")));
    if (type === "checkbox") input.checked = state[section][key]; else input.value = state[section][key] ?? "";
    label.append(input, Object.assign(document.createElement("span"), { textContent: labelText }));
    input.onchange = () => {
      let value = type === "checkbox" ? input.checked : type === "number" ? Number(input.value) : input.value || null;
      if (section === "authentication" && key === "login_enabled" && !value && !confirm(state.appearance.language === "ar" ? "سيصبح النظام متاحاً لأي شخص يمكنه الوصول إلى الخادم." : "Anyone who can reach the server will be able to access the system.")) {
        input.checked = true; return;
      }
      state[section][key] = value; dirty = true;
      root.querySelector(".unsaved-banner").hidden = false;
      if (section === "appearance") { applyAppearance(); render(); }
      if (section === "model" && key === "embedding_model") showToast("Changing the embedding model requires an index rebuild.");
    };
    return label;
  }

  async function renderClassifications() {
    const {items} = await api("/api/settings/classifications");
    const list = root.querySelector("#classification-list");
    list.replaceChildren(...items.map((item) => {
      const row = document.createElement("div"); row.className = "classification-row";
      row.innerHTML = `<i></i><strong></strong><span></span><small>${item.law_count} records</small><button>Edit</button><button class="danger-button">Delete</button>`;
      row.querySelector("i").style.backgroundColor = item.color;
      row.querySelector("strong").textContent = item.name_ar; row.querySelector("span").textContent = item.name_en;
      row.children[4].onclick = () => classificationForm(item);
      row.children[5].onclick = async () => {
        if (item.law_count) {
          const target = prompt(`Classification has ${item.law_count} laws. Enter replacement classification ID:`);
          if (!target) return;
          await api(`/api/settings/classifications/${item.id}/reassign`, json("POST",{target_id:Number(target)}));
        } else if (confirm("Delete classification?")) await api(`/api/settings/classifications/${item.id}`, {method:"DELETE"}); else return;
        renderClassifications();
      };
      return row;
    }));
  }

  function classificationForm(item = {}) {
    modalRoot.innerHTML = `<div class="settings-modal-backdrop"><form class="settings-modal"><h2>${t(item.id ? "save" : "add")}</h2><label>Arabic name<input name="name_ar" required></label><label>English name<input name="name_en" required></label><label>Description<textarea name="description"></textarea></label><label>Icon<input name="icon_identifier"></label><label>Color<input name="color" type="color"></label><label>Order<input name="display_order" type="number"></label><label><input name="enabled" type="checkbox"> Enabled</label><p class="field-error"></p><button class="primary-button">${t("save")}</button><button type="button" data-cancel>Cancel</button></form></div>`;
    const form = modalRoot.querySelector("form");
    ["name_ar","name_en","description","icon_identifier","color","display_order"].forEach((key) => form.elements[key].value = item[key] ?? (key === "color" ? "#145a38" : ""));
    form.elements.enabled.checked = item.enabled ?? true;
    form.querySelector("[data-cancel]").onclick = () => modalRoot.replaceChildren();
    form.onsubmit = async (event) => {
      event.preventDefault(); const data = Object.fromEntries(new FormData(form));
      data.enabled = form.elements.enabled.checked; data.display_order = Number(data.display_order);
      try { await api(item.id ? `/api/settings/classifications/${item.id}` : "/api/settings/classifications", json(item.id ? "PUT" : "POST",data)); modalRoot.replaceChildren(); renderClassifications(); }
      catch(error) { form.querySelector(".field-error").textContent = error.message; }
    };
  }

  function render() {
    const language = state.appearance.language;
    root.innerHTML = `<header class="settings-header"><div><h1>${t("settings",language)}</h1><p>Application administration and runtime configuration</p></div><div><button data-reset>${t("reset",language)}</button><button class="primary-button" data-save>${t("save",language)}</button></div></header><div class="unsaved-banner" ${dirty ? "" : "hidden"}>${t("unsaved",language)}</div><div class="settings-grid"></div>`;
    const grid = root.querySelector(".settings-grid");
    Object.entries(fields).forEach(([section, definitions]) => {
      const card = document.createElement("section"); card.className = "settings-card";
      card.innerHTML = `<h2>${t(section,language)}</h2><div class="settings-fields"></div>`;
      definitions.forEach((definition) => card.querySelector(".settings-fields").append(control(section,definition)));
      if (section === "upload" && state.capabilities?.upload_endpoint === false) {
        card.insertAdjacentHTML("beforeend","<p class=\"unsupported-note\">No backend upload endpoint exists; values are persisted for future enforcement, but uploads remain unavailable.</p>");
        card.querySelectorAll("input,select").forEach((input) => input.disabled = true);
      }
      if (section === "model") card.insertAdjacentHTML("beforeend",`<button data-test>${t("test",language)}</button>`);
      if (section === "retrieval") card.insertAdjacentHTML("beforeend",`<button class="danger-button" data-rebuild>${t("rebuild",language)}</button>`);
      if (section === "backup") card.insertAdjacentHTML("beforeend",`<p class="unsupported-note">Native database backup is not configured. JSON includes settings only.</p><a class="button-link" href="/api/settings/export">${t("export",language)}</a><button data-import>${t("import",language)}</button><input type="file" hidden accept="application/json">`);
      grid.append(card);
    });
    grid.insertAdjacentHTML("beforeend",`<section class="settings-card full-width"><h2>${t("classifications",language)}</h2><div id="classification-list"></div><button data-add>${t("add",language)}</button></section><section class="settings-card full-width disabled-section"><h2>${t("fineTuning",language)} — ${t("notConfigured",language)}</h2><p>No fine-tuning pipeline exists. A real dataset, trainer, scheduler, and monitoring implementation are required.</p></section>`);
    root.querySelector("[data-save]").onclick = async () => { try { const body={}; Object.keys(fields).forEach((key)=>body[key]=state[key]); state=await api("/api/settings",json("PUT",body)); dirty=false; applyAppearance(); render(); showToast(t("saved",state.appearance.language)); } catch(error){showToast(error.message);} };
    root.querySelector("[data-reset]").onclick = async () => { if(confirm(t("reset",language))){state=await api("/api/settings/reset",{method:"POST"});dirty=false;applyAppearance();render();} };
    root.querySelector("[data-test]").onclick = async () => { try{await api("/api/settings/model/test",json("POST",state.model));showToast("Ollama connection succeeded");}catch(error){showToast(error.message);} };
    root.querySelector("[data-rebuild]").onclick = async () => { if(confirm("Rebuild the generated index from PostgreSQL?")){await api("/api/settings/index/rebuild",{method:"POST"});showToast("Index rebuild started");} };
    root.querySelector("[data-add]").onclick = () => classificationForm();
    const importButton=root.querySelector("[data-import]"); const importInput=importButton.nextElementSibling;
    importButton.onclick=()=>importInput.click(); importInput.onchange=async()=>{state=await api("/api/settings/import",json("POST",JSON.parse(await importInput.files[0].text())));applyAppearance();render();};
    renderClassifications();
  }

  async function load() {
    try { state=await api("/api/settings"); const saved=localStorage.getItem("legal-ui-language"); if(saved) state.appearance.language=saved; applyAppearance(); render(); }
    catch(error) { if(error.status===401) showLogin(); else root.innerHTML=`<p class="settings-error">${error.message}</p>`; }
  }
  return {open:load};
}
