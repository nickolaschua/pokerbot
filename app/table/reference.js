"use strict";

const referenceElement = id => document.getElementById(id);
let referenceSession = "", journalReference = null, selectedReference = null, referenceRevision = 0;
function resetReference() {
  referenceRevision++;
  selectedReference = null;
  referenceElement("reference-review").hidden = true;
  referenceElement("reference-source").hidden = true;
}
function clearSavedReference() {
  if (selectedReference && selectedReference.key) resetReference();
}
function setReferenceSpot(s, row) {
  const key = [s.session_id, s.phase, row && row.decision.id].join("/");
  if (key !== referenceSession) {
    resetReference();
    referenceElement("reference-drill").open = false;
    referenceSession = key;
  }
  const drill = s.phase === "idle" || s.phase === "complete";
  journalReference = row && {session_id:s.session_id,id:row.decision.id};
  referenceElement("reference-live").hidden = !row;
  referenceElement("reference-drill").hidden = !drill;
  referenceElement("reference-panel").hidden = !drill && !row;
}
function describeExercise() {
  const variant = referenceElement("reference-variant").value;
  const line = variant === "history"
    ? "You opened to 4. The big blind called, bet 196 on the flop, and you called. The turn checked through."
    : "You opened to 200 and the big blind called. The flop and turn checked through.";
  const bet = variant === "size" ? 150 : 200;
  const stack = variant === "stack" ? 300 : 200;
  referenceElement("reference-situation").textContent = "Blinds 1/2. You hold K♣ 5♠ on the button. " + line +
    " On 5♥ J♥ 5♦ Q♥ 3♥ the pot is 400 with " + stack + " behind each. The big blind bets " + bet +
    ". Assume A♥ 2♥ and 7♠ 2♦ are equally likely before the bet. What would you do?";
}
async function loadReference() {
  const ticket = ++referenceRevision;
  const out = referenceElement("reference-output"), source = referenceElement("reference-source");
  out.textContent = "Checking the reference…";
  source.hidden = true;
  try {
    const response = await fetch("/api/reference", {method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({...selectedReference,range:referenceElement("reference-range").value})});
    const r = await response.json();
    if (ticket !== referenceRevision) return;
    if (!response.ok) throw Error(r.error || "Unable to check this reference.");
    const lines = [];
    if (r.covered) {
      const pct = n => (n * 100).toFixed(1) + "%";
      lines.push("Covered by the restricted river equilibrium. Call " + pct(r.call_frequency) + ", fold " + pct(r.fold_frequency) + ".");
      lines.push("The bettor always bets for value and bluffs " + pct(r.bluff_frequency) +
        " of weak holdings. After the bet, your equity is " + pct(r.conditional_equity) + ".");
      lines.push("Call EV " + r.call_ev_chips + " chips. Fold EV " + r.fold_ev_chips + " chips. Gap " + r.ev_gap_bb +
        " big blinds. Both actions break even against this mix; the frequencies keep a bluff indifferent.");
      lines.push("A winning call gains " + r.on_win_bb + " big blinds and a losing call costs " + Math.abs(r.on_loss_bb) +
        ". One big blind is 2 chips.");
      lines.push(r.reference.range + " " + r.reference.tree);
    } else {
      lines.push("Outside reference coverage. " + r.reasons.join(" "));
      const m = r.math;
      if (!r.conditional_ev_available) {
        lines.push("EV for the selected prior is unavailable. This reference supplies no betting frequencies for this spot, so the prior alone cannot determine which hands bet.");
      }
      lines.push("Uniform-hand fallback: " + (m.equity * 100).toFixed(1) + "% equity. " +
        (m.call_ev === null ? "Checking costs zero." : "Call EV " + m.call_ev.toFixed(1) + " chips.") + " " + m.assumption);
    }
    out.replaceChildren(...lines.map(line => {const p = document.createElement("p");p.textContent = line;return p;}));
    if (r.reference) {
      source.href = r.reference.url;
      source.textContent = r.reference.source + " · " + r.reference.revision;
      source.hidden = false;
    }
  } catch (e) { if (ticket === referenceRevision) out.textContent = e.message; }
}
function openReference(spot, title) {
  selectedReference = spot;
  referenceElement("reference-heading").textContent = title;
  referenceElement("reference-review").hidden = false;
  referenceElement("reference-range").value = spot.fixture ? "equal_polar" : "uniform";
  referenceElement("reference-heading").focus();
  loadReference();
}
referenceElement("reference-variant").onchange = () => {resetReference();describeExercise();};
for (const prediction of ["call","fold"]) {
  referenceElement("reference-" + prediction).onclick = () => {
    openReference({fixture:referenceElement("reference-variant").value,prediction}, "River review · you chose " + prediction);
  };
}
referenceElement("reference-live").onclick = () => openReference(journalReference, "Committed decision review");
referenceElement("reference-bookmark").onclick = () => openReference({key:referenceElement("bookmark-select").value}, "Saved decision review");
referenceElement("reference-range").onchange = loadReference;
referenceElement("reference-drill").ontoggle = () => {
  if (!referenceElement("reference-drill").open && selectedReference?.fixture) resetReference();
};
describeExercise();
