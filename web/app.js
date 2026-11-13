"use strict";

const GRADE_NAMES = ["DR 없음", "경도", "중등도", "중증", "증식성"];
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

const state = {
  examples: [],
  filteredExamples: [],
  caseIndex: 0,
  selectedGap: "all",
  uploadUrl: null,
  uploadFile: null,
  sensitivityUrl: null,
  imageMode: "original",
  demoExamples: [],
};

const byId = (id) => document.getElementById(id);
const formatNumber = (value) => new Intl.NumberFormat("ko-KR").format(value);
const formatPercent = (value, digits = 1) => `${(value * 100).toFixed(digits)}%`;

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "결과를 불러오지 못했습니다.");
  return payload;
}

function setText(id, value) {
  byId(id).textContent = value;
}

function activatePanel(panelName, updateHash = true) {
  document.querySelectorAll("[role=tab]").forEach((tab) => {
    const active = tab.dataset.panel === panelName;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
  });
  ["analysis", "model"].forEach((name) => {
    byId(`panel-${name}`).hidden = name !== panelName;
  });
  if (updateHash) history.replaceState(null, "", `#${panelName}`);
}

function setupTabs() {
  const tabs = [...document.querySelectorAll("[role=tab]")];
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activatePanel(tab.dataset.panel));
    tab.addEventListener("keydown", (event) => {
      const keys = ["ArrowLeft", "ArrowRight", "Home", "End"];
      if (!keys.includes(event.key)) return;
      event.preventDefault();
      const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : event.key === "ArrowRight" ? (index + 1) % tabs.length : (index - 1 + tabs.length) % tabs.length;
      const nextTab = tabs[nextIndex];
      activatePanel(nextTab.dataset.panel);
      nextTab.focus();
    });
  });
  activatePanel(location.hash === "#model" ? "model" : "analysis", false);
}

function setupRovingKeyboard(container) {
  container.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...container.querySelectorAll("button:not(:disabled)")];
    const index = buttons.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : event.key === "ArrowRight" ? (index + 1) % buttons.length : (index - 1 + buttons.length) % buttons.length;
    buttons[nextIndex].focus();
    buttons[nextIndex].click();
  });
}

