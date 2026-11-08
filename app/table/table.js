"use strict";
const el = id => document.getElementById(id);
let state = {phase: "idle"}, move = "", busy = false;
const suits = {s:"♠", c:"♣", d:"♦", h:"♥"};
const streets = {0:"Preflop", 3:"Flop", 4:"Turn", 5:"River"};
let decisionKey = "";

function cards(id, values, count, hidden=false) {
  const container = el(id);
  container.replaceChildren();
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div"), value = values[i];
    card.className = "card";
    if (value) {
      const rank = value[0] === "T" ? "10" : value[0], suit = value[1];
      const symbol = document.createElement("span");
      symbol.textContent = suits[suit];
      card.append(rank, symbol);
      if ("dh".includes(suit)) card.classList.add("red");
      card.setAttribute("aria-label", rank + " of " + ({s:"spades",h:"hearts",d:"diamonds",c:"clubs"})[suit]);
    } else {
      card.classList.add(hidden ? "back" : "empty");
      card.setAttribute("aria-label", hidden ? "Face down" : "Empty");
    }
    container.append(card);
  }
}

function choose(value) {
  move = value;
  for (const button of el("actions").children) button.setAttribute("aria-pressed", String(button.dataset.move === move));
  el("sizing").hidden = move !== "raise";
  el("amount").disabled = move !== "raise";
  el("commit").disabled = !move || busy;
}

function actionLabel(command, decision) {
  const [action, amount] = command.split(" ");
  if (action === "raise") {
    const isRaise = decision.opponent_pip > 0;
    if (!amount) return isRaise ? "Raise" : "Bet";
    return isRaise ? "Raise to " + amount : "Bet " + amount;
  }
  return {fold:"Fold", check:"Check", call:"Call " + decision.call_cost}[action];
}

function drawActions(d) {
  const key = state.session_id + "/" + d.id;
  if (decisionKey !== key) {move = ""; el("reason").value = ""; decisionKey = key;}
  el("actions").replaceChildren();
  for (const name of ["fold","check","call","raise"].filter(x => d.legal.includes(x))) {
    const b = document.createElement("button");
    b.type = "button"; b.dataset.move = name;
    b.textContent = actionLabel(name, d);
    b.onclick = () => choose(name);
    el("actions").append(b);
  }
  if (d.bounds) {
    el("amount-label").textContent = d.opponent_pip > 0 ? "Raise to (chips)" : "Bet amount (chips)";
    const [low,high] = d.bounds;
    Object.assign(el("amount"), {min:String(low), max:String(high), value:String(low)});
    el("presets").replaceChildren();
    for (const [label,v] of [["Min",low],["½ pot",d.my_pip+d.call_cost+Math.floor((d.pot+d.call_cost)/2)],["Pot",d.my_pip+d.call_cost+d.pot+d.call_cost],["All-in",high]]) {
      const b=document.createElement("button");
      b.type="button"; b.textContent=label;
      b.onclick=()=>{el("amount").value=String(Math.min(high,Math.max(low,v))); preview();};
      el("presets").append(b);
    }
    preview();
  }
  choose(move);
}

function preview() {
  const n=el("amount").valueAsNumber, d=state.decision;
  el("cost").textContent = Number.isInteger(n) && n >= d.bounds[0] && n <= d.bounds[1]
    ? (n-d.my_pip)+" additional chips · "+d.bounds[0]+"–"+d.bounds[1]+" total allowed"
    : "Enter a whole number from "+d.bounds[0]+" to "+d.bounds[1]+".";
}

const chipResult = n => (n > 0 ? "+" : "") + n + (Math.abs(n) === 1 ? " chip" : " chips");

function comparisonRow() {
  const rows = state.journal || [];
  if (state.phase === "review") return rows.find(row => row.decision.id === state.decision.id);
  if (state.phase !== "complete" || !rows.length) return;
  const saved = window.history.state;
  const selected = saved && saved.session === state.session_id ? saved.spot : "";
  return rows.find(row => String(row.decision.id) === selected) || rows.find(row => row.disagrees) || rows[0];
}

