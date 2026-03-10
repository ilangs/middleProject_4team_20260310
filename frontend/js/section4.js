// ─────────────────────────────────────────────────────────
// section4.js  ─  성적 로그 (📊 score) 섹션
// ─────────────────────────────────────────────────────────

async function loadScoreLog() {
  const card = document.getElementById("score-log-card");
  if (!card) return;

  card.innerHTML = '<p style="color:#999; padding:10px;">로딩 중...</p>';

  try {
    const res = await apiFetch("/api/exam/results");
    const data = await res.json();
    renderScoreLog(card, data.results || []);
  } catch (e) {
    console.error("성적 데이터 로드 실패", e);
    card.innerHTML = '<p style="color:#c00; padding:10px;">성적 데이터를 불러오는데 실패했습니다.</p>';
  }
}

function renderScoreLog(card, results) {
  if (results.length === 0) {
    card.innerHTML = `
      <div class="score-dashboard">
        <p style="color:#999; font-size:18px; text-align:center; padding:40px 0;">
          아직 시험 기록이 없어요.<br>
          <strong>시험</strong> 메뉴에서 시험을 치면 여기에 기록이 쌓여요!
        </p>
      </div>`;
    return;
  }

  const scores = results.map(r => convertScoreTo100(r.score, r.total_questions));
  const latest = results[results.length - 1];
  const latestScore100 = convertScoreTo100(latest.score, latest.total_questions);
  const avgScore = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);

  card.innerHTML = `
    <div class="score-dashboard">

      <h2>시험 기록 요약</h2>
      <div class="score-summary">
        <div class="summary-card">
          <div class="summary-label">최근 시험 단원</div>
          <div class="summary-value">${escapeHtmlScore(latest.unit)}</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">최근 점수</div>
          <div class="summary-value">${latestScore100}점 / 100점</div>
        </div>
        <div class="summary-card">
          <div class="summary-label">평균 점수</div>
          <div class="summary-value">${avgScore}점 / 100점</div>
        </div>
      </div>

      <h2>점수 변화 그래프</h2>
      <div class="graph-card">
        ${buildScoreGraphSvg(scores)}
      </div>

      <h2>시험 기록 목록</h2>
      <div class="log-card">
        <table class="score-table">
          <thead>
            <tr>
              <th>날짜</th>
              <th>단원</th>
              <th>점수</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            ${results.map(r => buildScoreRow(r)).join("")}
          </tbody>
        </table>
      </div>

    </div>
  `;
}

function convertScoreTo100(score, totalQuestions) {
  const total = totalQuestions || 10;
  const eachPoint = 100 / total;
  const correctCount = Math.round((score / 100) * total);
  return Math.round(correctCount * eachPoint);
}

function buildScoreGraphSvg(scores) {
  if (!scores || scores.length === 0) return "<p>데이터가 없습니다.</p>";

  const W = 800, H = 260;
  const PAD_L = 65, PAD_R = 30, PAD_T = 20, PAD_B = 50;
  const graphW = W - PAD_L - PAD_R;
  const graphH = H - PAD_T - PAD_B;

  const yMin = 0, yMax = 100;
  const yScale = graphH / (yMax - yMin);

  const toX = (i) => PAD_L + (scores.length > 1
    ? i * (graphW / (scores.length - 1))
    : graphW / 2);
  const toY = (s) => PAD_T + graphH - (s - yMin) * yScale;

  let svg = `<svg width="100%" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;

  svg += `<line x1="${PAD_L}" y1="${PAD_T}" x2="${PAD_L}" y2="${PAD_T + graphH}" stroke="#999" stroke-width="2"/>`;
  svg += `<line x1="${PAD_L}" y1="${PAD_T + graphH}" x2="${PAD_L + graphW}" y2="${PAD_T + graphH}" stroke="#999" stroke-width="2"/>`;

  [20, 40, 60, 80, 100].forEach(val => {
    const y = toY(val);
    svg += `<text x="${PAD_L - 8}" y="${y + 5}" font-size="13" text-anchor="end" fill="#666">${val}</text>`;
    svg += `<line x1="${PAD_L}" y1="${y}" x2="${PAD_L + graphW}" y2="${y}" stroke="#eee" stroke-width="1" stroke-dasharray="4"/>`;
  });

  if (scores.length > 1) {
    const pts = scores.map((s, i) => `${toX(i)},${toY(s)}`).join(" ");
    svg += `<polyline fill="none" stroke="#222" stroke-width="3" points="${pts}"/>`;
  }

  scores.forEach((s, i) => {
    const x = toX(i);
    const y = toY(s);
    svg += `<circle cx="${x}" cy="${y}" r="6" fill="#222"/>`;
    svg += `<text x="${x}" y="${y - 11}" font-size="12" text-anchor="middle" fill="#333">${s}점</text>`;
    svg += `<text x="${x}" y="${PAD_T + graphH + 22}" font-size="13" text-anchor="middle" fill="#555">${i + 1}회</text>`;
  });

  svg += "</svg>";
  return svg;
}

function buildScoreRow(record) {
  const date = formatDateScore(record.timestamp);
  const unit = escapeHtmlScore(record.unit);
  const score100 = convertScoreTo100(record.score, record.total_questions);
  const badge = getStatusBadge(score100);

  return `<tr>
    <td>${date}</td>
    <td>${unit}</td>
    <td>${score100}점 / 100점</td>
    <td>${badge}</td>
  </tr>`;
}

function getStatusBadge(score) {
  if (score <= 50) return `<span class="status-badge danger">노력해야겠어요!</span>`;
  if (score <= 70) return `<span class="status-badge up">조금만 더 열심히 해보도록 해요!</span>`;
  if (score <= 90) return `<span class="status-badge good">정말 훌륭하네요!</span>`;
  return `<span class="status-badge stable">당신은 수학천재!</span>`;
}

function formatDateScore(timestamp) {
  if (!timestamp) return "-";
  return String(timestamp).slice(0, 10);
}

function escapeHtmlScore(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}