function renderBars(container, values, labels, formatter = formatNumber) {
  container.replaceChildren();
  const maximum = Math.max(...values, 1);
  values.forEach((value, index) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<span>${labels[index]}</span><span class="bar-track"><span class="bar-fill" style="display:block;width:${(value / maximum) * 100}%"></span></span><span class="bar-value">${formatter(value, index)}</span>`;
    container.append(row);
  });
}

function renderMatrix(tableId, matrix, rowPrefix, columnPrefix) {
  const table = byId(tableId);
  table.replaceChildren();
  const maximum = Math.max(...matrix.flat(), 1);
  const head = document.createElement("thead");
  head.innerHTML = `<tr><th>${rowPrefix}＼${columnPrefix}</th>${GRADE_NAMES.map((_, grade) => `<th>${grade}</th>`).join("")}</tr>`;
  const body = document.createElement("tbody");
  matrix.forEach((rowValues, rowGrade) => {
    const row = document.createElement("tr");
    row.innerHTML = `<th>${rowGrade}</th>${rowValues.map((value, columnGrade) => {
      const intensity = Math.max(4, Math.round((value / maximum) * 72));
      return `<td style="--intensity:${intensity}" title="${rowPrefix} ${rowGrade}등급, ${columnPrefix} ${columnGrade}등급: ${formatNumber(value)}">${formatNumber(value)}</td>`;
    }).join("")}`;
    body.append(row);
  });
  table.append(head, body);
}

function renderAnalysis(summary) {
  setText("agreement-value", formatPercent(summary.exact_agreement));
  setText("agreement-context", `95% CI ${formatPercent(summary.exact_agreement_ci95[0])}–${formatPercent(summary.exact_agreement_ci95[1])}`);
  setText("discordant-value", formatNumber(summary.discordant_count));
  setText("discordant-context", `${summary.discordant_percentage.toFixed(1)}% · ${formatNumber(summary.patient_count)}명 기준`);
  setText("kappa-value", summary.weighted_kappa.toFixed(3));
  setText("affected-value", formatPercent(summary.affected_exact_agreement));
  setText("affected-context", `${formatNumber(summary.affected_patient_count)}명 기준`);
  renderBars(byId("difference-bars"), summary.difference_counts, summary.difference_counts.map((_, gap) => `차이 ${gap}`));
  renderBars(byId("class-bars"), summary.class_counts, GRADE_NAMES.map((name, grade) => `${grade} · ${name}`));
  renderMatrix("cross-matrix", summary.cross_matrix, "왼쪽", "오른쪽");
}

function imageUrl(name) {
  return `/images/${encodeURIComponent(name)}.jpg`;
}

function updateCaseControls() {
  const count = state.filteredExamples.length;
  byId("case-prev").disabled = count < 2;
  byId("case-next").disabled = count < 2;
  const label = state.selectedGap === "all" ? "전체 등급 차이" : `등급 차이 ${state.selectedGap}`;
  setText("gap-filter-status", `${label} · ${formatNumber(count)}개 실제 사례`);
}

function renderCase() {
  const pair = state.filteredExamples[state.caseIndex];
  if (!pair) {
    setText("case-title", "조건에 맞는 사례가 없습니다");
    setText("case-index", "다른 등급 차이를 선택해 주세요");
    ["left-image", "right-image"].forEach((id) => { byId(id).hidden = true; });
    return;
  }
  const left = byId("left-image");
  const right = byId("right-image");
  [left, right].forEach((image) => image.classList.add("is-changing"));
  const update = () => {
    left.src = imageUrl(pair.left_image);
    right.src = imageUrl(pair.right_image);
    left.alt = `ID ${pair.patient_id}의 왼쪽 안저 이미지, 제공 라벨 ${pair.left_grade}등급`;
    right.alt = `ID ${pair.patient_id}의 오른쪽 안저 이미지, 제공 라벨 ${pair.right_grade}등급`;
    setText("left-grade", pair.left_grade);
    setText("right-grade", pair.right_grade);
    setText("left-grade-name", GRADE_NAMES[pair.left_grade]);
    setText("right-grade-name", GRADE_NAMES[pair.right_grade]);
    setText("case-title", `ID ${pair.patient_id} · 등급 차이 ${pair.difference}`);
    setText("case-index", `${state.caseIndex + 1} / ${state.filteredExamples.length} · 실제 제공 라벨`);
    [left, right].forEach((image) => image.classList.remove("is-changing"));
  };
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) update();
  else window.setTimeout(update, 80);
}

function changeCase(offset) {
  if (!state.filteredExamples.length) return;
  state.caseIndex = (state.caseIndex + offset + state.filteredExamples.length) % state.filteredExamples.length;
  renderCase();
}

function selectGap(gap) {
  state.selectedGap = gap;
  state.filteredExamples = gap === "all" ? [...state.examples] : state.examples.filter((pair) => pair.difference === Number(gap));
  state.caseIndex = 0;
  document.querySelectorAll("[data-gap]").forEach((button) => {
    const selected = button.dataset.gap === gap;
    button.setAttribute("aria-pressed", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  updateCaseControls();
  renderCase();
}

async function loadAssignmentOne() {
  try {
    const [summary, examples] = await Promise.all([fetchJson("/api/analysis"), fetchJson("/api/examples")]);
    renderAnalysis(summary);
    state.examples = Array.isArray(examples.pairs) ? examples.pairs : [];
    selectGap("all");
  } catch (error) {
    const notice = byId("case-error");
    notice.textContent = error.message;
    notice.hidden = false;
    setText("agreement-context", "분석 생성 단계를 확인해 주세요");
  }
}

function renderModelMetrics(metrics) {
  setText("metric-accuracy", formatPercent(metrics.test.accuracy));
  setText("metric-qwk", metrics.test.qwk.toFixed(3));
  setText("metric-f1", metrics.test.macro_f1.toFixed(3));
  setText("metric-size", formatNumber(metrics.dataset.test));
  setText("model-note", `${metrics.selected_model} 모델을 검증 세트에서 선택한 뒤, 분리해 둔 최종평가 이미지 ${formatNumber(metrics.dataset.test)}장에 한 번 평가했습니다.`);
  const supports = metrics.test.confusion_matrix.map((row) => row.reduce((sum, value) => sum + value, 0));
  const recalls = GRADE_NAMES.map((_, grade) => metrics.test.recall_by_grade[String(grade)]);
  renderBars(byId("recall-bars"), recalls, GRADE_NAMES.map((name, grade) => `${grade} · ${name}`), (value, grade) => `${formatPercent(value)} · n=${supports[grade]}`);
  renderMatrix("model-matrix", metrics.test.confusion_matrix, "실제", "예측");
  const baseline = metrics.majority_baseline_test;
  setText("baseline-accuracy", formatPercent(baseline.accuracy));
  setText("baseline-qwk", baseline.qwk.toFixed(3));
  setText("baseline-f1", baseline.macro_f1.toFixed(3));
  setText("baseline-summary", `모델 정확도는 기준선보다 ${(baseline.accuracy - metrics.test.accuracy) * 100 > 0 ? "낮지만" : "높고"}, QWK ${metrics.test.qwk.toFixed(3)}와 macro-F1 ${metrics.test.macro_f1.toFixed(3)}로 등급 구분 능력을 확인합니다.`);
}

function renderProvenance(provenance) {
  const body = byId("split-table").querySelector("tbody");
  body.replaceChildren();
  const names = { train: "학습", validation: "검증", test: "최종평가" };
  provenance.splits.forEach((split) => {
    const row = document.createElement("tr");
    row.innerHTML = `<th>${names[split.split] || split.split}</th><td>${formatNumber(split.patients)}</td><td>${formatNumber(split.images)}</td><td>${split.class_counts.map(formatNumber).join(" · ")}</td>`;
    body.append(row);
  });
  setText("integrity-images", `${formatNumber(provenance.integrity.verified_originals)} / ${formatNumber(provenance.integrity.requested_images)}`);
  setText("integrity-overlap", `${formatNumber(provenance.integrity.patient_split_overlap)}명`);
  setText("integrity-test-use", `${formatNumber(provenance.run.final_test_evaluations)}회`);
  const hash = provenance.manifest_sha256;
  const hashElement = byId("manifest-hash");
  hashElement.textContent = `${hash.slice(0, 12)}…`;
  hashElement.title = hash;
}

function validateFile(file) {
  if (!file) return "이미지를 선택해 주세요.";
  if (!["image/jpeg", "image/png"].includes(file.type)) return "JPEG 또는 PNG 이미지만 선택할 수 있습니다.";
  if (file.size > MAX_UPLOAD_BYTES) return "이미지 크기는 10MB 이하여야 합니다.";
  return "";
}

function showUploadError(message) {
  const error = byId("upload-error");
  error.textContent = message;
  error.hidden = !message;
}

function previewFile(file) {
  if (state.uploadUrl) URL.revokeObjectURL(state.uploadUrl);
  state.uploadUrl = URL.createObjectURL(file);
  state.uploadFile = file;
  const preview = byId("upload-preview");
  preview.src = state.uploadUrl;
  preview.hidden = false;
  byId("predict-button").disabled = false;
}

function setImageMode(mode) {
  const hasSensitivity = Boolean(state.sensitivityUrl);
  state.imageMode = mode === "sensitivity" && hasSensitivity ? "sensitivity" : "original";
  const showSensitivity = state.imageMode === "sensitivity";
  byId("result-image").hidden = showSensitivity;
  byId("sensitivity-image").hidden = !showSensitivity;
  const original = byId("view-original");
  const sensitivity = byId("view-sensitivity");
  original.setAttribute("aria-pressed", String(!showSensitivity));
  sensitivity.setAttribute("aria-pressed", String(showSensitivity));
  original.tabIndex = showSensitivity ? -1 : 0;
  sensitivity.tabIndex = showSensitivity ? 0 : -1;
}

function renderPrediction(prediction, demo = null) {
  byId("result-placeholder").hidden = true;
  byId("result-content").hidden = false;
  setText("result-grade", prediction.grade);
  setText("result-name", `${prediction.grade}등급 · ${GRADE_NAMES[prediction.grade]}`);
  setText("result-context", demo ? `실제 라벨 ${demo.actual}등급 · 현재 모델 예측 ${prediction.grade}등급` : "가장 높은 모델 출력 점수의 등급");
  byId("result-image").src = state.uploadUrl;
  const scores = byId("score-list");
  scores.replaceChildren();
  prediction.scores.forEach((score, grade) => {
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `<span>${grade} · ${GRADE_NAMES[grade]}</span><span class="score-track"><span class="score-fill" style="display:block;width:${Math.max(0, Math.min(100, score * 100))}%"></span></span><span class="bar-value">${score.toFixed(3)}</span>`;
    scores.append(row);
  });
  state.sensitivityUrl = prediction.sensitivity_image || null;
  const sensitivityButton = byId("view-sensitivity");
  sensitivityButton.disabled = !state.sensitivityUrl;
  if (state.sensitivityUrl) byId("sensitivity-image").src = state.sensitivityUrl;
  setText("sensitivity-note", state.sensitivityUrl ? "붉은색은 가렸을 때 선택 등급 점수가 낮아진 곳, 푸른색은 높아진 곳입니다. 병변 위치 정답이 아닙니다." : "이 실행에서는 가림 민감도를 생성하지 못했습니다.");
  setImageMode("original");
}

async function runPrediction(file, demo = null, trigger = null) {
  const validationError = validateFile(file);
  if (validationError) {
    showUploadError(validationError);
    return;
  }
  const button = byId("predict-button");
  button.disabled = true;
  button.textContent = "모델 분석 중…";
  if (trigger) trigger.setAttribute("aria-busy", "true");
  showUploadError("");
  try {
    const response = await fetch("/api/predict", { method: "POST", headers: { "content-type": file.type }, body: file });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "이미지를 분석하지 못했습니다.");
    renderPrediction(payload, demo);
  } catch (error) {
    showUploadError(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "등급 분석하기";
    if (trigger) trigger.removeAttribute("aria-busy");
  }
}

async function runDemo(example, button) {
  try {
    const response = await fetch(imageUrl(example.image));
    if (!response.ok) throw new Error("예제 원본을 불러오지 못했습니다.");
    const blob = await response.blob();
    const file = new File([blob], `${example.image}.jpg`, { type: "image/jpeg" });
    previewFile(file);
    await runPrediction(file, example, button);
  } catch (error) {
    showUploadError(error.message);
  }
}

function renderDemoExamples(examples) {
  const list = byId("demo-list");
  list.replaceChildren();
  if (!examples.length) {
    const empty = document.createElement("p");
    empty.className = "filter-status";
    empty.textContent = "준비된 최종평가 예제가 없습니다.";
    list.append(empty);
    return;
  }
  examples.forEach((example) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "demo-button";
    const kind = example.kind === "correct" ? "일치 사례" : "오분류 사례";
    button.innerHTML = `<img src="${imageUrl(example.image)}" alt="최종평가 예제 ${example.image}"><span>${kind} · 실제 ${example.actual} / 기록 예측 ${example.predicted}</span>`;
    button.addEventListener("click", () => runDemo(example, button));
    list.append(button);
  });
}

function setupUpload() {
  const input = byId("image-file");
  const form = byId("predict-form");
  const well = byId("upload-well");
  let dragDepth = 0;
  input.addEventListener("change", () => {
    const file = input.files[0];
    const error = validateFile(file);
    showUploadError(error);
    if (error) {
      state.uploadFile = null;
      byId("predict-button").disabled = true;
      return;
    }
    previewFile(file);
  });
  well.addEventListener("dragenter", (event) => { event.preventDefault(); dragDepth += 1; well.classList.add("is-dragging"); });
  well.addEventListener("dragover", (event) => { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = "copy"; });
  well.addEventListener("dragleave", (event) => { event.preventDefault(); dragDepth = Math.max(0, dragDepth - 1); if (dragDepth === 0) well.classList.remove("is-dragging"); });
  well.addEventListener("drop", (event) => {
    event.preventDefault();
    dragDepth = 0;
    well.classList.remove("is-dragging");
    const file = event.dataTransfer?.files[0];
    const error = validateFile(file);
    showUploadError(error);
    if (error) return;
    previewFile(file);
  });
  form.addEventListener("submit", (event) => { event.preventDefault(); runPrediction(state.uploadFile); });
}

function setupImageErrors() {
  ["left-image", "right-image"].forEach((id) => {
    byId(id).addEventListener("error", (event) => {
      event.currentTarget.hidden = true;
      const notice = byId("case-error");
      notice.textContent = "선택한 사례 이미지를 아직 불러올 수 없습니다. 데이터 준비 단계를 확인해 주세요.";
      notice.hidden = false;
    });
    byId(id).addEventListener("load", (event) => { event.currentTarget.hidden = false; byId("case-error").hidden = true; });
  });
}

async function loadModelEvidence() {
  const [metrics, provenance, examples] = await Promise.allSettled([fetchJson("/api/model-metrics"), fetchJson("/api/provenance"), fetchJson("/api/model-examples")]);
  if (metrics.status === "fulfilled") renderModelMetrics(metrics.value);
  else { setText("model-note", metrics.reason.message); byId("model-note").classList.add("caution"); }
  if (provenance.status === "fulfilled") renderProvenance(provenance.value);
  if (examples.status === "fulfilled") { state.demoExamples = Array.isArray(examples.value) ? examples.value : []; renderDemoExamples(state.demoExamples); }
  else renderDemoExamples([]);
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupRovingKeyboard(byId("gap-filter"));
  setupRovingKeyboard(byId("view-original").parentElement);
  setupUpload();
  setupImageErrors();
  byId("case-prev").addEventListener("click", () => changeCase(-1));
  byId("case-next").addEventListener("click", () => changeCase(1));
  byId("gap-filter").addEventListener("click", (event) => { const button = event.target.closest("[data-gap]"); if (button) selectGap(button.dataset.gap); });
  byId("view-original").addEventListener("click", () => setImageMode("original"));
  byId("view-sensitivity").addEventListener("click", () => setImageMode("sensitivity"));
  loadAssignmentOne();
  loadModelEvidence();
});
