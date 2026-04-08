const API_BASE_URL =
  window.APP_CONFIG?.API_BASE_URL || "http://127.0.0.1:8000/api/v1";

const state = {
  supportMatrix: null,
  previewUrl: null,
  currentSessionId: null
};

const els = {};

document.addEventListener("DOMContentLoaded", init);

function init() {
  els.form = document.getElementById("analysisForm");
  els.virusSelect = document.getElementById("virusSelect");
  els.cellLineSelect = document.getElementById("cellLineSelect");
  els.imageInput = document.getElementById("imageInput");
  els.submitButton = document.getElementById("submitButton");

  els.previewPlaceholder = document.getElementById("previewPlaceholder");
  els.previewImage = document.getElementById("previewImage");

  els.statusText = document.getElementById("statusText");
  els.progressBar = document.getElementById("progressBar");
  els.progressText = document.getElementById("progressText");

  els.resultFilename = document.getElementById("resultFilename");
  els.resultClass = document.getElementById("resultClass");
  els.resultConfidence = document.getElementById("resultConfidence");

  els.errorBox = document.getElementById("errorBox");
  els.warningBox = document.getElementById("warningBox");

  els.virusSelect.addEventListener("change", populateCellLines);
  els.imageInput.addEventListener("change", handleImageSelection);
  els.form.addEventListener("submit", handleSubmit);

  loadSupportMatrix().catch((error) => {
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

async function loadSupportMatrix() {
  const data = await apiRequest("/support-matrix");
  state.supportMatrix = data;

  populateViruses();
  populateCellLines();
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
  resetResult();

  const file = els.imageInput.files?.[0];
  updatePreview(file);
}

function updatePreview(file) {
  if (state.previewUrl) {
    URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
  }

  els.previewImage.hidden = true;
  els.previewImage.removeAttribute("src");
  els.previewPlaceholder.hidden = false;
  els.previewPlaceholder.textContent = "Предпросмотр появится после выбора файла";

  if (!file) {
    return;
  }

  state.previewUrl = URL.createObjectURL(file);
  els.previewImage.src = state.previewUrl;
  els.previewImage.hidden = false;
  els.previewPlaceholder.hidden = true;

  els.previewImage.onerror = () => {
    els.previewImage.hidden = true;
    els.previewPlaceholder.hidden = false;
    els.previewPlaceholder.textContent =
      `Предпросмотр недоступен для файла "${file.name}"`;
  };
}

async function handleSubmit(event) {
  event.preventDefault();

  clearMessages();
  resetResult();

  const file = els.imageInput.files?.[0];
  if (!file) {
    showError("Сначала выберите файл изображения.");
    return;
  }

  try {
    setBusy(true);
    setStatus("Создание сеанса...", 0);

    const session = await createSession();
    state.currentSessionId = session.id;

    setStatus("Загрузка изображения...", 0);
    await uploadSingleImage(session.id, file);

    setStatus("Постановка анализа в очередь...", 0);
    await startSession(session.id);

    const finalSession = await pollSession(session.id);

    if (finalSession.status === "failed") {
      throw new Error(
        finalSession.error_message || "Сеанс завершился с ошибкой."
      );
    }

    setStatus("Чтение результата...", 100);
    const resultsPayload = await getSessionResults(session.id);
    renderResults(resultsPayload);

    setStatus("Анализ завершён", 100);
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
      "X-Client-Token": getClientToken()
    },
    body: JSON.stringify({
      virus_code: els.virusSelect.value,
      cell_line_code: els.cellLineSelect.value
    })
  });
}

async function uploadSingleImage(sessionId, file) {
  const formData = new FormData();
  formData.append("files[]", file, file.name);

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

    const progress = session.progress || {
      total_images: 0,
      completed_images: 0,
      failed_images: 0,
      percent: 0
    };

    const statusLabel = mapStatus(session.status);
    const statusDetails =
      `${statusLabel} · ${progress.completed_images}/${progress.total_images} завершено`;

    setStatus(statusDetails, progress.percent);

    if (session.status === "completed" || session.status === "failed") {
      return session;
    }

    await sleep(1000);
  }
}

function renderResults(payload) {
  const firstResult = payload.results?.[0];

  if (!firstResult) {
    showError("Сервис не вернул результат по изображению.");
    return;
  }

  els.resultFilename.textContent = firstResult.original_filename || "—";

  if (firstResult.error_message) {
    showError(firstResult.error_message);
    return;
  }

  const tc = firstResult.time_classification;

  if (!tc) {
    showError("Результат классификации отсутствует.");
    return;
  }

  els.resultClass.textContent = tc.predicted_class;
  els.resultConfidence.textContent = formatConfidence(tc.confidence);

  const isLowConfidence =
    tc.confidence_flag === "low" ||
    firstResult.warnings?.includes("low_confidence");

  if (isLowConfidence) {
    showWarning(
      "Низкая уверенность предсказания. Интерпретируйте результат осторожно."
    );
  }
}

function setBusy(isBusy) {
  els.submitButton.disabled = isBusy;
  els.virusSelect.disabled = isBusy;
  els.cellLineSelect.disabled = isBusy;
  els.imageInput.disabled = isBusy;
}

function setStatus(text, percent) {
  els.statusText.textContent = text;
  els.progressText.textContent = `${percent}%`;
  els.progressBar.style.width = `${percent}%`;
}

function resetResult() {
  els.resultFilename.textContent = "—";
  els.resultClass.textContent = "—";
  els.resultConfidence.textContent = "—";
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
    queued: "В очереди",
    processing: "Обработка",
    completed: "Завершён",
    failed: "Ошибка"
  };

  return map[status] || status;
}

function formatConfidence(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
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