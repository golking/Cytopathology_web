const API_BASE_URL =
  window.APP_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000/api/v1";

const state = {
  supportMatrix: null,
  previewUrls: [],
  selectedFiles: [],
  currentSessionId: null,
  resultCardMap: new Map(),
  historyItems: []
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
  els.form = document.getElementById("analysisForm");
  els.virusSelect = document.getElementById("virusSelect");
  els.cellLineSelect = document.getElementById("cellLineSelect");
  els.imageInput = document.getElementById("imageInput");
  els.submitButton = document.getElementById("submitButton");

  els.statusText = document.getElementById("statusText");
  els.progressBar = document.getElementById("progressBar");
  els.progressText = document.getElementById("progressText");

  els.errorBox = document.getElementById("errorBox");
  els.warningBox = document.getElementById("warningBox");

  els.resultsEmpty = document.getElementById("resultsEmpty");
  els.resultsList = document.getElementById("resultsList");

  els.summaryTotal = document.getElementById("summaryTotal");
  els.summaryCompleted = document.getElementById("summaryCompleted");
  els.summaryFailed = document.getElementById("summaryFailed");
  els.summaryPending = document.getElementById("summaryPending");
  els.classSummaryEmpty = document.getElementById("classSummaryEmpty");
  els.classSummaryList = document.getElementById("classSummaryList");

  els.historyEmpty = document.getElementById("historyEmpty");
  els.historyList = document.getElementById("historyList");
  els.refreshHistoryButton = document.getElementById("refreshHistoryButton");

  els.virusSelect.addEventListener("change", populateCellLines);
  els.imageInput.addEventListener("change", handleImageSelection);
  els.form.addEventListener("submit", handleSubmit);
  els.refreshHistoryButton.addEventListener("click", handleRefreshHistory);

  resetSummary();
  renderHistory([]);

  Promise.all([loadSupportMatrix(), refreshHistory()]).catch((error) => {
    showError(formatError(error));
  });
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get("content-type") || "";

  let payload = null;

  if (response.status !== 204) {
    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else {
      payload = await response.text();
    }
  }

  if (!response.ok) {
    const error = new Error(
      payload?.error?.message || `HTTP ${response.status}`
    );
    error.payload = payload;
    throw error;
  }

  return payload;
}

function getClientToken() {
  let token = localStorage.getItem("x-client-token");

  if (!token) {
    token = crypto.randomUUID();
    localStorage.setItem("x-client-token", token);
  }

  return token;
}

function getClientTokenHeaders() {
  return {
    "X-Client-Token": getClientToken()
  };
}

async function loadSupportMatrix() {
  const data = await apiRequest("/support-matrix");
  state.supportMatrix = data;

  populateViruses();
  populateCellLines();
}

async function refreshHistory(activeSessionId = state.currentSessionId) {
  const payload = await apiRequest("/analysis-sessions?limit=20&offset=0", {
    headers: getClientTokenHeaders()
  });

  state.historyItems = payload.items || [];
  renderHistory(state.historyItems, activeSessionId);
}

async function handleRefreshHistory() {
  clearMessages();

  try {
    await refreshHistory();
  } catch (error) {
    showError(formatError(error));
  }
}

function populateViruses() {
  els.virusSelect.innerHTML = "";

  for (const virus of state.supportMatrix.viruses) {
    const option = document.createElement("option");
    option.value = virus.code;
    option.textContent = virus.name;
    els.virusSelect.appendChild(option);
  }
}

function populateCellLines() {
  const virusCode = els.virusSelect.value;

  const allowedCellLineCodes = new Set(
    state.supportMatrix.profiles
      .filter((profile) => profile.virus_code === virusCode)
      .map((profile) => profile.cell_line_code)
  );

  const cellLines = state.supportMatrix.cell_lines.filter((item) =>
    allowedCellLineCodes.has(item.code)
  );

  els.cellLineSelect.innerHTML = "";

  for (const cellLine of cellLines) {
    const option = document.createElement("option");
    option.value = cellLine.code;
    option.textContent = cellLine.name;
    els.cellLineSelect.appendChild(option);
  }
}

