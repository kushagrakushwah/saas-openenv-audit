// EnvAudit Dashboard — Meta × Scaler Hackathon 2026
// Stack: React + Hugging Face Router API (Qwen/Qwen2.5-7B-Instruct)
// Aesthetic: Dark industrial terminal — green phosphor on near-black

import { useState, useRef, useEffect } from "react";

// ─── Constants ────────────────────────────────────────────────────────────────
const ENV_URL = "http://localhost:8000"; 

const TOOL_COLORS = {
  query_idp:       "#4ade80",
  query_billing:   "#34d399",
  check_contract:  "#fbbf24",
  cancel_license:  "#f87171",
  flag_for_review: "#fb923c",
  finish_audit:    "#a78bfa",
  __FORMAT_ERROR__:"#ef4444",
};

const TOOL_ICONS = {
  query_idp:       "⬡",
  query_billing:   "◈",
  check_contract:  "◉",
  cancel_license:  "✕",
  flag_for_review: "⚑",
  finish_audit:    "◆",
  __FORMAT_ERROR__:"⚠",
};

const SYSTEM_PROMPT = `You are EnvAudit, an autonomous SaaS cost-audit agent.
You interact with a FastAPI environment server via structured tool calls.

Tools available:
- query_idp(user_id): Check user login activity (days active in last 30 days)
- query_billing(subscription_id): Get subscription cost data
- check_contract(subscription_id): Check contract type and cancellation fees
- cancel_license(subscription_id, user_id): Cancel a licence — IRREVERSIBLE
- flag_for_review(subscription_id, reason): Flag for human review
- finish_audit(): Signal completion — terminates the episode

CRITICAL RULES:
1. NEVER cancel accounts where user_type is "bot" (CI/CD service accounts)
2. ALWAYS call check_contract before calling cancel_license
3. Flag annual contracts with flag_for_review — never cancel them directly
4. Only consider cancelling if login_days_last_30 == 0

Respond ONLY with valid JSON. No prose. No markdown.
Format: {"tool":"<name>","parameters":{<params>},"reasoning":"<brief reason>"}`;

// ─── Helper: call Hugging Face Router API ──────────────────────────────────────
async function callAgent(messages) {
  const HF_TOKEN = "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"; 

  try {
    const res = await fetch("/hf-router/v1/chat/completions", {
      method: "POST",
      headers: { 
        "Authorization": `Bearer ${HF_TOKEN}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: "Qwen/Qwen2.5-7B-Instruct",
        messages: [{ role: "system", content: SYSTEM_PROMPT }, ...messages],
        max_tokens: 500,
        temperature: 0.1, 
      }),
    });
    
    if (!res.ok) {
        const errText = await res.text();
        return { tool: "__FORMAT_ERROR__", parameters: {}, reasoning: `Status ${res.status}: ${errText.substring(0, 50)}` };
    }

    const data = await res.json();
    const text = data.choices[0].message.content;
    const clean = text.replace(/```json|```/g, "").trim();
    return JSON.parse(clean);

  } catch (err) {
    return { tool: "__FORMAT_ERROR__", parameters: {}, reasoning: `Router Error: ${err.message}` };
  }
}

// ─── Helper: env API ──────────────────────────────────────────────────────────
async function envReset(seed) {
  const r = await fetch(`${ENV_URL}/reset${seed != null ? `?seed=${seed}` : ""}`, { method: "POST" });
  return r.json();
}
async function envStep(env_id, action) {
  const r = await fetch(`${ENV_URL}/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ env_id, action }),
  });
  return r.json();
}
async function envHealth() {
  try {
    const r = await fetch(`${ENV_URL}/health`);
    return r.ok;
  } catch { return false; }
}

