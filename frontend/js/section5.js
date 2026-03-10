async function renderTokenPage() {
  const container = document.getElementById("page-token");

  container.innerHTML = `
    <h1 style="margin-bottom:20px;">⚡ 토큰 로그</h1>

    <div style="
      background:#f8f9fb;
      border:1px solid #e5e7eb;
      border-radius:16px;
      padding:24px;
      box-shadow:0 4px 12px rgba(0,0,0,0.06);
      max-width:1000px;
    ">
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:20px;
      ">
        <div style="font-size:20px; font-weight:700;">토큰 사용 대시보드</div>
      </div>

      <div id="token-card">불러오는 중...</div>
    </div>
  `;

  try {
    const res = await apiFetch("/api/token/logs");
    if (!res.ok) throw new Error("토큰 로그 조회 실패");

    const data = await res.json();

    const inputTokens = Number(data.prompt_tokens || 0);
    const outputTokens = Number(data.completion_tokens || 0);
    const totalTokens = Number(data.total_tokens || 0);
    const callCount = Number(data.call_count || 0);
    const costUsd = data.total_cost_usd || 0;
    const costKrw = data.total_cost_krw || 0;

    const totalForBar = inputTokens + outputTokens || 1;
    const inputWidth = (inputTokens / totalForBar) * 100;
    const outputWidth = (outputTokens / totalForBar) * 100;

    const history = (data.history || []).map(h => `
      <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        padding:10px 12px;
        margin-bottom:8px;
        background:#ffffff;
        border:1px solid #e5e7eb;
        border-radius:10px;
      ">
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="
            background:#4f7cff;
            color:#fff;
            font-size:12px;
            font-weight:700;
            padding:4px 10px;
            border-radius:8px;
          ">${h.action}</span>
          <span style="font-weight:600;">${h.total} tok</span>
        </div>
        <span style="color:#666; font-size:14px;">${h.ts}</span>
      </div>
    `).join("");

    document.getElementById("token-card").innerHTML = `
      <div style="display:flex; gap:16px; margin-bottom:18px; flex-wrap:wrap;">
        <div style="
          flex:1;
          min-width:180px;
          background:#ffffff;
          border:1px solid #e5e7eb;
          border-radius:12px;
          padding:18px;
          text-align:center;
        ">
          <div style="font-size:13px; color:#777; margin-bottom:8px;">총 토큰</div>
          <div style="font-size:32px; font-weight:800;">${totalTokens.toLocaleString()}</div>
        </div>

        <div style="
          flex:1;
          min-width:180px;
          background:#ffffff;
          border:1px solid #e5e7eb;
          border-radius:12px;
          padding:18px;
          text-align:center;
        ">
          <div style="font-size:13px; color:#777; margin-bottom:8px;">API 호출</div>
          <div style="font-size:32px; font-weight:800;">${callCount}</div>
        </div>
      </div>

      <div style="
        display:flex;
        justify-content:space-between;
        font-size:14px;
        font-weight:600;
        margin-bottom:8px;
      ">
        <span>입력 ${inputTokens.toLocaleString()}</span>
        <span>출력 ${outputTokens.toLocaleString()}</span>
      </div>

      <div style="
        display:flex;
        width:100%;
        height:14px;
        overflow:hidden;
        border-radius:999px;
        background:#e5e7eb;
        margin-bottom:16px;
      ">
        <div style="width:${inputWidth}%; background:#5b7cff;"></div>
        <div style="width:${outputWidth}%; background:#f28c52;"></div>
      </div>

      <div style="
        background:#fffaf0;
        border:1px solid #f2d6a2;
        border-radius:12px;
        padding:14px 16px;
        font-size:16px;
        font-weight:700;
        margin-bottom:20px;
      ">
        💰 예상 비용 : $ ${costUsd} (₩ ${Number(costKrw).toLocaleString()})
      </div>

      <div style="
        font-size:20px;
        font-weight:800;
        margin-bottom:12px;
      ">최근 기록</div>

      ${history || `<div style="color:#666;">기록 없음</div>`}
    `;
  } catch (err) {
    document.getElementById("token-card").innerHTML = `
      <div style="
        background:#fff5f5;
        border:1px solid #f5c2c7;
        color:#b02a37;
        border-radius:12px;
        padding:16px;
        font-weight:600;
      ">
        토큰 로그 불러오기 실패
      </div>
    `;
    console.error(err);
  }
}