function handleImageSelection() {
  clearMessages();

  state.currentSessionId = null;
  renderHistory(state.historyItems, null);

  state.selectedFiles = Array.from(els.imageInput.files || []);
  renderSelectedFiles(state.selectedFiles);
  renderSelectionSummary(state.selectedFiles.length);

  setStatus("Ожидание запуска", 0);
}

function disposePreviewUrls() {
  for (const url of state.previewUrls) {
    URL.revokeObjectURL(url);
  }
  state.previewUrls = [];
}

function clearResultsGrid() {
  disposePreviewUrls();
  state.resultCardMap.clear();
  els.resultsList.innerHTML = "";
  els.resultsEmpty.hidden = false;
}

function createResultCard({
  imageIndex,
  filename,
  previewUrl = null,
  statusText = "Выбрано"
}) {
  const card = document.createElement("article");
  card.className = "image-result-card";
  card.dataset.imageIndex = String(imageIndex);

  const thumbWrap = document.createElement("div");
  thumbWrap.className = "thumb-wrap";

  const img = document.createElement("img");
  img.className = "thumb-image hidden";
  img.alt = filename || `Изображение ${imageIndex}`;

  const fallback = document.createElement("div");
  fallback.className = "thumb-fallback";
  fallback.textContent = "Нет предпросмотра";

  thumbWrap.appendChild(img);
  thumbWrap.appendChild(fallback);

  const body = document.createElement("div");
  body.className = "image-result-body";

  const fileName = document.createElement("div");
  fileName.className = "file-name";
  fileName.textContent = filename || `Изображение ${imageIndex}`;

  const statusRow = document.createElement("div");
  statusRow.className = "item-row";

  const statusLabel = document.createElement("div");
  statusLabel.className = "item-label";
  statusLabel.textContent = "Статус";

  const statusValue = document.createElement("div");
  statusValue.className = "item-value";
  statusValue.textContent = statusText;

  statusRow.appendChild(statusLabel);
  statusRow.appendChild(statusValue);

  const classRow = document.createElement("div");
  classRow.className = "item-row";

  const classLabel = document.createElement("div");
  classLabel.className = "item-label";
  classLabel.textContent = "Класс";

  const classValue = document.createElement("div");
  classValue.className = "item-value";
  classValue.textContent = "—";

  classRow.appendChild(classLabel);
  classRow.appendChild(classValue);

  const confidenceRow = document.createElement("div");
  confidenceRow.className = "item-row";

  const confidenceLabel = document.createElement("div");
  confidenceLabel.className = "item-label";
  confidenceLabel.textContent = "Confidence";

  const confidenceValue = document.createElement("div");
  confidenceValue.className = "item-value";
  confidenceValue.textContent = "—";

  confidenceRow.appendChild(confidenceLabel);
  confidenceRow.appendChild(confidenceValue);

  const warningBox = document.createElement("div");
  warningBox.className = "card-message card-warning hidden";

  const errorBox = document.createElement("div");
  errorBox.className = "card-message card-error hidden";

  body.appendChild(fileName);
  body.appendChild(statusRow);
  body.appendChild(classRow);
  body.appendChild(confidenceRow);
  body.appendChild(warningBox);
  body.appendChild(errorBox);

  card.appendChild(thumbWrap);
  card.appendChild(body);

  els.resultsList.appendChild(card);

  const refs = {
    card,
    fileName,
    statusValue,
    classValue,
    confidenceValue,
    warningBox,
    errorBox,
    img,
    fallback
  };

  state.resultCardMap.set(imageIndex, refs);

  if (previewUrl) {
    setCardImage(refs, previewUrl);
  } else {
    setCardFallback(refs, "Нет предпросмотра");
  }

  return refs;
}
function ensureResultCard(imageIndex, filename) {
  let refs = state.resultCardMap.get(imageIndex);

  if (!refs) {
    els.resultsEmpty.hidden = true;
    refs = createResultCard({
      imageIndex,
      filename,
      previewUrl: null,
      statusText: "Ожидание"
    });
  }

  return refs;
}

