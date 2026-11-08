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

function render() {
  const {phase,decision:d,receipt,settlement} = state;
  const setup = phase === "idle" || phase === "complete";
  el("start").hidden=!setup;
  el("play").hidden=phase!=="decision";
  el("review").hidden=phase!=="review" && phase!=="settled";
  el("end").hidden=setup;
  el("hand-count").textContent = d ? "Hand "+d.hand+" / "+state.hands : "";
  const showing = d && !setup;
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
  el("history").replaceChildren();
  for (const line of state.history || []) {
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
}

async function request(path, data) {
  if (busy) return;
  busy=true; el("error").hidden=true;
  document.querySelectorAll("button").forEach(b=>b.disabled=true);
  try {
    const res=await fetch("/api/"+path,data===undefined ? {cache:"no-store"} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
    const body=await res.json();
    if (!res.ok) throw new Error(body.error || "Request failed. Refresh to recover your hand.");
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

el("start").onsubmit=e=>{e.preventDefault();request("start",{hands:Number(el("hands").value),position:el("position").value});};
el("amount").oninput=preview;
el("play").onsubmit=e=>{
  e.preventDefault(); if (!move) return;
  const command=move==="raise" ? "raise "+el("amount").value : move;
  request("commit",{session_id:state.session_id,id:state.decision.id,command,reason:el("reason").value.trim()});
};
el("continue").onclick=()=>request("continue",{session_id:state.session_id,id:state.decision.id,phase:state.phase});
el("end").onclick=()=>request("end",{session_id:state.session_id});
render(); request("state");
