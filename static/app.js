// makes sure html is ready before running any javascript
document.addEventListener("DOMContentLoaded", function () {
  setupSearchPage();
});

// sets up search page actions and UI behavior
function setupSearchPage() {
  var qEl = document.getElementById("q");
  var btn = document.getElementById("btn");
  var resultsEl = document.getElementById("results");
  var detailsEl = document.getElementById("details");
  var insightsEl = document.getElementById("insights");

  // if key elements are missing, stop safely
  if (!qEl || !btn || !resultsEl || !detailsEl || !insightsEl) {
    return;
  }

  // loads dashboard insights on page load
  loadInsights();

  // button click search
  btn.addEventListener("click", function () {
    doSearch();
  });

  // enter key search
  qEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      doSearch();
    }
  });

  // loads insights and handles request errors
  function loadInsights() {
    insightsEl.innerHTML = "Loading...";

    fetch("/api/insights")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Could not load insights.");
        }
        return response.json();
      })
      .then(function (data) {
        insightsEl.innerHTML = `
          <div class="insight-grid">
            <div class="insight">
              <div class="insight-k">Total records</div>
              <div class="insight-v">${escapeHtml(data.total_records)}</div>
            </div>
            <div class="insight">
              <div class="insight-k">Total amount</div>
              <div class="insight-v">$${escapeHtml(data.total_amount)}</div>
            </div>
            <div class="insight">
              <div class="insight-k">Missing email</div>
              <div class="insight-v">${escapeHtml(data.missing_email_pct)}%</div>
            </div>
            <div class="insight">
              <div class="insight-k">Missing phone</div>
              <div class="insight-v">${escapeHtml(data.missing_phone_pct)}%</div>
            </div>
            <div class="insight">
              <div class="insight-k">Duplicate emails</div>
              <div class="insight-v">${escapeHtml(data.duplicate_emails)}</div>
            </div>
            <div class="insight">
              <div class="insight-k">Duplicate phones</div>
              <div class="insight-v">${escapeHtml(data.duplicate_phones)}</div>
            </div>
          </div>

          <div class="insight-sep"></div>

          <div class="mini">
            <div class="mini-title">Top events</div>
            ${renderMiniList(data.top_events)}
          </div>

          <div class="mini" style="margin-top:12px;">
            <div class="mini-title">Payment status</div>
            ${renderMiniList(data.top_payment_status)}
          </div>
        `;
      })
      .catch(function () {
        insightsEl.innerHTML = `<div class="muted">Couldn’t load insights.</div>`;
      });
  }

  // renders a small key/value list for insight sections
  function renderMiniList(obj) {
    var entries = Object.entries(obj || {});
    if (entries.length === 0) {
      return `<div class="muted">No data.</div>`;
    }

    return `
      <div class="mini-list">
        ${entries
          .map(function (pair) {
            return `<div class="mini-row"><span>${escapeHtml(pair[0])}</span><b>${escapeHtml(pair[1])}</b></div>`;
          })
          .join("")}
      </div>
    `;
  }

  // runs search and builds results list
  function doSearch() {
    var q = qEl.value ? qEl.value.trim() : "";
    if (!q) {
      return;
    }

    resultsEl.innerHTML = "Searching...";
    detailsEl.innerHTML = `<div class="muted">Click a result to see full fields.</div>`;

    fetch("/api/search?q=" + encodeURIComponent(q) + "&limit=25")
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Search request failed.");
        }
        return response.json();
      })
      .then(function (data) {
        resultsEl.innerHTML = "";

        if (!data.results || data.results.length === 0) {
          resultsEl.innerHTML = `<div class="muted">No matches.</div>`;
          return;
        }

        data.results.forEach(function (record) {
          var card = document.createElement("button");
          card.type = "button";
          card.className = "result-card";
          card.innerHTML = `
            <div class="result-top">
              <div class="result-name">${escapeHtml(record.name || "(no name)")}</div>
              <div class="pill">${escapeHtml(record.payment_status || "—")}</div>
            </div>
            <div class="result-sub">${escapeHtml(record.email || "(no email)")} • ${escapeHtml(record.phone || "(no phone)")}</div>
            <div class="result-sub">${escapeHtml(record.event_name || "")} ${record.amount ? "• " + escapeHtml(record.amount) : ""}</div>
            <div class="result-meta">${escapeHtml(record.source || "")}</div>
          `;

          card.addEventListener("click", function () {
            loadDetails(record.id);
          });

          resultsEl.appendChild(card);
        });
      })
      .catch(function () {
        resultsEl.innerHTML = `<div class="muted">Couldn’t run search right now.</div>`;
      });
  }

  // loads full details for one selected record
  function loadDetails(id) {
    detailsEl.innerHTML = "Loading...";

    fetch("/api/record?record_id=" + encodeURIComponent(id))
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Record request failed.");
        }
        return response.json();
      })
      .then(function (data) {
        if (data.error) {
          detailsEl.innerHTML = `<div class="muted">${escapeHtml(data.error)}</div>`;
          return;
        }

        var raw = data.raw || {};
        var keys = Object.keys(raw).sort();

        var html = `
          <div class="details-head">
            <div>
              <div class="details-title">${escapeHtml(data.name || "")}</div>
              <div class="details-sub">${escapeHtml(data.email || "")} • ${escapeHtml(data.phone || "")}</div>
            </div>
            <div class="details-tag">${escapeHtml(data.payment_status || "—")}</div>
          </div>

          <div class="details-meta">
            Source: ${escapeHtml(data.source_file)}:${escapeHtml(data.row_num)}
          </div>

          <div class="details-mini">
            <div><span>Event</span><b>${escapeHtml(data.event_name || "—")}</b></div>
            <div><span>Type</span><b>${escapeHtml(data.activity_type || "—")}</b></div>
            <div><span>Date</span><b>${escapeHtml(data.activity_date || "—")}</b></div>
            <div><span>Amount</span><b>${escapeHtml(data.amount || "—")}</b></div>
          </div>

          <div class="details-divider"></div>

          <div class="kv">
        `;

        keys.forEach(function (key) {
          html += `<div class="k">${escapeHtml(key)}</div><div class="v">${escapeHtml(String(raw[key] ?? ""))}</div>`;
        });

        html += "</div>";
        detailsEl.innerHTML = html;
      })
      .catch(function () {
        detailsEl.innerHTML = `<div class="muted">Couldn’t load this record.</div>`;
      });
  }

  // simple html escaping for safe text rendering
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;"
      }[char];
    });
  }
}