function resetCardState(refs) {
  refs.statusValue.textContent = "Ожидание анализа";
  refs.classValue.textContent = "—";
  refs.confidenceValue.textContent = "—";
  refs.warningBox.textContent = "";
  refs.warningBox.classList.add("hidden");
  refs.errorBox.textContent = "";
  refs.errorBox.classList.add("hidden");
}



function renderSelectedFiles(files) {
  clearResultsGrid();

  if (!files.length) {
    resetSummary();
    return;
  }

  els.resultsEmpty.hidden = true;

  files.forEach((file, index) => {
    const previewUrl = URL.createObjectURL(file);
    state.previewUrls.push(previewUrl);

    createResultCard({
      imageIndex: index + 1,
      filename: file.name,
      previewUrl,
      statusText: "Выбрано"
    });
  });
}

function resolveApiUrl(url) {
  if (!url) {
    return null;
  }

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  const apiOrigin = new URL(API_BASE_URL).origin;

  if (url.startsWith("/")) {
    return `${apiOrigin}${url}`;
  }

  return `${apiOrigin}/${url}`;
}

function setCardFallback(refs, text = "Нет предпросмотра") {
  refs.img.classList.add("hidden");
  refs.fallback.classList.remove("hidden");
  refs.fallback.textContent = text;
}

function setCardImage(refs, imageUrl) {
  const resolvedUrl = resolveApiUrl(imageUrl);
  if (!resolvedUrl) {
    setCardFallback(refs, "Нет предпросмотра");
    return;
  }

  if (refs.img.dataset.sourceUrl === resolvedUrl &&
      !refs.img.classList.contains("hidden")) {
    return;
  }

  refs.img.dataset.sourceUrl = resolvedUrl;

  refs.img.onload = () => {
    refs.img.classList.remove("hidden");
    refs.fallback.classList.add("hidden");
    refs.fallback.textContent = "Нет предпросмотра";
  };

  refs.img.onerror = () => {
    setCardFallback(refs, "Не удалось загрузить изображение");
  };

  setCardFallback(refs, "Загрузка предпросмотра...");
  refs.img.src = resolvedUrl;
}

function resetCardsForRun() {
  for (const refs of state.resultCardMap.values()) {
    resetCardState(refs);
  }
}

function updateCardsFromUploadedImages(uploadedImages) {
  for (const image of uploadedImages) {
    const refs = ensureResultCard(image.image_index, image.original_filename);
    refs.fileName.textContent = image.original_filename;
    refs.statusValue.textContent = mapStatus(image.status);

    const previewUrl = image.preview_url || image.original_url;
    if (previewUrl) {
      setCardImage(refs, previewUrl);
    } else {
      setCardFallback(refs, "Нет предпросмотра");
    }
  }
}

function updateCardsFromApiResults(results) {
  for (const result of results) {
    const refs = ensureResultCard(result.image_index, result.original_filename);

    refs.fileName.textContent =
      result.original_filename || refs.fileName.textContent;
    refs.statusValue.textContent = mapStatus(result.status);

    const previewUrl = result.preview_url || result.original_url;
    if (previewUrl) {
      setCardImage(refs, previewUrl);
    } else {
      setCardFallback(refs, "Нет предпросмотра");
    }

    refs.warningBox.textContent = "";
    refs.warningBox.classList.add("hidden");
    refs.errorBox.textContent = "";
    refs.errorBox.classList.add("hidden");

    if (result.error_message) {
      refs.errorBox.textContent = result.error_message;
      refs.errorBox.classList.remove("hidden");
    }

    const tc = result.time_classification;
    if (tc) {
      refs.classValue.textContent = tc.predicted_class;
      refs.confidenceValue.textContent = formatConfidence(tc.confidence);

      const isLowConfidence =
        tc.confidence_flag === "low" ||
        result.warnings?.includes("low_confidence");

      if (isLowConfidence) {
        refs.warningBox.textContent =
          "Низкая уверенность предсказания. Интерпретируйте результат осторожно.";
        refs.warningBox.classList.remove("hidden");
      }
    } else {
      refs.classValue.textContent = "—";
      refs.confidenceValue.textContent = "—";
    }
  }
}
function resetSummary() {
  setSummaryMetrics({
    total: 0,
    completed: 0,
    failed: 0
  });
  renderClassDistribution({});
}