function describePolicy(diagnostics) {
  if (diagnostics.rule === "button_king_chart") {
    const suited = diagnostics.hand.endsWith("s") ? "suited" : "offsuit";
    return "Your button chart opens " + suited + " kings with a kicker of " +
      diagnostics.min_kicker + " or higher. You held " + diagnostics.hand + ".";
  }
  const pct = value => (value * 100).toFixed(1) + "%";
  return "The bot estimated " + pct(diagnostics.equity) + " equity against a random hand over " +
    diagnostics.samples + " simulated deals. " +
    (diagnostics.pot_odds ? "The call needed " + pct(diagnostics.pot_odds) + " equity on pot odds alone." : "Checking cost no chips.") +
    (diagnostics.decision_rule ? " " + diagnostics.decision_rule : "");
}

function drawComparison(row) {
  const section = el("comparison");
  section.hidden = !row;
  if (!row) {
    el("spot-select").replaceChildren();
    return;
  }
  const {decision, receipt, recommendation, disagrees} = row;
  const finished = state.phase === "complete";
  const picker = el("spot-select");
  el("spot-picker").hidden = !finished;
  if (finished && !picker.options.length) {
    for (const entry of state.journal) {
      const spot = entry.decision;
      const title = "Hand " + spot.hand + " · " + streets[spot.street] + " · " +
        (entry.disagrees ? "Different" : "Agreed") + " (#" + spot.id + ")";
      picker.add(new Option(title, String(spot.id)));
    }
  }
  if (finished) picker.value = String(decision.id);
  const labels = values => values.map(card => (card[0] === "T" ? "10" : card[0]) + suits[card[1]]).join(" ");
  const seat = decision.position === "button" ? "Button" : "Big blind";
  el("spot-context").textContent = "Hand " + decision.hand + " · " + seat + " · " + labels(decision.hole) +
    " · " + (decision.board.length ? streets[decision.street] + " " + labels(decision.board) : "Preflop") +
    " · Pot " + decision.pot + " · " + decision.call_cost + " to call";
  el("human-choice").textContent = actionLabel(receipt.command, decision);
  el("bot-choice").textContent = actionLabel(recommendation.command, decision);
  el("player-reason").textContent = receipt.reason ? "Your reasoning · " + receipt.reason : "You left your reasoning blank.";
  el("policy-reason").textContent = describePolicy(recommendation.diagnostics);
  const result = disagrees ? "Different choices." : "Agreed within the sizing threshold.";
  el("comparison-rule").textContent = result + " Sizes differing by at least 1 big blind (2 chips) count as different.";
  el("policy-source").textContent = "Local policy · King chart " + recommendation.chart_version;
  el("comparison-title").textContent = finished && !state.journal.some(entry => entry.disagrees)
    ? "You and your bot agreed throughout" : "Your bot’s comparison";
}

