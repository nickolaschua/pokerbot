"use strict";

const setCoachSpot = (() => {
  const field = id => document.getElementById(id);
  let sessionKey = "", journalSpot = null, selected = null, revision = 0;
  const pct = n => (100 * n).toFixed(1) + "%";

  function reset() {
    revision++;
    selected = null;
    field("math-panel").hidden = true;
    field("river-drill").open = false;
    field("coach-text").textContent = "";
  }
  async function post(path, data) {
    const response = await fetch("/api/" + path, {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(data)});
    if (!response.ok) throw Error("This review could not be loaded. Refresh to return to your session.");
    return response.json();
  }
  async function showMath() {
    const ticket = ++revision;
    const model = field("ev-range").value;
    field("math-result").textContent = "Calculating…";
    field("coach-text").textContent = "";
    field("math-assumption").textContent = "";
    field("ask-coach").hidden = true;
    try {
      const m = await post("analysis", {...selected, model});
      if (ticket !== revision) return;
      let result = "Modeled equity " + pct(m.equity) + ". ";
      if (m.call_ev === null) result += "Checking costs zero. To price a bet, estimate how often your opponent calls, folds or raises.";
      else {
        result += "Break-even " + pct(m.break_even) + " = " + m.cost + " / (" + m.pot + " + " + m.cost + "). " +
          "Call EV " + (m.call_ev >= 0 ? "+" : "−") + Math.abs(m.call_ev).toFixed(1) +
          " chips = equity × " + (m.pot + m.cost) + " − " + m.cost + ". Folding adds 0 chips from here.";
      }
      field("math-result").textContent = result;
      field("math-assumption").textContent = m.assumption;
      field("ask-coach").hidden = false;
    } catch (err) { if (ticket === revision) field("math-result").textContent = err.message; }
  }
  function open(spot, river) {
    selected = spot;
    field("math-panel").hidden = false;
    field("math-title").textContent = spot.fixture ? "Saved river · you chose " + spot.prediction : "Decision math";
    field("ev-range").value = "uniform";
    field("ev-range").querySelector('[value="strong"]').disabled = !river;
    showMath();
  }
  field("open-math").onclick = () => {
    field("river-drill").open = false;
    open(journalSpot.request, journalSpot.river);
  };
  field("river-drill").ontoggle = () => {
    if (!field("river-drill").open && selected && selected.fixture) {
      revision++;
      selected = null;
      field("math-panel").hidden = true;
    }
  };
  for (const prediction of ["call", "fold"]) {
    field("drill-" + prediction).onclick = () => open({fixture:"river", prediction}, true);
  }
  field("ev-range").onchange = showMath;
  field("ask-coach").onclick = async () => {
    const ticket = ++revision;
    field("coach-text").textContent = "Preparing explanation…";
    try {
      const res = await post("explain", {...selected, model:field("ev-range").value});
      if (ticket === revision) field("coach-text").textContent = res.source + " · " + res.text;
    } catch (err) { if (ticket === revision) field("coach-text").textContent = err.message; }
  };
  return (state, row) => {
    const key = [state.session_id, state.phase, row && row.decision.id].join("/");
    if (sessionKey !== key) reset();
    sessionKey = key;
    const drill = state.phase === "idle" || state.phase === "complete";
    journalSpot = row && {request:{session_id:state.session_id, id:row.decision.id}, river:row.decision.street === 5};
    field("ev-coach").hidden = !row && !drill;
    field("open-math").hidden = !row;
    field("river-drill").hidden = !drill;
  };
})();