function renderSelectionSummary(totalFiles) {
  setSummaryMetrics({
    total: totalFiles,
    completed: 0,
    failed: 0
  });
  renderClassDistribution({});
}

function setSummaryMetrics({ total, completed, failed }) {
  const safeTotal = Math.max(0, Number(total) || 0);
  const safeCompleted = Math.max(0, Number(completed) || 0);
  const safeFailed = Math.max(0, Number(failed) || 0);
  const safePending = Math.max(0, safeTotal - safeCompleted - safeFailed);

  els.summaryTotal.textContent = String(safeTotal);
  els.summaryCompleted.textContent = String(safeCompleted);
  els.summaryFailed.textContent = String(safeFailed);
  els.summaryPending.textContent = String(safePending);
}

function renderClassDistribution(classCounts) {
  els.classSummaryList.innerHTML = "";

  const entries = Object.entries(classCounts).sort((a, b) => {
    if (b[1] !== a[1]) {
      return b[1] - a[1];
    }
    return a[0].localeCompare(b[0], "ru");
  });

  if (!entries.length) {
    els.classSummaryEmpty.hidden = false;
    return;
  }

  els.classSummaryEmpty.hidden = true;

  for (const [className, count] of entries) {
    const chip = document.createElement("div");
    chip.className = "class-chip";

    const label = document.createElement("span");
    label.className = "class-chip-label";
    label.textContent = className;

    const badge = document.createElement("span");
    badge.className = "class-chip-count";
    badge.textContent = String(count);

    chip.appendChild(label);
    chip.appendChild(badge);

    els.classSummaryList.appendChild(chip);
  }
}

function updateSummary(session, results) {
  const progress = session?.progress || {};

  const total =
    Number.isFinite(progress.total_images)
      ? progress.total_images
      : Math.max(results.length, state.selectedFiles.length);

  const completed =
    Number.isFinite(progress.completed_images)
      ? progress.completed_images
      : results.filter((item) => item.status === "completed").length;

  const failed =
    Number.isFinite(progress.failed_images)
      ? progress.failed_images
      : results.filter((item) => item.status === "failed").length;

  setSummaryMetrics({
    total,
    completed,
    failed
  });

  const classCounts = {};

  for (const result of results) {
    const predictedClass = result?.time_classification?.predicted_class;
    if (!predictedClass) {
      continue;
    }

    classCounts[predictedClass] = (classCounts[predictedClass] || 0) + 1;
  }

  renderClassDistribution(classCounts);
}

function renderHistory(items, activeSessionId = state.currentSessionId) {
  els.historyList.innerHTML = "";

  if (!items.length) {
    els.historyEmpty.hidden = false;
    return;
  }

  els.historyEmpty.hidden = true;

  for (const item of items) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item";

    if (activeSessionId && item.id === activeSessionId) {
      button.classList.add("history-item--active");
    }

    button.addEventListener("click", () => {
      void openHistorySession(item.id);
    });

    const top = document.createElement("div");
    top.className = "history-item-top";

    const status = document.createElement("span");
    status.className = "history-status";
    status.textContent = mapStatus(item.status);

    const date = document.createElement("span");
    date.className = "history-date";
    date.textContent = formatDateTime(item.created_at);

    top.appendChild(status);
    top.appendChild(date);

    const title = document.createElement("div");
    title.className = "history-title";
    title.textContent = `${item.virus.name} · ${item.cell_line.name}`;

    const meta = document.createElement("div");
    meta.className = "history-meta";

    const metaFiles = document.createElement("div");
    metaFiles.textContent =
      `Файлы: ${item.images_count}, завершено: ${item.completed_images_count}, ошибки: ${item.failed_images_count}`;

    const metaId = document.createElement("div");
    metaId.textContent = `ID: ${shortId(item.id)}`;

    meta.appendChild(metaFiles);
    meta.appendChild(metaId);

    button.appendChild(top);
    button.appendChild(title);
    button.appendChild(meta);

    els.historyList.appendChild(button);
  }
}