function render() {
  const {phase,receipt,settlement} = state;
  const row = comparisonRow();
  const replay = phase === "complete" && row;
  const d = replay ? row.decision : state.decision;
  drawComparison(row);
  setCoachSpot(state, row);
  const setup = phase === "idle" || phase === "complete";
  el("start").hidden=!setup;
  el("play").hidden=phase!=="decision";
  el("review").hidden=phase!=="review" && phase!=="settled";
  el("end").hidden=setup;
  el("hand-count").textContent = d ? "Hand "+d.hand+" / "+state.hands : "";
  const showing = d && (!setup || replay);
  cards("hole",showing ? d.hole : [],2,!showing);
  cards("board",showing ? d.board : [],5);
  const exposed = phase==="settled" && state.showdown ? state.showdown.split(",") : [];
  cards("opp-cards",exposed,2,true);
  el("my-dealer").hidden=!showing || d.position!=="button";
  el("opp-dealer").hidden=!showing || d.position!=="bb";
  el("my-stack").textContent = phase==="settled" ? (400+settlement.human_delta)+" chips" : showing ? d.stack+" chips" : "400 chips";
  el("opp-stack").textContent = phase==="settled" ? (400-settlement.human_delta)+" chips" : showing ? d.opponent_stack+" chips" : "400 chips";
  el("pot").textContent= phase==="settled" ? "Pot awarded" : showing ? "Pot "+d.pot : "Pot 0";
  el("street").textContent=phase==="settled" ? "Hand complete" : showing ? streets[d.street] : "Waiting for players";
  el("panel-title").textContent=({idle:"Take a seat",decision:"Your decision",review:"Move committed",settled:"Hand result",complete:"Session complete"})[phase];
  el("status").textContent=({idle:"The MIT starter checks when it can and calls every bet.",decision:d && (d.call_cost ? d.call_cost+(d.call_cost===1 ? " chip to call." : " chips to call.") : "You can check."),review:"Review your move before revealing the next action.",settled:"Both seats acknowledged the payout.",complete:settlement && (settlement.hand+" hand"+(settlement.hand===1 ? "" : "s")+" played · "+chipResult(settlement.human_total)+" overall.")})[phase];
  el("receipt").hidden = phase === "review" && Boolean(row);
  el("history").replaceChildren();
  for (const line of (replay ? row.history : state.history) || []) {
    const li=document.createElement("li"); li.textContent=line; el("history").append(li);
  }
  if (phase==="decision") drawActions(d);
  if (phase==="review") {
    el("receipt").textContent="Your move · "+actionLabel(receipt.command, d)+(receipt.reason ? "\n"+receipt.reason : "");
    el("continue").textContent="Continue";
  }
  if (phase==="settled") {
    el("receipt").textContent="This hand · "+chipResult(settlement.human_delta)+"\nSession · "+chipResult(settlement.human_total);
    el("continue").textContent=settlement.hand===state.hands ? "Finish session" : "Next hand";
  }
  drawEncounter(state, row);
  setReplaySpot(state, row);
}

async function request(path, data) {
  if (busy) return;
  busy=true; el("error").hidden=true;
  document.querySelectorAll("button").forEach(b=>b.disabled=true);
  try {
    const res=await fetch("/api/"+path,data===undefined ? {cache:"no-store"} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
    let body=await res.json();
    if (res.status === 409) {
      const conflict = body.error;
      const current = await fetch("/api/state", {cache:"no-store"});
      if (!current.ok) throw new Error("The table changed. Refresh to recover your hand.");
      body = await current.json();
      el("error").textContent = conflict + " Showing the current table.";
      el("error").hidden = false;
    } else if (!res.ok) {
      throw new Error(body.error || "Request failed. Refresh to recover your hand.");
    }
    const phaseChanged = state.phase !== body.phase;
    state=body; render();
    if (phaseChanged) el("panel-title").focus();
  } catch (error) {
    el("error").textContent=error.message; el("error").hidden=false;
  } finally {
    busy=false; document.querySelectorAll("button").forEach(b=>b.disabled=false);
    if (state.phase==="decision") el("commit").disabled=!move;
  }
}

el("start").onsubmit=e=>{e.preventDefault();request("start",{hands:Number(el("hands").value),position:el("position").value,comparison_mode:el("comparison-mode").value,opponent:el("opponent").value,seat_mode:el("seat-mode").value,watch_mode:el("watch-mode").value});};
el("spot-select").onchange = () => {
  window.history.replaceState({session:state.session_id, spot:el("spot-select").value}, "");
  render();
};
el("amount").oninput=preview;
el("play").onsubmit=e=>{
  e.preventDefault(); if (!move) return;
  const command=move==="raise" ? "raise "+el("amount").valueAsNumber : move;
  request("commit",{session_id:state.session_id,id:state.decision.id,command,reason:el("reason").value.trim()});
};
el("continue").onclick=()=>request("continue",{session_id:state.session_id,id:state.decision.id,phase:state.phase});
el("end").onclick=()=>request("end",{session_id:state.session_id});
render(); request("state");
