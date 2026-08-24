const config = window.ZoneTripBoothConfig || {};
const endpoint = config.reviewEndpoint || "/review-day";
const status = document.querySelector("#review-status");
const content = document.querySelector("#review-content");
const loadButton = document.querySelector("#load-review");
const form = document.querySelector("#review-form");

function setStatus(message) {
  status.textContent = message;
}

function renderPacket(packet) {
  document.querySelector("#review-draft").textContent = packet.draft.content;
  document.querySelector("#review-transition").textContent = packet.warrant.transition;
  document.querySelector("#review-sources").textContent = String(packet.supporting_object_ids.length);
  document.querySelector("#review-uncertainty").textContent = packet.warrant.uncertainty_preserved
    ? "Yes"
    : "No";
  const checks = document.querySelector("#review-checks");
  checks.replaceChildren();
  for (const check of packet.checks) {
    const item = document.createElement("li");
    item.className = check.passed ? "check-pass" : "check-fail";
    item.textContent = `${check.rule_id}: ${check.detail}`;
    checks.append(item);
  }
  content.hidden = false;
  setStatus(`${packet.status} · ${packet.id}`);
}

async function loadReview() {
  setStatus("Loading pending review…");
  try {
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Processor returned ${response.status}`);
    renderPacket(await response.json());
  } catch (error) {
    content.hidden = true;
    setStatus(`Unavailable: ${error.message}`);
  }
}

loadButton.addEventListener("click", loadReview);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitter = event.submitter;
  const decision = submitter?.value;
  if (!decision) return;
  submitter.disabled = true;
  setStatus(`${decision === "approve" ? "Approving" : "Rejecting"} and verifying burn…`);
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reviewer_role: document.querySelector("#reviewer-role").value,
        decision,
        rationale: document.querySelector("#review-rationale").value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `Processor returned ${response.status}`);
    content.hidden = true;
    setStatus(
      `${payload.review_status}. Burn verified: ${payload.burn_receipt.deletion_verified ? "yes" : "no"}.`
    );
  } catch (error) {
    setStatus(`Review failed: ${error.message}`);
  } finally {
    submitter.disabled = false;
  }
});