function buildHistoryItemFromSessionDetail(session) {
  const progress = session?.progress || {};

  return {
    id: session.id,
    status: session.status,
    virus: session.virus,
    cell_line: session.cell_line,
    images_count: Number(progress.total_images || 0),
    completed_images_count: Number(progress.completed_images || 0),
    failed_images_count: Number(progress.failed_images || 0),
    notes: session.notes ?? null,
    error_message: session.error_message ?? null,
    created_at: session.created_at,
    queued_at: session.queued_at ?? null,
    started_at: session.started_at ?? null,
    finished_at: session.finished_at ?? null
  };
}

function upsertHistoryItem(item) {
  const existingIndex = state.historyItems.findIndex(
    (historyItem) => historyItem.id === item.id
  );

  if (existingIndex >= 0) {
    state.historyItems.splice(existingIndex, 1, item);
  } else {
    state.historyItems.unshift(item);
  }

  state.historyItems.sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  renderHistory(state.historyItems, state.currentSessionId);
}

async function openHistorySession(sessionId) {
  clearMessages();
  state.selectedFiles = [];
  if (els.imageInput) {
    els.imageInput.value = "";
  }

  try {
    setBusy(true);

    state.currentSessionId = sessionId;
    renderHistory(state.historyItems, sessionId);

    const session = await apiRequest(`/analysis-sessions/${sessionId}`);
    upsertHistoryItem(buildHistoryItemFromSessionDetail(session));

    const resultsPayload = await getSessionResults(sessionId);
    renderSessionSnapshot(session, resultsPayload.results || []);

    if (session.status === "queued" || session.status === "processing") {
      const finalSession = await pollSession(sessionId);
      const finalResultsPayload = await getSessionResults(sessionId);
      renderSessionSnapshot(
        finalResultsPayload.session || finalSession,
        finalResultsPayload.results || []
      );
    }

    await refreshHistory(sessionId);
  } catch (error) {
    showError(formatError(error));
  } finally {
    setBusy(false);
  }
}

function renderSessionSnapshot(session, results) {
  clearResultsGrid();

  if (!results.length) {
    els.resultsEmpty.hidden = false;
  } else {
    els.resultsEmpty.hidden = true;
  }

  updateCardsFromApiResults(results);
  updateSummary(session, results);

  const progress = session.progress || {
    total_images: 0,
    completed_images: 0,
    failed_images: 0,
    percent: 0
  };

  const doneCount =
    (progress.completed_images || 0) + (progress.failed_images || 0);

  const statusDetails =
    `${mapStatus(session.status)} · ${doneCount}/${progress.total_images} обработано`;

  setStatus(statusDetails, progress.percent || 0);

  if (session.status === "failed" && session.error_message) {
    showError(session.error_message);
  } else if (session.error_message) {
    showWarning(session.error_message);
  }
}

async function handleSubmit(event) {
  event.preventDefault();

  clearMessages();
  resetCardsForRun();

  const files = Array.from(els.imageInput.files || []);
  if (!files.length) {
    showError("Сначала выберите хотя бы один файл изображения.");
    return;
  }

  renderSelectionSummary(files.length);

  try {
    setBusy(true);
    setStatus("Создание сеанса...", 0);

    const session = await createSession();
    state.currentSessionId = session.id;
    renderHistory(state.historyItems, session.id);

    await refreshHistory(session.id);

    setStatus("Загрузка изображений...", 0);
    const uploadedImages = await uploadImages(session.id, files);
    updateCardsFromUploadedImages(uploadedImages);
    renderSelectionSummary(uploadedImages.length);

    setStatus("Постановка анализа в очередь...", 0);
    await startSession(session.id);

    const finalSession = await pollSession(session.id);
    const finalResultsPayload = await getSessionResults(session.id);

    updateCardsFromApiResults(finalResultsPayload.results || []);
    updateSummary(
      finalResultsPayload.session || finalSession,
      finalResultsPayload.results || []
    );

    if (finalSession.status === "failed") {
      showError(
        finalSession.error_message || "Сеанс завершился с ошибкой."
      );
      setStatus("Ошибка", finalSession.progress?.percent ?? 0);
      await refreshHistory(session.id);
      return;
    }

    if (finalResultsPayload.session?.error_message) {
      showWarning(finalResultsPayload.session.error_message);
    }

    setStatus("Анализ завершён", 100);
    await refreshHistory(session.id);
  } catch (error) {
    showError(formatError(error));
    setStatus("Ошибка", 0);
  } finally {
    setBusy(false);
  }
}

