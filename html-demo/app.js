"use strict";

const GRADE_NAMES = ["DR 없음", "경도", "중등도", "중증", "증식성"];
const CASES = [
  { key: "correct", label: "일치 사례", image: "19_left", actual: 0, predicted: 0, original: "assets/correct-input.jpg", sensitivity: "assets/correct-sensitivity.jpg", scores: [0.9912455677986145, 0.006852536927908659, 0.0006209035636857152, 0.001221047597937286, 0.00005986781252431683] },
  { key: "incorrect", label: "오분류 사례", image: "627_left", actual: 0, predicted: 1, original: "assets/incorrect-input.jpg", sensitivity: "assets/incorrect-sensitivity.jpg", scores: [0.007272066082805395, 0.989117443561554, 0.0036025280132889748, 0.000002074982603517128, 0.000005772307304141577] },
];
const CONFUSION = [[187, 13, 19, 3, 1], [21, 0, 0, 0, 0], [28, 6, 9, 1, 0], [4, 0, 3, 0, 0], [1, 0, 0, 1, 3]];
const RECALLS = [0.8385650224215246, 0, 0.20454545454545456, 0, 0.6];
const SUPPORT = [223, 21, 44, 7, 5];
let selectedCase = CASES[0];
const byId = (id) => document.getElementById(id);

function renderCase(nextCase) {
  selectedCase = nextCase;
  document.querySelectorAll(".demo-button").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.case === nextCase.key)));
  byId("result-grade").textContent = String(nextCase.predicted);
  byId("result-name").textContent = `${nextCase.predicted}등급 · ${GRADE_NAMES[nextCase.predicted]}`;
  byId("result-context").textContent = `${nextCase.label} · 실제 ${nextCase.actual}등급 / 저장 예측 ${nextCase.predicted}등급`;
  byId("result-image").src = nextCase.original;
  byId("result-image").alt = `${nextCase.label} ${nextCase.image}, 실제 ${nextCase.actual}등급 안저 이미지`;
  byId("view-original").setAttribute("aria-pressed", "true");
  byId("view-sensitivity").setAttribute("aria-pressed", "false");
  byId("sensitivity-note").textContent = "원본 이미지를 표시하고 있습니다.";
  const scoreList = byId("score-list");
  scoreList.replaceChildren();
  nextCase.scores.forEach((score, grade) => {
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `<span>${grade} · ${GRADE_NAMES[grade]}</span><span class="score-track"><span class="score-fill" style="display:block;width:${(score * 100).toFixed(4)}%"></span></span><span class="bar-value">${score.toFixed(6)}</span>`;
    scoreList.append(row);
  });
}

function setImageMode(mode) {
  const sensitivity = mode === "sensitivity";
  byId("view-original").setAttribute("aria-pressed", String(!sensitivity));
  byId("view-sensitivity").setAttribute("aria-pressed", String(sensitivity));
  byId("result-image").src = sensitivity ? selectedCase.sensitivity : selectedCase.original;
  byId("result-image").alt = sensitivity ? `${selectedCase.image} 사례의 4×4 가림 민감도 오버레이` : `${selectedCase.label} ${selectedCase.image}, 실제 ${selectedCase.actual}등급 안저 이미지`;
  byId("sensitivity-note").textContent = sensitivity ? "붉은색은 가렸을 때 선택 등급 점수가 낮아진 곳, 푸른색은 높아진 곳입니다." : "원본 이미지를 표시하고 있습니다.";
}

function renderCaseButtons() {
  CASES.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "demo-button";
    button.dataset.case = item.key;
    button.setAttribute("aria-pressed", "false");
    button.innerHTML = `<img src="${item.original}" width="320" height="320" alt=""><span class="demo-caption"><b>${item.label}</b><small>실제 ${item.actual} · 예측 ${item.predicted}</small></span>`;
    button.addEventListener("click", () => renderCase(item));
    byId("demo-list").append(button);
  });
}

function renderRecallBars() {
  RECALLS.forEach((value, grade) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<span>${grade}등급</span><span class="bar-track"><span class="bar-fill" style="display:block;width:${(value * 100).toFixed(2)}%"></span></span><span class="bar-value">${(value * 100).toFixed(1)}% · n=${SUPPORT[grade]}</span>`;
    byId("recall-bars").append(row);
  });
}

function renderConfusion() {
  const table = byId("model-matrix");
  const head = document.createElement("thead");
  head.innerHTML = `<tr><th>실제＼예측</th>${GRADE_NAMES.map((_, grade) => `<th>${grade}</th>`).join("")}</tr>`;
  const body = document.createElement("tbody");
  const maximum = Math.max(...CONFUSION.flat());
  CONFUSION.forEach((values, actual) => {
    const row = document.createElement("tr");
    row.innerHTML = `<th>${actual}</th>${values.map((value, predicted) => `<td style="--intensity:${Math.max(4, Math.round((value / maximum) * 72))}" title="실제 ${actual}등급, 예측 ${predicted}등급: ${value}안">${value}</td>`).join("")}`;
    body.append(row);
  });
  table.append(head, body);
}

document.addEventListener("DOMContentLoaded", () => {
  renderCaseButtons();
  renderRecallBars();
  renderConfusion();
  byId("view-original").addEventListener("click", () => setImageMode("original"));
  byId("view-sensitivity").addEventListener("click", () => setImageMode("sensitivity"));
  renderCase(CASES[0]);
});
