"use strict";

let playbackTimer, readSession, readSaved, predictionSpot;
function drawEncounter(s, row) {
  clearTimeout(playbackTimer);
  const e = s.encounter;
  const watch = e && e.seat_mode === "watch";
  const active = e && s.phase !== "complete";
  el("opponent-name").textContent = e ? e.label : "Opponent";
  el("hero-name").textContent = watch ? "Your bot" : "You";
  el("encounter-reads").hidden = !e;
  el("reveal-identity").hidden = !(e && e.opponent === "mystery" && !e.revealed && s.phase === "complete");
  el("watch-controls").hidden = !(watch && active);
  el("human-choice").parentElement.hidden = Boolean(watch);
  if (!e) {
    el("status").textContent = encounterDescription();
    return;
  }
  el("reason").placeholder = "What do you expect your opponent to do?";
  const stats = e.observed;
  el("observed").textContent = "Folded facing a bet: " + stats.folded + " / " + stats.facing_bet +
    ". Bet or raised when available: " + stats.raised + " / " + stats.may_raise + ".";
  const saved = JSON.stringify([e.note, e.confidence]);
  if (s.session_id !== readSession || saved !== readSaved) {
    el("read-note").value = e.note;
    el("confidence").value = e.confidence;
    el("read-status").textContent = "";
    readSession = s.session_id;
    readSaved = saved;
  }
  if (!watch) return;
  el("play").hidden = true;
  el("predict-controls").hidden = s.phase !== "decision";
  el("live-pace").value = e.watch_mode;
  if (row) {
    el("comparison-title").textContent = "Watched decision";
    el("comparison-rule").textContent = "";
    el("player-reason").textContent = row.receipt.reason ? "Your prediction · " + row.receipt.reason : "No prediction recorded.";
  }
  if (!active) return;
  const d = s.decision;
  const trigger = s.phase === "decision" && d.street === 5 && d.my_pip > 0 && d.call_cost > 0;
  const pause = e.watch_mode === "step" || (e.watch_mode === "river_raise" && trigger);
  if (s.phase === "decision") {
    el("panel-title").textContent = pause ? "Predict your bot’s move" : "Watching your bot";
    el("status").textContent = trigger && pause ? "Your bot faces a river raise." : e.label + " is in the other seat.";
    if (predictionSpot !== s.session_id + "/" + d.id) {
      el("prediction").value = "";
      predictionSpot = s.session_id + "/" + d.id;
    }
    el("predict-controls").hidden = !pause;
  }
  if (s.phase === "review") {
    el("receipt").textContent = "Your bot played · " + actionLabel(s.receipt.command, d) +
      (s.receipt.reason ? "\nYour prediction · " + s.receipt.reason : "");
  }
  if (!pause) {
    playbackTimer = setTimeout(() => {
      if (s !== state || busy) return;
      if (s.phase === "decision") stepWatch("");
      else if (s.phase === "review" || s.phase === "settled") el("continue").click();
    }, 650);
  }
}
function stepWatch(prediction) {
  return request("step", {session_id:state.session_id, id:state.decision.id, prediction});
}
function encounterDescription() {
  const options = {starter:"The MIT starter checks when it can and calls every bet.", equity:"The equity bot estimates its share of the pot before acting.",
    random:"The random bot samples a legal move.", check_fold:"The check/fold bot checks for free and folds facing a bet.",
    mystery:"One opponent stays with you for the full session."};
  return options[el("opponent").value];
}
document.addEventListener("DOMContentLoaded", () => {
  el("opponent").onchange = () => { if (state.phase === "idle") el("status").textContent = encounterDescription(); };
  el("seat-mode").onchange = () => {el("watch-setup").hidden = el("seat-mode").value !== "watch";};
  el("watch-step").onclick = () => stepWatch(el("prediction").value.trim());
  el("live-pace").onchange = () => request("watch-mode", {session_id:state.session_id, watch_mode:el("live-pace").value});
  el("save-read").onclick = async () => {
    await request("read", {session_id:state.session_id, note:el("read-note").value, confidence:el("confidence").value});
    if (el("error").hidden) el("read-status").textContent = "Saved";
  };
  el("reveal-identity").onclick = () => request("reveal", {session_id:state.session_id});
});
