"use strict";

const setReplaySpot = (() => {
  const byId = id => document.getElementById(id);
  let current = null, items = [], revision = 0, activity = "", pendingKey = "";
  const editor = byId("library-editor");
  const selected = () => items.find(item => item.key === byId("bookmark-select").value);
  const message = text => {byId("library-status").textContent = text;};
  const ranks = "23456789TJQ";
  const cutoff = byId("replay-cutoff");
  for (const rank of ranks) cutoff.add(new Option(rank, rank));

  async function api(op, data) {
    const response = await fetch("/api/" + op, data ? {method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify(data)} : {cache:"no-store"});
    const result = await response.json();
    if (!response.ok) throw Error(result.error || "Unable to open saved decision.");
    return result;
  }
  function clearTrial() {
    revision++;
    byId("replay-output").textContent = "";
    byId("chart-controls").hidden = true;
  }
  function showRecord() {
    clearTrial();
    const item = selected();
    if (!item) return;
    const {record, candidate} = item, {decision:d, receipt, history} = record.row;
    cutoff.value = candidate || record.chart?.K?.offsuit_min_kicker || "7";
    byId("saved-context").textContent = "Hand " + d.hand + " · " + d.position + " · " + d.hole.join(" ") +
      " · " + (d.board.join(" ") || "Preflop") + " · Pot " + d.pot + " · " + d.call_cost + " to call · Stacks " + d.stack + " / " + d.opponent_stack;
    byId("saved-reason").textContent = "Your move: " + actionLabel(receipt.command,d) + ". " + (receipt.reason || "") +
      " · Recorded bot: " + actionLabel(record.row.recommendation.command,d);
    byId("saved-history").textContent = history.join(" · ");
    byId("retained-status").textContent = candidate ? "Kept cutoff for this spot: " + candidate : "Original chart · " + (record.row.recommendation.chart_version || "version unavailable");
    const action = byId("replay-action");
    action.replaceChildren(new Option("Trial chart move", ""));
    for (const name of d.legal) action.add(new Option(actionLabel(name,d),name));
    byId("replay-sizing").hidden = true;
    if (d.bounds) Object.assign(byId("replay-size"),{value:d.bounds[0],min:d.bounds[0],max:d.bounds[1]});
  }
  async function load(key) {
    const ticket = ++revision;
    try {
      const rows = await api("bookmarks");
      if (ticket !== revision) return;
      items = rows;
      const picker = byId("bookmark-select");
      const previous = key || picker.value;
      picker.replaceChildren();
      for (const item of rows) {
        const d = item.record.row.decision;
        picker.add(new Option("Hand " + d.hand + " · " + d.hole.join(" ") + " · decision " + d.id, item.key));
      }
      if (rows.some(r=>r.key===previous)) picker.value = previous;
      editor.hidden = !rows.length;
      message(rows.length ? "" : "Save a committed decision to replay it here.");
      showRecord();
    } catch (error) { if (ticket===revision) message(error.message); }
  }
  byId("saved-library").ontoggle = () => {if (byId("saved-library").open) {load(pendingKey); pendingKey="";}};
  byId("bookmark-move").onclick = async () => {
    const spot = current;
    if (!spot) return;
    try {
      const result = await api("bookmark",spot);
      if (current !== spot) return;
      byId("bookmark-status").textContent = "Saved";
      if (byId("saved-library").open) await load(result.key);
      else {pendingKey = result.key; byId("saved-library").open = true;}
    } catch(error) {if(current===spot) byId("bookmark-status").textContent = error.message;}
  };
  byId("bookmark-select").onchange = showRecord;
  cutoff.onchange = clearTrial;
  byId("replay-action").onchange = () => {
    clearTrial();
    byId("replay-sizing").hidden = byId("replay-action").value !== "raise";
  };
  byId("replay-size").oninput = clearTrial;
  async function run(op, discard=false) {
    const item = selected();
    if (!item) return;
    const ticket = ++revision;
    let alternate = byId("replay-action").value;
    if (alternate === "raise") {
      const size = byId("replay-size");
      if (!Number.isInteger(size.valueAsNumber) || !size.reportValidity()) {
        byId("replay-output").textContent = "Enter a legal whole-chip total."; return;
      }
      alternate += " " + size.valueAsNumber;
    }
    try {
      const result = await api(op,{key:item.key, cutoff:discard ? null : cutoff.value, alternate});
      if (ticket !== revision) return;
      if (op === "retain") {await load(item.key); return;}
      if (result.status !== "Reproduced") {byId("replay-output").textContent=result.status; return;}
      const d=item.record.row.decision, b=result.batch;
      const chart= item.record.chart.K.offsuit_min_kicker;
      byId("replay-output").textContent = "Original chart (" + chart + "): " + actionLabel(result.original.command,d) +
        ". Trial chart (" + cutoff.value + "): " + actionLabel(result.revised.command,d) +
        ". Compared " + actionLabel(b.alternate,d) + " with your " + actionLabel(b.original,d) + " on " + b.deals +
        " matched deals (seed " + b.seed + "). Mean difference " + b.mean_difference.toFixed(2) +
        " chips, standard error " + b.standard_error.toFixed(2) + ". Uniform opponent calls every bet; remaining streets check through.";
      byId("chart-controls").hidden = false;
    } catch(error) {if(ticket===revision) byId("replay-output").textContent=error.message;}
  }
  byId("run-replay").onclick = () => run("replay");
  byId("keep-chart").onclick = () => run("retain");
  byId("drop-chart").onclick = () => run("retain",true);
  return (s,row) => {
    const next = [s.session_id,s.phase,row?.decision.id].join("/");
    if (next!==activity) {
      revision++;
      byId("saved-library").open = false;
      byId("bookmark-status").textContent = "";
      current = row ? {session_id:s.session_id,id:row.decision.id} : null;
      activity = next;
    }
    byId("saved-library").hidden = !row && !["idle","complete"].includes(s.phase);
  };
})();
