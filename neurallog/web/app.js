const outputPanel = document.getElementById("output-panel");
const API_BASE =
  window.location.protocol === "file:" ? "http://127.0.0.1:8000" : "";

function getConfig() {
  return {
    backend: document.getElementById("vector-backend").value,
    embedding_backend: document.getElementById("embedding-backend").value,
    embedding_model: document.getElementById("embedding-model").value || null,
    embedding_batch_size: toNumberOrNull(document.getElementById("batch-size").value),
    embedding_cache_path: document.getElementById("cache-path").value || null,
  };
}

function exportPayload() {
  return {
    token: document.getElementById("discord-token").value,
    token_kind: document.getElementById("token-kind").value,
    channel_id: document.getElementById("channel-id").value,
    output_path: document.getElementById("output-path").value || null,
    config: getConfig(),
  };
}

function toNumberOrNull(value) {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function basePayload() {
  return {
    export_path: document.getElementById("export-path").value,
    query: document.getElementById("query-input").value,
    limit: Number(document.getElementById("limit-input").value || 5),
    config: getConfig(),
  };
}

async function loadHealth() {
  const response = await fetch(`${API_BASE}/health`);
  const payload = await response.json();
  document.getElementById("health-status").textContent = payload.status;
  document.getElementById("health-index").textContent = String(payload.index_size);
  document.getElementById("health-backend").textContent = `${payload.backend} / ${payload.embedding_backend}`;
}

async function callApi(path, body) {
  outputPanel.innerHTML = `
    <div class="empty-state">
      <h3>Running workflow</h3>
      <p>NeuralLog is processing your request.</p>
    </div>
  `;
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await response.json();
    outputPanel.innerHTML = renderPayload(path, payload);
    await loadHealth();
  } catch (error) {
    outputPanel.innerHTML = renderError(error.message || String(error));
  }
}

