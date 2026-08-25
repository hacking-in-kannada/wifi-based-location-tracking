const dashboardState = {
  zone: "North Desk",
  motion: "Continuous motion",
  confidence: 0.86,
  signalQuality: 94,
  packetBuffer: 248,
  rssi: -41,
  amplitude: 0.91,
  latency: 38,
  rate: 118,
  direction: "east",
};

const eventFeed = [
  { time: "14:32:10", title: "Motion started", detail: "Packet variance crossed the motion threshold." },
  { time: "14:32:18", title: "Zone updated", detail: "Prediction shifted from North Desk to Center Path." },
  { time: "14:32:29", title: "Confidence rise", detail: "Three consecutive windows agreed on the same fingerprint." },
  { time: "14:32:41", title: "Motion stabilized", detail: "Filtered CSI now shows sustained human movement." },
];

const modelRows = [
  ["KNN", "91.2%", "0.90", "14 ms"],
  ["Random Forest", "93.8%", "0.92", "18 ms"],
  ["SVM", "89.7%", "0.88", "12 ms"],
  ["Neural Network", "95.4%", "0.95", "28 ms"],
];

const series = {
  rssi: [-45, -44, -43, -43, -42, -41, -41, -42, -40, -41, -39, -41],
  amp: [0.82, 0.84, 0.85, 0.86, 0.88, 0.9, 0.92, 0.91, 0.93, 0.92, 0.91, 0.91],
  latency: [44, 42, 40, 43, 41, 39, 38, 37, 40, 39, 38, 38],
  rate: [104, 107, 110, 109, 112, 114, 115, 116, 117, 118, 118, 118],
};

function $(selector) {
  return document.querySelector(selector);
}

function fmtPercent(value) {
  return `${Math.round(value * 100)}%`;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}

function renderSummary() {
  setText("zoneLabel", dashboardState.zone);
  setText("confidenceValue", fmtPercent(dashboardState.confidence));
  setText("motionState", dashboardState.motion);
  setText("signalQuality", `${dashboardState.signalQuality}%`);
  setText("packetBuffer", String(dashboardState.packetBuffer));
  setText("rssiValue", `${dashboardState.rssi} dBm`);
  setText("ampValue", dashboardState.amplitude.toFixed(2));
  setText("latencyValue", `${dashboardState.latency} ms`);
  setText("rateValue", `${dashboardState.rate} pps`);
  setText("blueprintLabel", `${dashboardState.zone} - ${fmtPercent(dashboardState.confidence)} confidence - movement trending ${dashboardState.direction}`);
}

function renderEvents() {
  const list = $("#eventList");
  list.innerHTML = eventFeed
    .map(
      (event) => `
        <article class="event">
          <span>${event.time}</span>
          <strong>${event.title}</strong>
          <p>${event.detail}</p>
        </article>`
    )
    .join("");
}

function renderModels() {
  const body = $("#modelTable");
  body.innerHTML = modelRows
    .map(
      (row) => `
        <tr>
          <td>${row[0]}</td>
          <td>${row[1]}</td>
          <td>${row[2]}</td>
          <td>${row[3]}</td>
        </tr>`
    )
    .join("");
}

function createSparkline(container, values, accent) {
  const width = 240;
  const height = 48;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const points = values
    .map((value, index) => {
      const x = index * step;
      const y = height - ((value - min) / range) * (height - 8) - 4;
      return `${x},${y}`;
    })
    .join(" ");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <polyline fill="none" stroke="${accent}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="${points}"></polyline>
    </svg>
  `;
}

function renderSparklines() {
  const accents = {
    rssi: "#57dbad",
    amp: "#7bb7ff",
    latency: "#ffd166",
    rate: "#92e3a9",
  };

  document.querySelectorAll(".sparkline").forEach((sparkline) => {
    const key = sparkline.dataset.series;
    createSparkline(sparkline, series[key], accents[key]);
  });
}

function drawTimeline() {
  const canvas = $("#timelineChart");
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(rect.width, 1);
  const height = 180;

  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  ctx.clearRect(0, 0, width, height);

  const values = [20, 35, 28, 42, 50, 44, 55, 62, 58, 69, 74, 70];
  const padding = 20;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const step = innerWidth / (values.length - 1);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  const gradient = ctx.createLinearGradient(0, 0, width, 0);
  gradient.addColorStop(0, "#57dbad");
  gradient.addColorStop(1, "#7bb7ff");

  ctx.strokeStyle = "rgba(255,255,255,0.07)";
  ctx.lineWidth = 1;
  for (let index = 0; index <= 4; index += 1) {
    const y = padding + (innerHeight / 4) * index;
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  ctx.beginPath();
  values.forEach((value, index) => {
    const x = padding + index * step;
    const y = padding + innerHeight - ((value - min) / range) * innerHeight;
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.strokeStyle = gradient;
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.fillStyle = "rgba(87, 219, 173, 0.18)";
  ctx.lineTo(width - padding, height - padding);
  ctx.lineTo(padding, height - padding);
  ctx.closePath();
  ctx.fill();

  values.forEach((value, index) => {
    const x = padding + index * step;
    const y = padding + innerHeight - ((value - min) / range) * innerHeight;
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fillStyle = "#edf3ff";
    ctx.fill();
    ctx.strokeStyle = "#57dbad";
    ctx.stroke();
  });
}

function attachButtons() {
  document.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      const label = button.textContent.trim();
      dashboardState.confidence = Math.min(0.97, dashboardState.confidence + 0.01);
      dashboardState.packetBuffer += 1;
      dashboardState.rate = Math.min(126, dashboardState.rate + 1);
      if (label === "Retrain Model") {
        dashboardState.motion = "Training batch queued";
      }
      renderSummary();
    });
  });
}

function tick() {
  const nextConfidence = 0.82 + Math.random() * 0.13;
  const zones = ["North Desk", "Center Path", "Window Seat", "South Cabinet"];
  const directions = ["east", "west", "north", "south"];
  const motions = ["No motion", "Motion started", "Continuous motion", "Motion stopped"];

  dashboardState.zone = zones[Math.floor(Math.random() * zones.length)];
  dashboardState.direction = directions[Math.floor(Math.random() * directions.length)];
  dashboardState.motion = motions[Math.floor(Math.random() * motions.length)];
  dashboardState.confidence = nextConfidence;
  dashboardState.signalQuality = 88 + Math.floor(Math.random() * 10);
  dashboardState.packetBuffer = 220 + Math.floor(Math.random() * 40);
  dashboardState.rssi = -46 + Math.floor(Math.random() * 8);
  dashboardState.amplitude = 0.83 + Math.random() * 0.1;
  dashboardState.latency = 32 + Math.floor(Math.random() * 10);
  dashboardState.rate = 106 + Math.floor(Math.random() * 18);

  renderSummary();
}

function init() {
  renderSummary();
  renderEvents();
  renderModels();
  renderSparklines();
  drawTimeline();
  attachButtons();
  tick();
  window.addEventListener("resize", drawTimeline);
  setInterval(tick, 4500);
}

document.addEventListener("DOMContentLoaded", init);
