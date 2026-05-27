/**
 * ui.js — DOM rendering
 * Pure rendering. No API calls, no state.
 */
const UI = {
  createBotMessage(resp) {
    switch (resp.message_type) {
      case "greeting":        return this._renderGreeting(resp);
      case "classify_ask":    return this._renderClassifyAsk(resp);
      case "question":        return this._renderQuestion(resp);
      case "result":          return this._renderResult(resp);
      case "rag_answer":      return this._renderRagAnswer(resp);
      case "rag_unavailable": return this._renderRagUnavailable(resp);
      case "info":            return this._renderInfo(resp);
      case "error":           return this._renderError(resp);
      default:                return this._renderInfo(resp);
    }
  },
  createUserMessage(text) {
    const msg = this._msgShell("user");
    msg.appendChild(this._avatar("YOU","usr"));
    msg.appendChild(this._el("div",{class:"bubble"},text));
    return msg;
  },
  createTypingIndicator(tier=1) {
    const msg = this._msgShell("bot");
    msg.appendChild(this._avatar(tier===2?"AI":"SYS", tier===2?"ai":"sys"));
    const b = this._el("div",{class: tier===2 ? "bubble t2-bubble" : "bubble"});
    if (tier===2) b.innerHTML=`<div class="msg-label tier2">AI thinking…</div>`;
    b.innerHTML += `<div class="typing"><span></span><span></span><span></span></div>`;
    msg.appendChild(b);
    return msg;
  },
  scrollToBottom(el) { el.scrollTop = el.scrollHeight; },
  disableAllButtons(el) {
    el.querySelectorAll("button[data-action]").forEach(b=>{ b.disabled=true; });
  },

  _renderGreeting(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble"});
    b.innerHTML=`<div class="msg-label tier1">System Online</div><p>${this._esc(resp.text)}</p>`;
    if(resp.all_procedures?.length) b.appendChild(this._allProcButtons(resp.all_procedures,"Browse all procedures"));
    msg.appendChild(b); return msg;
  },
  _renderClassifyAsk(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble"});
    b.innerHTML=`<p>${this._esc(resp.text)}</p>`;
    if(resp.candidates?.length){
      const opts=this._el("div",{class:"options"});
      resp.candidates.forEach(c=>{
        const btn=this._el("button",{class:"opt-btn proc-btn","data-action":`CMD:SELECT:${c.id}`});
        btn.innerHTML=`<span class="proc-id">${c.id}</span>${this._esc(c.name)}<span class="proc-conf">${Math.round(c.confidence*100)}%</span>${c.matched?.length?`<div class="proc-keywords">Matched: ${c.matched.join(", ")}</div>`:""}`;
        opts.appendChild(btn);
      });
      b.appendChild(opts);
      b.appendChild(this._el("div",{class:"sep-label"},"— or select directly —"));
    }
    if(resp.all_procedures?.length) b.appendChild(this._allProcButtons(resp.all_procedures));
    msg.appendChild(b); return msg;
  },
  _renderQuestion(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble"});
    b.innerHTML=`<div class="proc-badge">${resp.procedure_id} · ${this._esc(resp.procedure_name)}</div><div class="msg-label tier1">Step ${resp.step_number}</div><p>${this._esc(resp.text)}</p>`;
    if(resp.test_point){
      const tp=this._el("div",{class:"test-point"});
      tp.innerHTML=`<span class="tp-label">Test Point</span><span class="tp-value">${this._esc(resp.test_point)}</span>${resp.target_value?`<span class="tp-sep">→</span><span class="tp-target">${this._esc(resp.target_value)}</span>`:""}`;
      b.appendChild(tp);
    }
    const opts=this._el("div",{class:"options"});
    opts.appendChild(this._el("button",{class:"opt-btn yes","data-action":"yes"},"✓  Yes"));
    opts.appendChild(this._el("button",{class:"opt-btn no","data-action":"no"},"✗  No"));
    opts.appendChild(this._el("button",{class:"opt-btn ai","data-action":"CMD:ASK_AI"},"🤖  Ask AI instead"));
    b.appendChild(opts); msg.appendChild(b); return msg;
  },
  _renderResult(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble"});
    b.innerHTML=`<div class="proc-badge">${resp.procedure_id} · ${this._esc(resp.procedure_name)}</div>`;
    const box=this._el("div",{class:resp.is_ok?"fault-result ok":"fault-result"});
    box.innerHTML=`<div class="fault-label">${resp.is_ok?"✓ PASS":"⚠ Root Cause Identified"}</div><div class="fault-component">${this._esc(resp.component)}</div><div class="fault-action">${this._esc(resp.action)}</div>`;
    b.appendChild(box);
    const opts=this._el("div",{class:"options"});
    opts.appendChild(this._el("button",{class:"opt-btn","data-action":"CMD:NEW"},"Diagnose another fault"));
    opts.appendChild(this._el("button",{class:"opt-btn","data-action":"CMD:RESTART"},"Restart procedure"));
    opts.appendChild(this._el("button",{class:"opt-btn ai","data-action":"CMD:ASK_AI"},"🤖  Ask AI a follow-up"));
    b.appendChild(opts); msg.appendChild(b); return msg;
  },
  _renderRagAnswer(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("AI","ai"));
    const b=this._el("div",{class:"bubble t2-bubble"});
    b.innerHTML=`<div class="proc-badge t2">AI Knowledge Base</div><div class="msg-label tier2">Answer</div><p style="white-space:pre-wrap">${this._esc(resp.text)}</p>`;
    if(resp.rag_chunks?.length){
      const src=this._el("div",{class:"rag-sources"});
      src.innerHTML=`<div class="rag-sources-label">Sources Used</div>`;
      resp.rag_chunks.forEach(c=>{
        const item=this._el("div",{class:"rag-source-item"});
        item.innerHTML=`<span class="rag-score">${c.score.toFixed(2)}</span><span>${this._esc(c.doc)}</span>`;
        src.appendChild(item);
      });
      if(resp.llm_latency_ms) src.appendChild(this._el("div",{class:"rag-latency"},`Generated in ${(resp.llm_latency_ms/1000).toFixed(1)}s`));
      b.appendChild(src);
    }
    const opts=this._el("div",{class:"options"});
    opts.appendChild(this._el("button",{class:"opt-btn","data-action":"CMD:NEW"},"Diagnose a fault"));
    opts.appendChild(this._el("button",{class:"opt-btn","data-action":"CMD:ALL_PROCS"},"Browse procedures"));
    b.appendChild(opts); msg.appendChild(b); return msg;
  },
  _renderRagUnavailable(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("AI","ai"));
    const b=this._el("div",{class:"bubble t2-bubble"});
    b.innerHTML=`<div class="proc-badge t2">AI Knowledge Base — Offline</div><p style="white-space:pre-wrap">${this._esc(resp.text)}</p>`;
    if(resp.all_procedures?.length){
      b.appendChild(this._el("div",{class:"sep-label"},"Use structured procedures:"));
      b.appendChild(this._allProcButtons(resp.all_procedures));
    }
    msg.appendChild(b); return msg;
  },
  _renderInfo(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble"});
    b.innerHTML=`<p>${this._esc(resp.text)}</p>`;
    if(resp.show_yes_no){
      const opts=this._el("div",{class:"options"});
      opts.appendChild(this._el("button",{class:"opt-btn yes","data-action":"yes"},"✓  Yes"));
      opts.appendChild(this._el("button",{class:"opt-btn no","data-action":"no"},"✗  No"));
      b.appendChild(opts);
    }
    if(resp.all_procedures?.length) b.appendChild(this._allProcButtons(resp.all_procedures));
    msg.appendChild(b); return msg;
  },
  _renderError(resp) {
    const msg=this._msgShell("bot"); msg.appendChild(this._avatar("SYS","sys"));
    const b=this._el("div",{class:"bubble danger-bubble"});
    b.innerHTML=`<p>⚠ ${this._esc(resp.text)}</p>`;
    msg.appendChild(b); return msg;
  },

  _allProcButtons(procs, label="") {
    const wrap=document.createDocumentFragment();
    if(label) wrap.appendChild(this._el("div",{class:"sep-label"},label));
    const opts=this._el("div",{class:"options"});
    procs.forEach(p=>{
      const btn=this._el("button",{class:"opt-btn","data-action":`CMD:SELECT:${p.id}`,title:p.description});
      btn.innerHTML=`<span class="proc-id">${p.id}</span> ${this._esc(p.name)}`;
      opts.appendChild(btn);
    });
    wrap.appendChild(opts); return wrap;
  },
  _msgShell(role){ return this._el("div",{class:`msg ${role}`}); },
  _avatar(label,cls){ return this._el("div",{class:`avatar ${cls}`},label); },
  _el(tag,attrs={},text=null){
    const el=document.createElement(tag);
    for(const[k,v] of Object.entries(attrs)) el.setAttribute(k,v);
    if(text!==null) el.textContent=text;
    return el;
  },
  _esc(str){
    if(!str) return "";
    return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  },
};
export default UI;
