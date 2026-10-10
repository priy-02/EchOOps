import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowRight, BrainCircuit, Check, CircleHelp, Clock3, Database, Play, RefreshCw, Search, ShieldAlert, Sparkles, Waves, X } from 'lucide-react';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/$/, '');
const API = `${API_ORIGIN}/api/v1`;

type MemoryMatch = { id?: string | null; text: string; type?: string | null; metadata?: Record<string, unknown> };
type ActionOutcome = { id: string; action: string; status: 'succeeded' | 'failed'; result: string };
type Incident = {
  id: string; title: string; service: string; severity: string; status: string; environment: string;
  symptoms: string[]; logs: string[]; metrics: Record<string, number | null>; events: { at: string; label: string; detail: string }[];
  actions: ActionOutcome[]; root_cause: string | null; resolution: string | null; analyzed: boolean; recall_done: boolean;
  recall: { query: string | null; matches: MemoryMatch[]; source: string; count: number };
  strategy_adapted: boolean; recommendation: any; retained: boolean;
};

async function request(path: string, method = 'GET', body?: unknown) {
  if (!API_ORIGIN) throw new Error('Set VITE_API_BASE_URL to the deployed EchoOps API origin.');
  const response = await fetch(`${API}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

export default function App() {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [recall, setRecall] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [lastAction, setLastAction] = useState<ActionOutcome | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const refreshIncident = useCallback(async (id: string) => {
    const latest = await request(`/incidents/${encodeURIComponent(id)}`);
    setIncident(latest);
    setRecall(latest.recall_done ? latest.recall : null);
    setPlan(latest.recommendation || null);
    setLastAction(latest.actions[latest.actions.length - 1] || null);
    return latest as Incident;
  }, []);

  useEffect(() => {
    if (!API_ORIGIN) { setError('Set VITE_API_BASE_URL to the deployed EchoOps API origin.'); return; }
    let live = true;
    Promise.all([fetch(`${API_ORIGIN}/health`).then(r => r.json()), request('/incidents')])
      .then(([healthResult, incidentList]) => {
        if (!live) return;
        setHealth(healthResult);
        const latest = incidentList[incidentList.length - 1] as Incident | undefined;
        if (latest) {
          setIncident(latest);
          setRecall(latest.recall_done ? latest.recall : null);
          setPlan(latest.recommendation || null);
          setLastAction(latest.actions[latest.actions.length - 1] || null);
        }
      })
      .catch(() => { if (live) setError('Cannot reach the EchoOps API. Start the backend, then reload this page.'); });
    return () => { live = false; };
  }, []);

  const run = async (task: () => Promise<any>, success: string) => {
    setBusy(true); setError(''); setNotice('');
    try { const result = await task(); setNotice(success); return result; }
    catch (err) { setError(err instanceof Error ? err.message : 'The operation failed.'); return null; }
    finally { setBusy(false); }
  };

  const startIncident = async (number: string) => run(async () => {
    const created = await request('/incidents', 'POST', { incident_number: number, scenario: 'payment_api_503' });
    setIncident(created); setAnalysis(null); setRecall(null); setPlan(null); setLastAction(null);
    return created;
  }, `${number} started in the deterministic simulator.`);

  const investigate = async () => {
    if (!incident) return;
    await run(async () => {
      const result = await request(`/incidents/${incident.id}/analyze`, 'POST');
      setAnalysis(result); await refreshIncident(incident.id); return result;
    }, 'Investigation complete. Review current evidence, then run Hindsight Recall.');
  };

  const recallHistory = async () => {
    if (!incident) return;
    await run(async () => {
      const result = await request(`/incidents/${incident.id}/recall`, 'POST');
      setRecall(result); await refreshIncident(incident.id); return result;
    }, 'Hindsight Recall completed. The panel shows the actual bank results.');
  };

  const recommend = async () => {
    if (!incident) return;
    await run(async () => {
      const result = await request(`/incidents/${incident.id}/plan`, 'POST');
      setPlan(result); await refreshIncident(incident.id); return result;
    }, 'Recommendation generated from current evidence and recalled experience.');
  };

  const doAction = async (action: string) => {
    if (!incident) return;
    await run(async () => {
      const result = await request(`/incidents/${incident.id}/actions`, 'POST', { action });
      setLastAction(result); await refreshIncident(incident.id); return result;
    }, 'Simulator recorded the action outcome.');
  };

  const retainExperience = async () => {
    if (!incident) return;
    await run(async () => {
      const result = await request(`/incidents/${incident.id}/learn`, 'POST');
      await refreshIncident(incident.id); return result;
    }, 'Resolved experience was submitted to Hindsight Retain.');
  };

  const resetDemo = async () => run(async () => {
    const result = await request('/demo/reset', 'POST');
    setIncident(null); setAnalysis(null); setRecall(null); setPlan(null); setLastAction(null);
    return result;
  }, 'Simulator reset. Persistent Hindsight memories were left untouched.');
  const nextAction = lastAction?.action === 'inspect_connection_pool'
    ? 'increase_connection_pool'
    : (plan?.strategy_adapted || (lastAction?.action === 'restart_service' && lastAction.status === 'failed'))
      ? 'inspect_connection_pool' : 'restart_service';
  const actionLabel = nextAction === 'restart_service' ? 'Simulate restart'
    : nextAction === 'inspect_connection_pool' ? 'Inspect connection pool'
      : plan?.strategy_adapted ? 'Apply learned strategy · increase pool' : 'Increase connection pool';
  const canRetain = incident?.status === 'resolved' && !incident.retained;

  return <div className="console-shell">
    <aside className="console-sidebar">
      <a className="console-brand" href="#top" aria-label="EchoOps home"><span className="brand-symbol"><Waves size={19}/></span><span>echoops</span></a>
      <div className="console-workspace"><span className="workspace-mark">E</span><span><b>EchoOps Demo</b><small>Incident response agent</small></span></div>
      <div className="sidebar-caption">WORKFLOW</div>
      <div className="workflow-nav"><span className="workflow-nav-active"><Activity size={16}/> Incident console</span></div>
      <div className="sidebar-bottom"><span className={'health-led '+(health?.hindsight?.configured ? 'ready' : 'warning')}/><span><b>{health?.hindsight?.configured ? 'Hindsight configured' : 'Hindsight setup needed'}</b><small>{health?.hindsight?.configured ? 'Credentials and bank ID present' : 'Configure bank and API key'}</small></span></div>
    </aside>
    <main className="console-main" id="top">
      <header className="console-topbar"><div className="console-breadcrumb">EchoOps <span>/</span> <b>Incident console</b></div><div className="console-tools"><div className="console-search"><Search size={15}/><span>Incident learning workflow</span></div><button className="top-icon" aria-label="Help"><CircleHelp size={17}/></button><span className="profile-avatar" aria-label="EchoOps demo user">EO</span></div></header>
      <div className="console-content">
        <div className="console-overline"><span className="live-dot"/> SIMULATED INCIDENT ENVIRONMENT <span className="overline-sep">·</span> HINDSIGHT MEMORY</div>
        <div className="console-heading"><div><h1>Incident response console</h1><p>One incident at a time. Every resolved response teaches the next one.</p></div><button className="button button-secondary reset-button" onClick={resetDemo} disabled={busy}><RefreshCw size={14}/> Reset simulator</button></div>

        {!health?.hindsight?.configured && <section className="config-notice" role="status"><AlertTriangle size={17}/><div><b>Connect Hindsight to run the learning demo</b><p>Set <code>HINDSIGHT_API_KEY</code> and <code>HINDSIGHT_BANK_ID</code> in the backend environment. EchoOps never substitutes local demo memories.</p></div></section>}
        {error && <div className="message message-error" role="alert"><X size={15}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={14}/></button></div>}
        {notice && <div className="message message-success" role="status"><Check size={15}/>{notice}<button onClick={()=>setNotice('')} aria-label="Dismiss notification"><X size={14}/></button></div>}

        <section className="runbar panel-soft"><div><span className="runbar-label">DETERMINISTIC DEMO CONTROLS</span><p>Run the same payment failure twice and watch real Hindsight memory change the response.</p></div><div className="runbar-actions"><button className="button button-primary" onClick={()=>startIncident('INC-1042')} disabled={busy}><Play size={14}/> Run Incident #1</button><button className="button button-secondary" onClick={()=>startIncident('INC-1087')} disabled={busy}><RefreshCw size={14}/> Run similar Incident #2</button></div></section>

        {!incident ? <section className="empty-console panel"><div className="empty-console-icon"><ShieldAlert size={21}/></div><h2>Ready for the first incident</h2><p>Start Incident #1 to investigate a simulated Payment API outage.</p><button className="button button-primary" onClick={()=>startIncident('INC-1042')} disabled={busy}><Play size={14}/> Run Incident #1</button></section> : <>
          <div className="incident-summary panel"><div className="incident-summary-title"><span className="incident-alert-icon"><ShieldAlert size={18}/></span><div><span className="summary-label">CURRENT INCIDENT</span><h2>{incident.id} <span>·</span> {incident.title}</h2><p>{incident.service} <span>·</span> Simulated production <span>·</span> <i className="severity-dot"/> Critical</p></div></div><span className={'incident-status '+(incident.status==='resolved'?'status-resolved':'')}>{incident.status==='resolved'?'Resolved':'Investigating'}</span></div>

          <div className="work-grid">
            <section className="panel current-panel"><div className="section-heading"><div><span className="section-kicker">01 / CURRENT INCIDENT</span><h3>Evidence & investigation</h3></div><Activity size={17}/></div>
              <div className="symptom-list">{incident.symptoms.map(symptom=><span className="symptom-chip" key={symptom}>{symptom}</span>)}</div>
              <div className="metric-strip"><div><small>Error rate</small><b>{incident.metrics.error_rate ?? '—'}{incident.metrics.error_rate === null ? '' : '%'}</b></div><div><small>Traffic</small><b>{incident.metrics.requests_per_min?.toLocaleString() ?? '—'}<em>/min</em></b></div><div><small>Pool use</small><b>{incident.metrics.pool_utilization === null ? 'Not yet inspected' : `${incident.metrics.pool_utilization}%`}</b></div></div>
              <div className="logs"><div className="subsection-label"><span>SIMULATED LOGS</span><span>{incident.logs.length} entries</span></div>{incident.logs.map((line,index)=><div className="log-line" key={`${index}-${line}`}><span className="log-time">09:{42+index}:11</span><code>{line}</code></div>)}</div>
              {analysis && <div className="hypothesis"><span className="subsection-label">INVESTIGATION FINDING</span><p>{incident.root_cause || analysis.initial_hypothesis}</p><small>Reasoning: {analysis.reasoning_mode}</small></div>}
              <div className="action-row"><button className="button button-primary" onClick={investigate} disabled={busy}><Activity size={14}/> Investigate</button><span className="simulator-note">Simulator only · no production systems affected</span></div>
            </section>

            <section className="panel memory-panel"><div className="section-heading"><div><span className="section-kicker">02 / HINDSIGHT RECALL</span><h3>Historical experience</h3></div><BrainCircuit size={18}/></div>
              {!recall ? <div className="recall-empty"><div className="recall-icon"><BrainCircuit size={19}/></div><p>Recall runs against your configured Hindsight bank after investigation.</p><button className="button button-secondary" onClick={recallHistory} disabled={busy || !incident.analyzed}><BrainCircuit size={14}/> Recall historical experience</button></div> : <>
                <div className={'recall-status '+(recall.count ? 'has-memory' : '')}><span className="recall-status-dot"/><div><b>{recall.count ? (recall.count === 1 ? 'HISTORICAL ECHO FOUND' : `${recall.count} HINDSIGHT RESULTS`) : 'NO RELEVANT EXPERIENCE FOUND'}</b><small>Source: actual Hindsight Recall results</small></div><span className="recall-count">{recall.count}</span></div>
                {recall.matches.length ? <div className="memory-results">{recall.matches.map((match: MemoryMatch,index: number)=><article className="memory-result" key={match.id || `${index}-${match.text.slice(0,24)}`}><span className="memory-type">{match.type || 'HISTORICAL EXPERIENCE'}</span><p>{match.text}</p>{match.metadata?.incident_id != null && <small>Source incident: {String(match.metadata.incident_id)}</small>}</article>)}</div> : <p className="no-memory-copy">Hindsight returned no relevant memories. The agent will use its generic first response.</p>}
                <button className="button button-secondary recall-again" onClick={recallHistory} disabled={busy}><RefreshCw size={13}/> Recall again</button>
              </>}
            </section>

            <section className="panel recommendation-panel"><div className="section-heading"><div><span className="section-kicker">03 / RESPONSE PLAN</span><h3>Recommendation</h3></div><Sparkles size={18}/></div>
              {!plan ? <div className="plan-empty"><p>Investigate, then recall, before generating a recommendation.</p><button className="button button-primary" onClick={recommend} disabled={busy || !incident.analyzed || !incident.recall_done}><Sparkles size={14}/> Generate recommendation</button></div> : <>
                {plan.memory_influenced && <div className="memory-influenced"><Check size={15}/><b>MEMORY INFLUENCED DECISION</b></div>}
                <div className="recommendation-body"><span className="recommend-label">RECOMMENDED ACTION</span><h4>{plan.recommendation}</h4><p>{plan.reason}</p><div className="plan-facts"><div><small>CURRENT EVIDENCE</small><span>{plan.current_evidence}</span></div><div><small>EXPECTED RESULT</small><span>{plan.expected_result}</span></div><div><small>RISK · CONFIDENCE</small><span>{plan.risk} · {Math.round(plan.confidence * 100)}%</span></div></div></div>
                {plan.memory_influenced && <div className="recalled-outcomes"><div><ArrowDownRight size={14}/><span><b>PREVIOUS APPROACH FAILED</b><small>{plan.previous_approach_failed}</small></span></div><div><Check size={14}/><span><b>PREVIOUS RESOLUTION SUCCEEDED</b><small>{plan.previous_resolution_succeeded}</small></span></div></div>}
                <button className="button button-primary action-button" onClick={()=>doAction(nextAction)} disabled={busy || incident.status==='resolved'}><Play size={14}/>{actionLabel}</button>
                {lastAction && <div className={'action-result '+(lastAction.status==='failed'?'result-failed':'result-success')}><span>{lastAction.status==='failed'?<ArrowDownRight size={15}/>:<Check size={15}/>}</span><div><b>{lastAction.action.replace(/_/g, ' ')} · {lastAction.status.toUpperCase()}</b><p>{lastAction.result}</p></div></div>}
              </>}
            </section>

            <section className="panel timeline-panel"><div className="section-heading"><div><span className="section-kicker">04 / LEARNING LOOP</span><h3>Incident timeline</h3></div><Clock3 size={17}/></div><div className="timeline-list">{incident.events.map((event,index)=><div className="timeline-event" key={`${event.label}-${index}`}><span className="timeline-marker">{index+1}</span><div><b>{event.label}</b><p>{event.detail}</p></div></div>)}{incident.retained && <div className="retained-proof"><Check size={15}/><span><b>LESSON RETAINED IN HINDSIGHT</b><small>Persistent experience stored for future Recall</small></span></div>}</div>
              {incident.status==='resolved' && <div className="resolution-proof"><div><Check size={17}/><span><b>Incident resolved</b><small>{incident.root_cause} · {incident.resolution}</small></span></div><button className="button button-primary" onClick={retainExperience} disabled={busy || incident.retained}><Database size={14}/>{incident.retained?'Experience retained':'Retain experience'}</button></div>}
              {incident.status!=='resolved' && <div className="timeline-next"><ArrowRight size={14}/> Resolve the incident, then retain the full experience in Hindsight.</div>}
            </section>
          </div>
        </>}
        <footer className="console-footer"><span>EchoOps · Every incident leaves an echo. Every response gets smarter.</span><span><span className={'health-led '+(health?.hindsight?.configured?'ready':'warning')}/>{health?.hindsight?.configured?'Hindsight configured':'Hindsight not configured'}</span></footer>
      </div>
    </main>
  </div>;
}