function renderPayload(path, payload) {
  if (payload.detail) {
    return renderError(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  }

  if (path.includes("search")) return renderSearch(payload);
  if (path.includes("timeline")) return renderTimeline(payload);
  if (path.includes("compare-backends")) return renderCompare(payload);
  if (path.includes("evaluate")) return renderEvaluation(payload);
  if (path.includes("export-discord")) return renderExport(payload);
  if (path.includes("ingest")) return renderIngest(payload);
  return renderRaw("Response", payload);
}

function renderExport(payload) {
  return `
    <div class="result-stack">
      <div class="summary-strip">
        ${pill(`Channel ${payload.channel_id || "unknown"}`)}
        ${pill(`Token type: ${payload.token_kind || "unknown"}`)}
        ${pill(`Saved export`)}
      </div>
      <article class="result-card">
        <div class="section-title">Discord Export Complete</div>
        <h3>Export written to disk</h3>
        <div class="meta-row">
          ${badge(payload.output_path || "No output path")}
        </div>
        <p>
          NeuralLog can now ingest or search this exported JSON file. The Discord Export Path field
          has been updated to point to the new file.
        </p>
      </article>
      ${renderRaw("Raw export output", payload)}
    </div>
  `;
}

function renderIngest(payload) {
  return `
    <div class="result-stack">
      <div class="summary-strip">
        ${pill(`Messages indexed: ${payload.messages_indexed ?? 0}`)}
        ${pill(`Chunks created: ${payload.chunks_created ?? 0}`)}
        ${pill(`Index size: ${payload.index_size ?? 0}`)}
        ${pill(`Retrieval: ${payload.backend ?? "unknown"}`)}
        ${pill(`Embeddings: ${payload.embedding_backend ?? "unknown"}`)}
      </div>
      ${renderRaw("Raw ingest output", payload)}
    </div>
  `;
}

function renderSearch(payload) {
  const results = payload.results ?? [];
  return `
    <div class="result-stack">
      <div class="summary-strip">
        ${pill(`Matches: ${results.length}`)}
      </div>
      ${
        results.length
          ? results.map((result, index) => `
              <article class="result-card">
                <div class="section-title">Search Result ${index + 1}</div>
                <h3>${escapeHtml(result.channel_name || "Unknown channel")}</h3>
                <div class="meta-row">
                  ${badge(`Score ${formatNumber(result.score)}`)}
                  ${badge(shortDate(result.start_time))}
                  ${badge(participantText(result.participants))}
                </div>
                <p>${escapeHtml(result.preview || "No preview available.")}</p>
              </article>
            `).join("")
          : emptyResult("No matches found", "Try a broader query or a different embedding backend.")
      }
      ${renderRaw("Raw search output", payload)}
    </div>
  `;
}

function renderTimeline(payload) {
  const events = payload.events ?? [];
  return `
    <div class="result-stack">
      <div class="summary-strip">
        ${pill(`Timeline events: ${events.length}`)}
      </div>
      ${
        events.length
          ? events.map((event, index) => `
              <article class="result-card">
                <div class="section-title">Timeline Event ${index + 1}</div>
                <h3>${escapeHtml(event.title || "Untitled event")}</h3>
                <div class="meta-row">
                  ${badge(shortDate(event.timestamp))}
                  ${badge(escapeHtml(event.channel_name || "Unknown channel"))}
                  ${badge(participantText(event.participants))}
                </div>
                <p>${escapeHtml(event.summary || "No summary available.")}</p>
              </article>
            `).join("")
          : emptyResult("No timeline events found", "Try a more specific query tied to a debugging thread or milestone.")
      }
      ${renderRaw("Raw timeline output", payload)}
    </div>
  `;
}

function renderEvaluation(payload) {
  const summary = payload.summary ?? {};
  const perQuery = payload.per_query ?? [];
  return `
    <div class="result-stack">
      <div class="section-title">Evaluation Summary</div>
      <div class="metric-grid">
        ${metric("Queries", summary.queries_evaluated ?? 0)}
        ${metric("Mean Precision@K", formatNumber(summary.mean_precision_at_k))}
        ${metric("Mean Recall@K", formatNumber(summary.mean_recall_at_k))}
        ${metric("Mean Reciprocal Rank", formatNumber(summary.mean_reciprocal_rank))}
      </div>
      ${
        perQuery.map((item, index) => `
          <article class="result-card">
            <div class="section-title">Query ${index + 1}</div>
            <h3>${escapeHtml(item.query)}</h3>
            <div class="meta-row">
              ${badge(`Precision ${formatNumber(item.precision_at_k)}`)}
              ${badge(`Recall ${formatNumber(item.recall_at_k)}`)}
              ${badge(`MRR ${formatNumber(item.reciprocal_rank)}`)}
            </div>
            <p>Relevant messages: ${escapeHtml((item.relevant_message_ids || []).join(", ") || "none")}</p>
            <p>Retrieved messages: ${escapeHtml((item.retrieved_message_ids || []).join(", ") || "none")}</p>
          </article>
        `).join("")
      }
      ${renderRaw("Raw evaluation output", payload)}
    </div>
  `;
}

function renderCompare(payload) {
  const comparisons = payload.comparisons ?? [];
  const failures = payload.failures ?? [];
  return `
    <div class="result-stack">
      <div class="section-title">Backend Comparison</div>
      <div class="compare-grid">
        ${
          comparisons.length
            ? comparisons.map((item, index) => `
                <article class="result-card">
                  <div class="section-title">Rank ${index + 1}</div>
                  <h3>${escapeHtml(item.label)}</h3>
                  <div class="meta-row">
                    ${badge(`Embedding ${item.embedding_backend}`)}
                    ${badge(`Model ${item.embedding_model || "default"}`)}
                  </div>
                  <div class="metric-grid">
                    ${metric("Precision@K", formatNumber(item.summary?.mean_precision_at_k))}
                    ${metric("Recall@K", formatNumber(item.summary?.mean_recall_at_k))}
                    ${metric("MRR", formatNumber(item.summary?.mean_reciprocal_rank))}
                  </div>
                </article>
              `).join("")
            : emptyResult("No successful comparisons", "Every requested backend appears to be unavailable.")
        }
      </div>
      ${
        failures.length
          ? `
            <div class="section-title">Unavailable Backends</div>
            ${failures.map((item) => `
              <div class="failure-card">
                <strong>${escapeHtml(item.label)}</strong>
                <p>${escapeHtml(item.error)}</p>
              </div>
            `).join("")}
          `
          : ""
      }
      ${renderRaw("Raw comparison output", payload)}
    </div>
  `;
}

function renderRaw(title, payload) {
  return `
    <details class="raw-toggle">
      <summary>${escapeHtml(title)}</summary>
      <pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>
    </details>
  `;
}

function renderError(message) {
  const normalized = String(message || "");
  const hint =
    normalized.toLowerCase().includes("failed to fetch")
      ? "This usually means the page cannot reach the NeuralLog API. If you are on the file:// version, open http://127.0.0.1:8000 instead, or make sure the local server is running."
      : "";
  return `
    <div class="result-stack">
      <div class="failure-card">
        <strong>Request failed</strong>
        <p>${escapeHtml(message)}</p>
        ${hint ? `<p>${escapeHtml(hint)}</p>` : ""}
      </div>
    </div>
  `;
}

function pill(text) {
  return `<span class="summary-pill">${escapeHtml(text)}</span>`;
}

function badge(text) {
  return `<span class="meta-badge">${escapeHtml(text)}</span>`;
}

function metric(label, value) {
  return `
    <div class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </div>
  `;
}

function emptyResult(title, body) {
  return `
    <div class="empty-state">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(body)}</p>
    </div>
  `;
}

function participantText(participants) {
  if (!participants || !participants.length) return "No participants";
  if (participants.length === 1) return participants[0];
  return `${participants[0]} +${participants.length - 1}`;
}

function shortDate(value) {
  if (!value) return "Unknown time";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function formatNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return value ?? "n/a";
  return parsed.toFixed(3);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    const action = button.dataset.action;
    if (action === "ingest") {
      await callApi("/ingest/discord-export", {
        export_path: document.getElementById("export-path").value,
        config: getConfig(),
      });
      return;
    }

    if (action === "export-discord") {
      await callApi("/workflow/export-discord", exportPayload());
      const outputPath = document.getElementById("output-path").value;
      if (outputPath) {
        document.getElementById("export-path").value = outputPath;
      }
      return;
    }

    if (action === "search-export") {
      await callApi("/workflow/search-export", basePayload());
      return;
    }

    if (action === "timeline-export") {
      await callApi("/workflow/timeline-export", basePayload());
      return;
    }

    if (action === "evaluate") {
      await callApi("/workflow/evaluate", {
        export_path: document.getElementById("export-path").value,
        evaluation_set_path: document.getElementById("evaluation-path").value,
        limit: Number(document.getElementById("limit-input").value || 5),
        config: getConfig(),
      });
      return;
    }

    if (action === "compare-backends") {
      const specs = document
        .getElementById("compare-specs")
        .value
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      await callApi("/workflow/compare-backends", {
        export_path: document.getElementById("export-path").value,
        evaluation_set_path: document.getElementById("evaluation-path").value,
        specs,
        limit: Number(document.getElementById("limit-input").value || 5),
        skip_unavailable: true,
        config: getConfig(),
      });
    }
  });
});

loadHealth().catch((error) => {
  outputPanel.innerHTML = renderError(error.message || String(error));
});