async function createSession() {
  return apiRequest("/analysis-sessions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getClientTokenHeaders()
    },
    body: JSON.stringify({
      virus_code: els.virusSelect.value,
      cell_line_code: els.cellLineSelect.value
    })
  });
}

async function uploadImages(sessionId, files) {
  const formData = new FormData();

  for (const file of files) {
    formData.append("files[]", file, file.name);
  }

  return apiRequest(`/analysis-sessions/${sessionId}/images`, {
    method: "POST",
    body: formData
  });
}

async function startSession(sessionId) {
  return apiRequest(`/analysis-sessions/${sessionId}/start`, {
    method: "POST"
  });
}

async function getSessionResults(sessionId) {
  return apiRequest(`/analysis-sessions/${sessionId}/results`);
}

async function pollSession(sessionId) {
  while (true) {
    const session = await apiRequest(`/analysis-sessions/${sessionId}`);
    const resultsPayload = await getSessionResults(sessionId);

    updateCardsFromApiResults(resultsPayload.results || []);
    updateSummary(session, resultsPayload.results || []);

    upsertHistoryItem(buildHistoryItemFromSessionDetail(session));

    const progress = session.progress || {
      total_images: 0,
      completed_images: 0,
      failed_images: 0,
      percent: 0
    };

    const doneCount =
      (progress.completed_images || 0) + (progress.failed_images || 0);

    const statusDetails =
      `${mapStatus(session.status)} · ${doneCount}/${progress.total_images} обработано`;

    setStatus(statusDetails, progress.percent);

    if (session.status === "completed" || session.status === "failed") {
      return session;
    }

    await sleep(1000);
  }
}

function setBusy(isBusy) {
  els.submitButton.disabled = isBusy;
  els.virusSelect.disabled = isBusy;
  els.cellLineSelect.disabled = isBusy;
  els.imageInput.disabled = isBusy;
  els.refreshHistoryButton.disabled = isBusy;
}

function setStatus(text, percent) {
  els.statusText.textContent = text;
  els.progressText.textContent = `${percent}%`;
  els.progressBar.style.width = `${percent}%`;
}

function clearMessages() {
  els.errorBox.classList.add("hidden");
  els.errorBox.textContent = "";

  els.warningBox.classList.add("hidden");
  els.warningBox.textContent = "";
}

function showError(message) {
  els.errorBox.textContent = message;
  els.errorBox.classList.remove("hidden");
}

function showWarning(message) {
  els.warningBox.textContent = message;
  els.warningBox.classList.remove("hidden");
}

function mapStatus(status) {
  const map = {
    created: "Создан",
    uploaded: "Загружено",
    queued: "В очереди",
    processing: "Обработка",
    completed: "Завершён",
    failed: "Ошибка",
    cancelled: "Отменён"
  };

  return map[status] || status;
}

function formatConfidence(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }

  return `${(num * 100).toFixed(1)}%`;
}

function formatDateTime(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString("ru-RU");
}

function shortId(value) {
  const text = String(value || "");
  return text.length > 8 ? text.slice(0, 8) : text;
}

function formatError(error) {
  if (error?.payload?.error?.message) {
    return error.payload.error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Неизвестная ошибка.";
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}