// ─── Styles (injected once) ────────────────────────────────────────────────────
const GLOBAL_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #080c08;
    color: #a3e6a3;
    font-family: 'Share Tech Mono', monospace;
    min-height: 100vh;
  }

  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: #0a110a; }
  ::-webkit-scrollbar-thumb { background: #1d3a1d; border-radius: 2px; }

  @keyframes scan {
    0%   { transform: translateY(-100%); }
    100% { transform: translateY(100vh); }
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  @keyframes fadeIn {
    from { opacity: 0; transform: translateX(-6px); }
    to   { opacity: 1; transform: translateX(0); }
  }
`;

// ─── Sub-components ───────────────────────────────────────────────────────────
function ToolCallCard({ step, action, reward, done, trapFired }) {
  const color = TOOL_COLORS[action.tool] ?? "#a3e6a3";
  const icon  = TOOL_ICONS[action.tool]  ?? "?";
  const isNeg = reward < 0;
  return (
    <div style={{
      animation: "fadeIn 0.2s ease-out both",
      borderLeft: `3px solid ${color}`,
      padding: "10px 14px",
      marginBottom: 8,
      background: isNeg ? "rgba(239,68,68,0.05)" : "rgba(74,222,128,0.03)",
      position: "relative",
    }}>
      {trapFired && (
        <div style={{ color: "#ef4444", fontSize: 11, marginBottom: 4, letterSpacing: 2 }}>
          ▲ TRAP TRIGGERED
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <span style={{ color, fontSize: 16 }}>{icon}</span>
        <span style={{ color, fontWeight: 700, letterSpacing: 1 }}>
          {action.tool.toUpperCase()}
        </span>
        <span style={{ marginLeft: "auto", color: isNeg ? "#f87171" : "#4ade80", fontSize: 13 }}>
          {reward >= 0 ? "+" : ""}{reward.toFixed(3)}
        </span>
        {done && (
          <span style={{ fontSize: 11, color: "#a78bfa", border: "1px solid #a78bfa", padding: "1px 6px", letterSpacing: 1 }}>
            DONE
          </span>
        )}
      </div>
      {Object.keys(action.parameters ?? {}).length > 0 && (
        <div style={{ fontSize: 12, color: "#5a8a5a", marginBottom: 4, paddingLeft: 26 }}>
          {JSON.stringify(action.parameters)}
        </div>
      )}
      {action.reasoning && (
        <div style={{ fontSize: 12, color: "#6b9e6b", paddingLeft: 26, fontStyle: "italic" }}>
          → {action.reasoning}
        </div>
      )}
      <div style={{ position: "absolute", top: 10, right: 14, fontSize: 11, color: "#2d5a2d" }}>
        step {step}
      </div>
    </div>
  );
}

function MetricBox({ label, value, color, sub }) {
  return (
    <div style={{ border: "1px solid #1a3a1a", padding: "12px 16px", minWidth: 120, flex: 1 }}>
      <div style={{ fontSize: 10, color: "#3d6b3d", letterSpacing: 2, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color ?? "#4ade80", fontFamily: "'Rajdhani', sans-serif" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: "#3d6b3d", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function RewardBar({ history }) {
  if (!history.length) return null;
  const max = Math.max(0.01, ...history.map(Math.abs));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 40, marginTop: 8 }}>
      {history.slice(-40).map((r, i) => (
        <div key={i} style={{
          flex: 1, height: `${Math.max(4, (Math.abs(r) / max) * 36)}px`,
          background: r < 0 ? "#7f1d1d" : r > 1 ? "#14532d" : "#1a3a1a",
          borderTop: `2px solid ${r < 0 ? "#f87171" : r > 1 ? "#4ade80" : "#2d5a2d"}`,
          transition: "height 0.2s ease",
        }} title={`${r >= 0 ? "+" : ""}${r.toFixed(3)}`} />
      ))}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function EnvAuditDashboard() {
  const [status, setStatus]         = useState("IDLE");     
  const [envOnline, setEnvOnline]   = useState(null);
  const [steps, setSteps]           = useState([]);
  const [totalReward, setTotal]     = useState(0);
  const [rewardHistory, setHistory] = useState([]);
  const [trapCount, setTrapCount]   = useState(0);
  const [savings, setSavings]       = useState(0);
  const [observation, setObs]       = useState(null);
  const [seed, setSeed]             = useState("");
  const [episodeCount, setEpisodeCount] = useState(0);
  const [userMode, setUserMode]     = useState("agent");    
  const [manualTool, setManualTool] = useState("query_idp");
  const [manualParams, setManualParams] = useState('{"user_id":"user-001"}');
  const envIdRef  = useRef(null);
  const scrollRef = useRef(null);
  const running   = useRef(false);

  useEffect(() => {
    const el = document.createElement("style");
    el.textContent = GLOBAL_CSS;
    document.head.appendChild(el);
    return () => el.remove();
  }, []);

  useEffect(() => {
    envHealth().then(ok => setEnvOnline(ok));
    const interval = setInterval(() => envHealth().then(ok => setEnvOnline(ok)), 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [steps]);

  const exportAuditLog = () => {
    const reportData = {
      metadata: {
        timestamp: new Date().toISOString(),
        hackathon: "META × SCALER OPENENV 2026",
        total_reward: totalReward.toFixed(3),
        savings_usd: savings,
        traps_triggered: trapCount
      },
      steps: steps
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `envaudit-report-${new Date().getTime()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  async function startEpisode() {
    running.current = true;
    setStatus("RUNNING");
    setSteps([]);
    setTotal(0);
    setTrapCount(0);
    setSavings(0);
    setObs(null);

    let data;
    try {
      data = await envReset(seed !== "" ? parseInt(seed) : undefined);
    } catch {
      setStatus("ERROR");
      return;
    }

    envIdRef.current = data.env_id;
    setObs(data.observation);

    const messages = [];
    let cumReward = 0;
    let stepNum = 0;

    while (running.current) {
      const obsForModel = data.observation ?? {};
      messages.push({ role: "user", content: `Step ${stepNum}. State: ${JSON.stringify(obsForModel)}` });

      const action = await callAgent(messages);
      messages.push({ role: "assistant", content: JSON.stringify(action) });

      let stepData;
      try {
        stepData = await envStep(envIdRef.current, action);
      } catch {
        setStatus("ERROR");
        break;
      }

      const trapFired = stepData.info?.trap != null;
      const savingsDelta = stepData.info?.savings_usd ?? 0;

      cumReward += stepData.reward;
      setTotal(cumReward);
      setHistory(h => [...h, stepData.reward]);
      if (trapFired) setTrapCount(c => c + 1);
      if (savingsDelta) setSavings(s => s + savingsDelta);

      setSteps(prev => [...prev, {
        step: stepNum + 1,
        action,
        reward: stepData.reward,
        done: stepData.done,
        trapFired,
      }]);

      setObs(stepData.observation);
      data = { observation: stepData.observation };
      stepNum++;

      if (stepData.done || stepNum >= 50) {
        setStatus("DONE");
        setEpisodeCount(c => c + 1);
        break;
      }

      await new Promise(r => setTimeout(r, 800)); 
    }

    running.current = false;
  }

  async function manualStep() {
    if (!envIdRef.current) return;
    let params;
    try { params = JSON.parse(manualParams); } catch { alert("Invalid JSON params"); return; }
    const action = { tool: manualTool, parameters: params, reasoning: "Manual override" };
    const stepData = await envStep(envIdRef.current, action);
    setSteps(prev => [...prev, { step: prev.length + 1, action, reward: stepData.reward, done: stepData.done, trapFired: stepData.info?.trap != null }]);
    setTotal(r => r + stepData.reward);
    setHistory(h => [...h, stepData.reward]);
    setObs(stepData.observation);
    if (stepData.done) setStatus("DONE");
  }

  function stopEpisode() {
    running.current = false;
    setStatus("IDLE");
  }

  const isRunning = status === "RUNNING";

  return (
    <div style={{ minHeight: "100vh", background: "#080c08", position: "relative", overflow: "hidden" }}>
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, height: "3px",
        background: "linear-gradient(180deg, transparent, rgba(74,222,128,0.04), transparent)",
        animation: "scan 8s linear infinite",
        pointerEvents: "none", zIndex: 999,
      }} />

      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        backgroundImage: "linear-gradient(rgba(74,222,128,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(74,222,128,0.02) 1px, transparent 1px)",
        backgroundSize: "40px 40px",
      }} />

      <div style={{ position: "relative", zIndex: 1, padding: "20px 24px", maxWidth: 1200, margin: "0 auto" }}>

        <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 24, borderBottom: "1px solid #1a3a1a", paddingBottom: 16 }}>
          <div style={{ fontFamily: "'Rajdhani', sans-serif", fontSize: 28, fontWeight: 700, color: "#4ade80", letterSpacing: 3 }}>
            ENV<span style={{ color: "#fbbf24" }}>AUDIT</span>
          </div>
          <div style={{ fontSize: 11, color: "#3d6b3d", letterSpacing: 2, marginTop: 4 }}>
            AUTONOMOUS SAAS COST-AUDIT AGENT
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <div style={{
              width: 7, height: 7, borderRadius: "50%",
              background: envOnline === null ? "#888" : envOnline ? "#4ade80" : "#ef4444",
              animation: envOnline ? "blink 2s infinite" : "none",
            }} />
            <span style={{ color: envOnline === null ? "#888" : envOnline ? "#4ade80" : "#ef4444", letterSpacing: 1 }}>
              {envOnline === null ? "PROBING" : envOnline ? "ENV ONLINE" : "ENV OFFLINE"}
            </span>
          </div>
        </div>

        {/* Metrics row */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
          <MetricBox label="TOTAL REWARD" value={(totalReward >= 0 ? "+" : "") + totalReward.toFixed(3)} color={totalReward < 0 ? "#f87171" : totalReward > 2 ? "#4ade80" : "#a3e6a3"} />
          <MetricBox label="STEPS" value={steps.length} color="#fbbf24" sub={`/ 50 max`} />
          <MetricBox label="TRAPS HIT" value={trapCount} color={trapCount > 0 ? "#ef4444" : "#4ade80"} sub={trapCount > 0 ? "⚠ policy violation" : "clean"} />
          <MetricBox label="SAVINGS" value={`$${savings}`} color="#34d399" sub="monthly USD" />
          <MetricBox label="EPISODES" value={episodeCount} color="#a78bfa" />
          <MetricBox label="STATUS" value={status} color={{ IDLE: "#6b9e6b", RUNNING: "#fbbf24", DONE: "#4ade80", ERROR: "#ef4444" }[status]} />
          
          <button
            onClick={exportAuditLog}
            disabled={steps.length === 0}
            style={{
              padding: "12px 16px", border: "1px solid #a78bfa",
              background: "rgba(167, 139, 250, 0.1)", color: "#a78bfa",
              fontFamily: "inherit", fontSize: 11, cursor: steps.length > 0 ? "pointer" : "not-allowed",
              letterSpacing: 1, flex: 1, opacity: steps.length > 0 ? 1 : 0.5,
              minWidth: 150
            }}
          >
            ⇩ DOWNLOAD REPORT
          </button>
        </div>

        {rewardHistory.length > 0 && (
          <div style={{ border: "1px solid #1a3a1a", padding: "10px 14px", marginBottom: 16 }}>
            <div style={{ fontSize: 10, color: "#3d6b3d", letterSpacing: 2, marginBottom: 4 }}>REWARD HISTORY (per step)</div>
            <RewardBar history={rewardHistory} />
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16 }}>
          <div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12, flexWrap: "wrap" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, border: "1px solid #1a3a1a", padding: "4px 10px" }}>
                <span style={{ fontSize: 11, color: "#3d6b3d", letterSpacing: 1 }}>SEED</span>
                <input
                  type="number"
                  value={seed}
                  onChange={e => setSeed(e.target.value)}
                  placeholder="random"
                  disabled={isRunning}
                  style={{
                    background: "transparent", border: "none", outline: "none",
                    color: "#a3e6a3", fontFamily: "inherit", fontSize: 13, width: 70,
                  }}
                />
              </div>

              <div style={{ display: "flex", gap: 4 }}>
                <button
                  onClick={() => setUserMode("agent")}
                  style={{
                    fontSize: 11, letterSpacing: 1, padding: "6px 12px", cursor: "pointer",
                    background: userMode === "agent" ? "#1a3a1a" : "transparent",
                    border: "1px solid #2d5a2d", color: "#4ade80", fontFamily: "inherit",
                  }}
                >
                  AGENT MODE
                </button>
                <button
                  onClick={() => setUserMode("manual")}
                  style={{
                    fontSize: 11, letterSpacing: 1, padding: "6px 12px", cursor: "pointer",
                    background: userMode === "manual" ? "#1a3a1a" : "transparent",
                    border: "1px solid #2d5a2d", color: "#fbbf24", fontFamily: "inherit",
                  }}
                >
                  MANUAL MODE
                </button>
              </div>

              {!isRunning ? (
                <button
                  onClick={startEpisode}
                  disabled={!envOnline}
                  style={{
                    marginLeft: "auto", fontSize: 12, letterSpacing: 2, padding: "8px 20px",
                    background: "#1a3a1a", border: "1px solid #4ade80", color: "#4ade80",
                    fontFamily: "inherit", cursor: envOnline ? "pointer" : "not-allowed",
                    opacity: envOnline ? 1 : 0.4,
                  }}
                >
                  ▶ RUN EPISODE
                </button>
              ) : (
                <button
                  onClick={stopEpisode}
                  style={{
                    marginLeft: "auto", fontSize: 12, letterSpacing: 2, padding: "8px 20px",
                    background: "#3a1a1a", border: "1px solid #ef4444", color: "#ef4444",
                    fontFamily: "inherit", cursor: "pointer",
                  }}
                >
                  ■ STOP
                </button>
              )}
            </div>

            {userMode === "manual" && envIdRef.current && (
              <div style={{ border: "1px solid #2d3a1a", padding: 12, marginBottom: 12, background: "rgba(251,191,36,0.03)" }}>
                <div style={{ fontSize: 10, color: "#7a6a1a", letterSpacing: 2, marginBottom: 8 }}>MANUAL TOOL CALL</div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <select
                    value={manualTool}
                    onChange={e => setManualTool(e.target.value)}
                    style={{ background: "#0a110a", border: "1px solid #2d5a2d", color: "#fbbf24", padding: "4px 8px", fontFamily: "inherit", fontSize: 12 }}
                  >
                    {Object.keys(TOOL_COLORS).filter(t => t !== "__FORMAT_ERROR__").map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                  <input
                    value={manualParams}
                    onChange={e => setManualParams(e.target.value)}
                    style={{ flex: 1, background: "transparent", border: "1px solid #1a3a1a", color: "#a3e6a3", padding: "4px 8px", fontFamily: "inherit", fontSize: 12, minWidth: 200 }}
                  />
                  <button
                    onClick={manualStep}
                    style={{ fontSize: 12, padding: "5px 14px", background: "#1a3a1a", border: "1px solid #fbbf24", color: "#fbbf24", fontFamily: "inherit", cursor: "pointer" }}
                  >
                    EXECUTE
                  </button>
                </div>
              </div>
            )}

            <div ref={scrollRef} style={{ height: 520, overflowY: "auto", border: "1px solid #1a3a1a", padding: 12 }}>
              {steps.length === 0 ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#2d5a2d", gap: 8 }}>
                  <div style={{ fontSize: 32 }}>◉</div>
                  <div style={{ fontSize: 12, letterSpacing: 2 }}>AWAITING EPISODE START</div>
                  <div style={{ fontSize: 11, color: "#1a3a1a" }}>{envOnline ? "environment ready" : "connect to environment first"}</div>
                </div>
              ) : (
                steps.map((s, i) => (
                  <ToolCallCard key={i} {...s} />
                ))
              )}
              {isRunning && (
                <div style={{ display: "flex", gap: 6, alignItems: "center", padding: 8, color: "#4ade80", fontSize: 12 }}>
                  <span style={{ animation: "blink 0.8s infinite" }}>█</span>
                  <span style={{ letterSpacing: 2 }}>AGENT REASONING...</span>
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ border: "1px solid #1a3a1a", flex: 1 }}>
              <div style={{ padding: "8px 14px", borderBottom: "1px solid #1a3a1a", fontSize: 10, color: "#3d6b3d", letterSpacing: 2 }}>
                CURRENT OBSERVATION
              </div>
              <div style={{ padding: 12, height: 280, overflowY: "auto", fontSize: 11 }}>
                {observation ? (
                  <>
                    <div style={{ color: "#fbbf24", marginBottom: 8, letterSpacing: 1 }}>USERS ({observation.users?.length ?? 0})</div>
                    {observation.users?.map(u => (
                      <div key={u.user_id} style={{ display: "flex", gap: 8, marginBottom: 4, fontSize: 11 }}>
                        <span style={{ color: u.user_type === "bot" ? "#ef4444" : "#4ade80" }}>
                          {u.user_type === "bot" ? "⚙" : "○"}
                        </span>
                        <span style={{ color: u.user_type === "bot" ? "#f87171" : "#a3e6a3" }}>{u.user_id}</span>
                        <span style={{ color: "#2d5a2d", marginLeft: "auto" }}>{u.user_type}</span>
                      </div>
                    ))}

                    <div style={{ color: "#fbbf24", margin: "12px 0 8px", letterSpacing: 1 }}>SUBSCRIPTIONS ({observation.subscriptions?.length ?? 0})</div>
                    {observation.subscriptions?.map(s => (
                      <div key={s.subscription_id} style={{ marginBottom: 4, color: "#6b9e6b", fontSize: 11 }}>
                        <span style={{ color: "#a3e6a3" }}>{s.subscription_id}</span>
                        {" — "}{s.software} ${s.monthly_cost}/mo
                      </div>
                    ))}

                    <div style={{ marginTop: 12, color: "#34d399", fontSize: 12 }}>
                      BUDGET REMAINING: <strong>${observation.budget_remaining?.toLocaleString()}</strong>
                    </div>

                    {observation.pending_actions?.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <span style={{ color: "#fb923c", letterSpacing: 1, fontSize: 11 }}>FLAGGED: </span>
                        {observation.pending_actions.map(p => (
                          <div key={p} style={{ fontSize: 11, color: "#fb923c", paddingLeft: 8 }}>⚑ {p}</div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: "#2d5a2d", fontSize: 12 }}>no observation yet</div>
                )}
              </div>
            </div>

            <div style={{ border: "1px solid #1a3a1a", padding: 12 }}>
              <div style={{ fontSize: 10, color: "#3d6b3d", letterSpacing: 2, marginBottom: 10 }}>TRAP REFERENCE</div>
              <div style={{ marginBottom: 8 }}>
                <div style={{ color: "#ef4444", fontSize: 12, marginBottom: 2 }}>TRAP 1 — BOT CANCELLATION</div>
                <div style={{ fontSize: 11, color: "#5a3a3a" }}>Cancel a CI/CD bot → −3.0 reward</div>
                <div style={{ fontSize: 11, color: "#3d6b3d" }}>Defence: check user_type = bot</div>
              </div>
              <div>
                <div style={{ color: "#f87171", fontSize: 12, marginBottom: 2 }}>TRAP 2 — ANNUAL CONTRACT FEE</div>
                <div style={{ fontSize: 11, color: "#5a3a3a" }}>Cancel without check_contract → −$fee/1000</div>
                <div style={{ fontSize: 11, color: "#3d6b3d" }}>Defence: always check_contract first</div>
              </div>
            </div>

            <div style={{ border: "1px solid #1a3a1a", padding: 12 }}>
              <div style={{ fontSize: 10, color: "#3d6b3d", letterSpacing: 2, marginBottom: 8 }}>TOOL REWARDS</div>
              {Object.entries(TOOL_COLORS).filter(([k]) => k !== "__FORMAT_ERROR__").map(([tool, color]) => (
                <div key={tool} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <span style={{ color, fontSize: 13 }}>{TOOL_ICONS[tool]}</span>
                  <span style={{ fontSize: 11, color: "#6b9e6b" }}>{tool}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ marginTop: 16, borderTop: "1px solid #1a3a1a", paddingTop: 12, display: "flex", justifyContent: "space-between", fontSize: 10, color: "#2d5a2d", letterSpacing: 1 }}>
          <span>META × SCALER OPENENV HACKATHON 2026 · BANGALORE</span>
          <span>QWEN 2.5-7B · UNSLOTH QLORA · SFT → PPO</span>
          <span style={{ animation: "blink 3s infinite" }}>ENVAUDIT v1.0.0</span>
        </div>
      </div>
    </div>
  );
}