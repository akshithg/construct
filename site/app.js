const benchmarks = [
  { name: "Proportional", short: "P", kind: "linear", space: 2, generation: 1, evaluations: 2, mse: "0" },
  { name: "First-order low-pass", short: "LPF", kind: "linear", space: 1, generation: 1, evaluations: 1, mse: "0" },
  { name: "PI", short: "PI", kind: "linear", space: 4, generation: 1, evaluations: 4, mse: "5.79e−32" },
  { name: "Lead-lag", short: "LL", kind: "linear", space: 6, generation: 1, evaluations: 6, mse: "0" },
  { name: "Rate limiter", short: "RL", kind: "nonlinear", space: 2, generation: 1, evaluations: 2, mse: "0" },
  { name: "Deadband PI", short: "DB", kind: "nonlinear", space: 12, generation: 1, evaluations: 12, mse: "1.49e−32" },
  { name: "Filtered PID", short: "PID", kind: "linear", space: 48, generation: 1, evaluations: 48, mse: "7.40e−32" },
  { name: "Cascade PI", short: "CPI", kind: "linear", space: 144, generation: 1, evaluations: 134, mse: "2.60e−31" },
  { name: "Gain-scheduled PI", short: "GS", kind: "nonlinear", space: 720, generation: 2, evaluations: 426, mse: "7.83e−32" },
  { name: "Limited PID", short: "LIM", kind: "nonlinear", space: 4320, generation: 3, evaluations: 867, mse: "5.67e−32" },
  { name: "Anti-windup PID", short: "AW", kind: "nonlinear", space: 10080, generation: 4, evaluations: 1233, mse: "5.79e−32" },
];

const exampleGroups = [
  {
    name: "Fundamentals",
    description: "Core linear building blocks",
    items: [
      { name: "Proportional", use: "Basic regulation", tags: ["P", "stateless"] },
      { name: "First-order low-pass", use: "Sensor and command filtering", tags: ["filter", "1 state"] },
      { name: "PI", use: "Motor speed and process control", tags: ["PI", "1 state"] },
      { name: "Lead-lag", use: "Frequency-loop shaping", tags: ["filter", "1 state"] },
    ],
  },
  {
    name: "Stateful controls",
    description: "Memory and nested loops",
    items: [
      { name: "Rate limiter", use: "Actuator slew protection", tags: ["limits", "1 state"] },
      { name: "Filtered PID", use: "Servo and motion control", tags: ["PID", "2 states"] },
      { name: "Cascade PI", use: "Position and rate loops", tags: ["nested", "2 states"] },
    ],
  },
  {
    name: "Nonlinear controls",
    description: "Branches, limits, and anti-windup",
    items: [
      { name: "Deadband PI", use: "Backlash compensation", tags: ["PI", "deadband"] },
      { name: "Gain-scheduled PI", use: "Operating-point adaptation", tags: ["schedule", "branch"] },
      { name: "Limited PID", use: "Saturated feedforward", tags: ["PID", "saturation"] },
      { name: "Anti-windup PID", use: "Integrator recovery after saturation", tags: ["PID", "anti-windup"] },
    ],
  },
];

const formatNumber = new Intl.NumberFormat("en-US");

function renderChart() {
  const chart = document.querySelector("#space-chart");
  if (!chart) return;

  const maxLog = Math.log10(Math.max(...benchmarks.map(({ space }) => space))) + 1;
  chart.innerHTML = benchmarks
    .map((item) => {
      const height = 7 + ((Math.log10(item.space) + 1) / maxLog) * 86;
      return `
        <div class="bar-item" style="--bar-height: ${height}%">
          <div class="bar" style="height: ${height}%"></div>
          <button class="bar-button" type="button" aria-label="${item.name}: ${formatNumber.format(item.space)} candidate mappings"></button>
          <span class="chart-tooltip">${item.name}<br>${formatNumber.format(item.space)} mappings</span>
          <span class="bar-label">${item.short}</span>
        </div>`;
    })
    .join("");
}

function renderTable(filter = "all") {
  const body = document.querySelector("#benchmark-rows");
  if (!body) return;

  const rows = filter === "all" ? benchmarks : benchmarks.filter(({ kind }) => kind === filter);
  body.innerHTML = rows
    .map(
      (item) => `
        <tr>
          <td>${item.name}</td>
          <td><span class="class-pill ${item.kind}">${item.kind}</span></td>
          <td>${formatNumber.format(item.space)}</td>
          <td>${item.generation}</td>
          <td>${formatNumber.format(item.evaluations)}</td>
          <td>${item.mse}</td>
          <td><span class="result-pill">✓ Exact</span></td>
        </tr>`,
    )
    .join("");
}

function bindFilters() {
  document.querySelectorAll(".filter").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".filter").forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle("active", active);
        candidate.setAttribute("aria-pressed", String(active));
      });
      renderTable(button.dataset.filter);
    });
  });
}

function renderExamples() {
  const grid = document.querySelector("#example-grid");
  if (!grid) return;

  grid.innerHTML = exampleGroups
    .map(
      (group, index) => `
        <section class="example-group reveal" aria-labelledby="example-group-${index}">
          <div class="example-group-header">
            <span class="example-index">${String(index + 1).padStart(2, "0")}</span>
            <div>
              <h3 id="example-group-${index}">${group.name}</h3>
              <p>${group.description}</p>
            </div>
          </div>
          <ul class="example-list">
            ${group.items
              .map(
                (item) => `
                  <li class="example-row">
                    <div class="example-main">
                      <h4>${item.name}</h4>
                      <p>${item.use}</p>
                    </div>
                    <div class="tags">${item.tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}</div>
                  </li>`,
              )
              .join("")}
          </ul>
        </section>`,
    )
    .join("");
}

function bindCopyButton() {
  const button = document.querySelector("#copy-command");
  if (!button) return;

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText("uv run construct-demo run-all");
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = "Copy";
      }, 1400);
    } catch {
      button.textContent = "Select command";
    }
  });
}

function observeReveals() {
  const elements = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window)) {
    elements.forEach((element) => element.classList.add("visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.08 },
  );
  elements.forEach((element) => observer.observe(element));
}

renderChart();
renderTable();
renderExamples();
bindFilters();
bindCopyButton();
observeReveals();
