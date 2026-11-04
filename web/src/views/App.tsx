import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, AlertTriangle, ArrowUpRight, Check, ChevronDown, Command, Droplets, FlaskConical, Gauge, HardDrive, Home, Info, Layers, Moon, Play, RotateCcw, Search, Sun, Waves, X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getHealth, getMetrics, getReplay, getScenarios, getTelemetry, getUnits, ingestCsv, simulateEvent, whatIf } from '../api'
import { useStore } from '../store'
import type { EventKind, IngestResponse, Metrics, Reading, Scenario, StageHealth } from '../types'

const TwinScene = lazy(() => import('./TwinScene').then((module) => ({ default: module.TwinScene })))

const nav = [
  { to: '/twin', label: 'Twin', icon: Layers }, { to: '/why', label: 'Why flow changes', icon: Waves },
  { to: '/app', label: 'Home concept', icon: Home }, { to: '/fleet', label: 'Fleet', icon: Activity },
  { to: '/evidence', label: 'Evidence', icon: FlaskConical }, { to: '/hardware', label: 'Bench readiness', icon: HardDrive },
  { to: '/about', label: 'Limits & claims', icon: Info }, { to: '/demo', label: 'Guided tour', icon: Play },
]

const stageNames: Record<string, string> = { sediment: 'Sediment', uf: 'UF membrane', carbon: 'Carbon', ro: 'RO membrane' }
const stageIcons: Record<string, string> = { sediment: '01', uf: '02', carbon: '03', ro: '04' }
const C = { aqua: '#56dfcf', amber: '#f3bb67', red: '#ff7d78', green: '#76d6a0' }
const number = (value?: number | null, digits = 1) => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })
const errorLabel = 'Data unavailable. Run the local pipeline to create evidence.'

function Provenance({ children = 'SIMULATED' }: { children?: string }) {
  return <span className="provenance"><i />{children}</span>
}

function Panel({ title, eyebrow, action, children, className = '' }: { title?: string; eyebrow?: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>
    {(title || eyebrow || action) && <div className="panel-head">
      <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}{title && <h2>{title}</h2>}</div>{action}
    </div>}
    {children}
  </section>
}

function SectionTitle({ kicker, title, description, provenance = true }: { kicker: string; title: string; description: string; provenance?: boolean }) {
  return <div className="section-title"><div><div className="eyebrow">{kicker}</div><h1>{title}</h1><p>{description}</p></div>{provenance && <Provenance />}</div>
}

function Metric({ label, value, suffix, detail, tone = 'aqua' }: { label: string; value: string; suffix?: string; detail?: string; tone?: string }) {
  return <div className="metric"><span className="metric-label">{label}</span><div className={`metric-value tone-${tone}`}>{value}<small>{suffix}</small></div>{detail && <span className="metric-detail">{detail}</span>}</div>
}

function FallbackSchematic({ current }: { current?: Reading }) {
  return <svg className="schematic" viewBox="0 0 760 340" role="img" aria-label="Two-dimensional purifier flow schematic">
    <defs><linearGradient id="shell" x2="0" y2="1"><stop stopColor="#243442" /><stop offset="1" stopColor="#101a24" /></linearGradient><linearGradient id="flow" x2="1"><stop stopColor="#56dfcf" stopOpacity=".2" /><stop offset=".5" stopColor="#56dfcf" /><stop offset="1" stopColor="#56dfcf" stopOpacity=".2" /></linearGradient></defs>
    <rect x="82" y="38" width="595" height="238" rx="24" fill="url(#shell)" stroke="#415663" strokeWidth="2" />
    <path d="M118 149H650" stroke="url(#flow)" strokeWidth="4" strokeDasharray="10 12" />
    {['Sediment', 'Carbon', 'RO', 'UF', 'UV', 'Mineral'].map((name, i) => <g key={name} transform={`translate(${130 + i * 82} 116)`}>
      <rect width="52" height="68" rx="18" fill={i === 2 ? '#183f48' : '#1a2732'} stroke={i === 2 ? C.aqua : '#718590'} />
      <rect x="8" y="10" width="36" height="9" rx="4" fill={i === 2 ? C.aqua : '#778d99'} opacity=".65" />
      <text x="26" y="89" textAnchor="middle" fill="#aebec8" fontSize="10">{name}</text>
    </g>)}
    <circle cx="577" cy="69" r="22" fill="#132e38" stroke={C.aqua} /><path d="M570 69h14m-7-7v14" stroke={C.aqua} strokeWidth="2" />
    <text x="116" y="78" fill="#90a2ad" fontSize="11">FEED</text><text x="592" y="218" fill="#90a2ad" fontSize="11">TANK</text>
    <rect x="603" y="194" width="34" height="54" rx="8" fill="#182b35" stroke="#536d7a" />
    <text x="128" y="317" fill="#90a2ad" fontSize="11">FLOW {number(current?.flow_l_h, 1)} L/H</text>
    <text x="462" y="317" fill="#90a2ad" fontSize="11">VIRTUAL PRESSURE {number(current?.pressure_virtual_bar, 2)} BAR</text>
  </svg>
}

function HealthRing({ value, size = 56, stage }: { value: number; size?: number; stage: string }) {
  const radius = 20; const circumference = 2 * Math.PI * radius; const color = value < 0.55 ? C.red : value < 0.78 ? C.amber : C.green
  return <div className="ring-wrap" title={`${stage}: ${number(value * 100, 0)} percent estimated health`}>
    <svg width={size} height={size} viewBox="0 0 52 52" aria-label={`${stage} estimated health ${number(value * 100, 0)} percent`} role="img">
      <circle cx="26" cy="26" r={radius} fill="none" stroke="rgba(167,192,202,.15)" strokeWidth="4" />
      <circle cx="26" cy="26" r={radius} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference * (1 - Math.max(0, Math.min(1, value)))} transform="rotate(-90 26 26)" />
      <text x="26" y="29" textAnchor="middle" fontSize="11" fill="currentColor">{number(value * 100, 0)}</text>
    </svg>
  </div>
}

function StageInspector({ health, selected, onSelect }: { health: StageHealth[]; selected: string; onSelect: (stage: string) => void }) {
  return <div className="stage-list">
    {health.map((item) => <button className={`stage-row ${selected === item.stage ? 'selected' : ''}`} key={item.stage} onClick={() => onSelect(item.stage)} aria-label={`Inspect ${stageNames[item.stage] || item.stage}`}>
      <span className="stage-index">{stageIcons[item.stage]}</span><HealthRing value={item.health_fraction} stage={item.stage} size={50} />
      <span className="stage-copy"><b>{stageNames[item.stage] || item.stage}</b><small>{item.cause}</small></span>
      <span className="stage-rul"><b>{number(item.rul_days, 0)}d</b><small>estimated</small></span>
    </button>)}
  </div>
}

function TwinPage() {
  const { scenario, setScenario, unitId, setUnitId } = useStore()
  const scenarios = useQuery({ queryKey: ['scenarios'], queryFn: getScenarios })
  const units = useQuery({ queryKey: ['units'], queryFn: getUnits })
  useEffect(() => {
    if (!units.data?.length) return
    if (!unitId) {
      const match = units.data.find((u) => u.scenario === scenario) || units.data[0]
      setUnitId(match.unit_id)
      if (match.scenario && match.scenario !== scenario) {
        setScenario(match.scenario)
      }
    }
  }, [unitId, units.data, scenario, setUnitId, setScenario])
  const telemetry = useQuery({ queryKey: ['telemetry', unitId], queryFn: () => getTelemetry(unitId), enabled: !!unitId })
  const healthResult = useQuery({ queryKey: ['health', unitId], queryFn: () => getHealth(unitId), enabled: !!unitId })
  const metricsResult = useQuery({ queryKey: ['metrics'], queryFn: getMetrics })
  const [position, setPosition] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(24)
  const [stage, setStage] = useState('ro')
  const [preset, setPreset] = useState<'overview' | 'exploded' | 'xray'>('overview')
  const [viewMode, setViewMode] = useState<'3d' | '2d'>('3d')
  const [eventMessage, setEventMessage] = useState('')
  const [localReadings, setLocalReadings] = useState<Reading[] | null>(null)
  const rows = localReadings || telemetry.data?.readings || []
  const current = rows[Math.min(position, Math.max(rows.length - 1, 0))]
  const baseHealth = healthResult.data?.health || []
  const health = localReadings && current ? baseHealth.map((item) => {
    const prediction = current[`pred_p1_${item.stage}_d` as keyof Reading]
    if (typeof prediction !== 'number') return item
    const baseline = localReadings[0]
    const ratio = (current.hydraulic_resistance_index || 1) / Math.max(baseline.hydraulic_resistance_index || 1, 0.01)
    const healthByStage: Record<string, number> = {
      sediment: Math.max(0, Math.min(1, 1 - 0.05 * (ratio - 1))),
      uf: Math.max(0, Math.min(1, 1 - 0.04 * (ratio - 1))),
      carbon: Math.max(0, Math.min(1, 1 - (current.carbon_exposure_index || 0))),
      ro: Math.max(0, Math.min(1, current.ro_permeability_est_lmh_bar / 8)),
    }
    const radius = metricsResult.data?.value.stages[item.stage]?.conformal_q_days_by_horizon?.['21'] || 0
    const dailyLitres = current.daily_litres_mean_l || current.litres_dispensed_l || 0
    return { ...item, rul_days: prediction, rul_litres: prediction * dailyLitres,
      health_fraction: healthByStage[item.stage] ?? item.health_fraction,
      interval_days: [Math.max(0, prediction - radius), prediction + radius],
      confidence: item.stage === 'carbon' ? 'low' as const : item.confidence,
      cause: 'Simulated event replay', explanation: 'The event-adjusted forecast uses the frozen model and simulator-derived telemetry.' }
  }) : baseHealth
  const activeHealth = health.find((item) => item.stage === stage) || health[0]
  const offline = telemetry.data?.offline ?? true
  useEffect(() => { setPosition(Math.max(0, (rows.length || 1) - 1)) }, [rows.length, unitId])
  useEffect(() => {
    if (!playing || rows.length < 2) return
    const timer = window.setInterval(() => setPosition((i) => (i + 1) % rows.length), Math.max(45, 1000 / speed))
    return () => window.clearInterval(timer)
  }, [playing, rows.length, speed])
  async function inject(kind: EventKind) {
    setEventMessage('')
    try { const result = await simulateEvent(scenario, kind); setLocalReadings(result); setPosition(Math.max(0, result.length - 1)); setEventMessage('Event-adjusted forecast loaded from the simulator.') }
    catch (error) { setEventMessage(error instanceof Error ? error.message : 'Event replay is unavailable.'); }
  }
  const eventButtons: [EventKind, string][] = [
    ['silt_spike', 'Silt spike'], ['tanker_tds_switch', 'Tanker switch'], ['chlorine_breakthrough', 'Chlorine load'],
    ['cold_snap', 'Cold snap'], ['pump_wear', 'Pump wear'], ['usage_change', 'Usage shift'],
  ]
  return <div className="page twin-page">
    <SectionTitle kicker="Mission control / digital twin" title="Know what changed before you change the filter." description="A configurable purifier twin separates feed-water stress from developing hydraulic resistance." />
    <div className="twin-grid">
      <aside className="control-rail">
        <Panel eyebrow="Water profile" title="Scenario">
          <label className="field-label" htmlFor="scenario">Feed-water scenario</label>
          <div className="select-wrap"><select id="scenario" value={scenario} onChange={(e) => {
            const next = e.target.value
            setScenario(next)
            setLocalReadings(null)
            setEventMessage('')
            const match = units.data?.find((u) => u.scenario === next)
            if (match) {
              setUnitId(match.unit_id)
            }
          }}>
            {(scenarios.data?.length ? scenarios.data : [{ id: current?.scenario || scenario, tds_mg_l: 0, turbidity_ntu: 0, chlorine_mg_l: 0, hardness: 0, temp_c: 0 }]).map((option) => <option key={option.id} value={option.id}>{option.id.replaceAll('_', ' ')}</option>)}
          </select><ChevronDown size={15} /></div>
          <div className="scenario-readout"><span>Feed TDS <b>{number(current?.tds_in_mg_l, 0)} <small>mg/L</small></b></span><span>Turbidity <b>{number(current?.turbidity_ntu, 1)} <small>NTU</small></b></span></div>
        </Panel>
        <Panel eyebrow="Controlled perturbations" title="Inject an event">
          <div className="event-grid">{eventButtons.map(([kind, label]) => <button key={kind} className="event-button" onClick={() => inject(kind)}>{label}<ArrowUpRight size={13} /></button>)}</div>
          {eventMessage && <p className="inline-note" role="status">{eventMessage}</p>}
        </Panel>
        <Panel eyebrow="Live readings" title="Operating point">
          <div className="readout-grid">
            <div><span>Permeate flow</span><b>{number(current?.flow_l_h)} <small>L/h</small></b></div>
            <div><span>Virtual pressure</span><b>{number(current?.pressure_virtual_bar, 2)} <small>bar</small></b></div>
            <div><span>Pump current</span><b>{number(current?.motor_current_a, 2)} <small>A</small></b></div>
            <div><span>Outlet TDS</span><b>{number(current?.outlet_tds_mg_l, 0)} <small>mg/L</small></b></div>
          </div>
        </Panel>
      </aside>
      <div className="twin-main">
        <Panel className="scene-panel" eyebrow="Procedural hardware / configurable topology" title="Treatment path" action={<div className="scene-modes">
          <button onClick={() => setViewMode('3d')} className={viewMode === '3d' ? 'active' : ''}>3D</button>
          <button onClick={() => setViewMode('2d')} className={viewMode === '2d' ? 'active' : ''}>2D</button>
          <span className="mode-sep" />
          {(['overview', 'exploded', 'xray'] as const).map((mode) => <button key={mode} onClick={() => setPreset(mode)} className={preset === mode ? 'active' : ''}>{mode}</button>)}
        </div>}>
          {viewMode === '2d' ? (
            <FallbackSchematic current={current} />
          ) : (
            <Suspense fallback={<FallbackSchematic current={current} />}>
              <TwinScene flow={current?.flow_l_h || 0} current={current?.motor_current_a || 0} selected={stage} preset={preset} onSelect={setStage} force3d={viewMode === '3d'} fallback={<FallbackSchematic current={current} />} />
            </Suspense>
          )}
          <div className="scene-footer"><span><i className="dot aqua" /> Feed → prefilter → RO → post-treatment → tank</span><span><Provenance /></span></div>
        </Panel>
        <div className="timeline panel">
          <div className="timeline-controls"><button className="icon-btn play-btn" onClick={() => setPlaying(!playing)} aria-label={playing ? 'Pause simulation' : 'Play simulation'}>{playing ? <span className="pause-glyph">Ⅱ</span> : <Play size={15} fill="currentColor" />}</button><span className="mono">DAY {number(current?.day, 0)}</span>
            <input aria-label="Replay timeline" type="range" min={0} max={Math.max(0, rows.length - 1)} value={position} onChange={(e) => setPosition(Number(e.target.value))} />
            <label className="speed-control">Speed<select aria-label="Playback speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={1}>1×</option><option value={8}>8×</option><option value={24}>24×</option><option value={100}>100×</option><option value={1000}>1000×</option></select></label>
          </div>
          <div className="timeline-track"><span>START</span><div className="track-line"><i style={{ left: `${rows.length > 1 ? (position / (rows.length - 1)) * 100 : 0}%` }} /></div><span>{rows.length ? `DAY ${number(rows.at(-1)?.day, 0)}` : 'NO REPLAY'}</span></div>
        </div>
      </div>
      <aside className="inspector">
        <Panel eyebrow="Stage condition" title="Health & forecast" action={<Provenance />}>{health.length ? <StageInspector health={health} selected={stage} onSelect={setStage} /> : <div className="empty-state">{errorLabel}</div>}</Panel>
        <Panel eyebrow="Selected stage" title={stageNames[stage] || stage}>
          {activeHealth ? <><div className="selected-health"><HealthRing value={activeHealth.health_fraction} size={76} stage={activeHealth.stage} /><div><b>{number(activeHealth.rul_days, 0)} days</b><span>estimated remaining life</span></div></div>
            <div className="forecast-range"><span>Replacement window</span><b>{number(activeHealth.interval_days[0], 0)} — {number(activeHealth.interval_days[1], 0)} days</b></div>
            <div className="confidence-row"><span>Confidence</span><b className={`confidence ${activeHealth.confidence}`}>{activeHealth.confidence}</b></div>
            <div className="why-box"><b><Gauge size={14} /> Why this estimate</b><p>{activeHealth.explanation}</p><span className="cause-label">{activeHealth.cause}</span></div>
          </> : <div className="empty-state">{errorLabel}</div>}
        </Panel>
        {offline && <div className="offline-banner"><Check size={14} /> Demo-Safe replay active <span>API not connected</span></div>}
      </aside>
    </div>
  </div>
}

function WhyPage() {
  const [tds, setTds] = useState(1800)
  const [temp, setTemp] = useState(25)
  const [permeability, setPermeability] = useState(8)
  const result = useQuery({ queryKey: ['whatif', tds, temp, permeability], queryFn: () => whatIf({ tds_mg_l: tds, temperature_c: temp, membrane_permeability_lmh_bar: permeability }), retry: false })
  const [golden, setGolden] = useState<Record<string, any> | null>(null)
  useEffect(() => { fetch('/evidence/physics_golden.json').then((r) => r.json()).then(setGolden).catch(() => undefined) }, [])
  const raw = result.data || (() => {
    const pi = 0.7 * 1.2 * tds / 1000; const factor = Math.exp(0.0239 * (temp - 25)); const flux = permeability * factor * Math.max(0, 4.5 - 0.15 - pi)
    return { raw_flux_lmh: flux, raw_flow_l_h: flux * 0.4, osmotic_pressure_bar: pi, net_driving_pressure_bar: 4.5 - .15 - pi, normalized_permeability_lmh_bar: permeability, normalized_health_fraction: permeability / 8 }
  })()
  const g = golden?.G1
  return <div className="page">
    <SectionTitle kicker="Physics explainer" title="Why is my flow down?" description="Raw output changes with feed water. Normalize for osmotic pressure and temperature to see whether the membrane itself changed." />
    <div className="why-layout">
      <Panel className="why-controls" eyebrow="Live what-if" title="Change the conditions">
        <Slider label="Feed TDS" value={tds} min={100} max={2500} step={50} unit="mg/L" onChange={setTds} />
        <Slider label="Water temperature" value={temp} min={10} max={35} step={1} unit="°C" onChange={setTemp} />
        <Slider label="Membrane permeability" value={permeability} min={3} max={8} step={0.1} unit="LMH/bar" onChange={setPermeability} />
        <div className="equation-card"><div className="eyebrow">Solution-diffusion model</div><code>Jw = A · fT(T) · (Pm − Pperm − Δπ)</code><small>Δπ responds to dissolved solids; fT corrects for temperature.</small></div>
      </Panel>
      <div className="why-result-grid">
        <Panel eyebrow="What a sensor sees" title="Raw permeate flow" className="big-result">
          <div className="result-number">{number(raw.raw_flow_l_h, 2)}<small> L/h</small></div><div className="result-caption">The same membrane can produce less water when TDS rises or feed water gets colder.</div>
          <div className="mini-stats"><span>Osmotic pressure <b>{number(raw.osmotic_pressure_bar, 3)} bar</b></span><span>Net driving pressure <b>{number(raw.net_driving_pressure_bar, 3)} bar</b></span></div>
        </Panel>
        <Panel eyebrow="What physics reveals" title="Normalized membrane health" className="big-result aha">
          <div className="health-number">{number(raw.normalized_health_fraction * 100, 1)}<small>%</small></div><div className="health-track"><i style={{ width: `${Math.min(100, raw.normalized_health_fraction * 100)}%` }} /></div>
          <div className="result-caption">Flow corrected back to 25 °C and the same net driving pressure.</div>
          <div className="mini-stats"><span>Estimated permeability <b>{number(raw.normalized_permeability_lmh_bar, 2)} LMH/bar</b></span><span>Provenance <b>SIMULATED</b></span></div>
        </Panel>
      </div>
    </div>
    <Panel eyebrow="Golden example G1" title="High TDS vs. true fouling" action={<Provenance />}>
      {g ? <div className="golden-grid">
        <GoldenCard title="Healthy membrane · lower TDS" item={g.healthy_600} />
        <GoldenCard title="Healthy membrane · higher TDS" item={g.healthy_1800} ratio={g.healthy_1800.raw_flow_ratio_vs_600} />
        <GoldenCard title="Fouled membrane · same lower TDS" item={g.fouled_600} />
      </div> : <div className="empty-state">{errorLabel}</div>}
    </Panel>
    <div className="safety-note"><AlertTriangle size={16} /><span>This estimate supports maintenance planning. It does not certify drinking-water safety.</span></div>
  </div>
}

function Slider({ label, value, min, max, step, unit, onChange }: { label: string; value: number; min: number; max: number; step: number; unit: string; onChange: (value: number) => void }) {
  return <label className="slider-field"><span>{label}<b>{number(value, step < 1 ? 1 : 0)} <small>{unit}</small></b></span><input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>
}

function GoldenCard({ title, item, ratio }: { title: string; item: Record<string, number>; ratio?: number }) {
  return <div className="golden-card"><div><b>{title}</b><Provenance /></div><span>Raw flow <strong>{number(item.permeate_l_h, 3)} L/h</strong></span><span>Net pressure <strong>{number(item.ndp_bar, 3)} bar</strong></span><span>Normalized health <strong>{number(item.normalized_health * 100, 1)}%</strong></span>{ratio && <small>Raw output is {number((1-ratio)*100, 1)}% lower on higher-TDS water.</small>}</div>
}

function AppPage() {
  const { health } = useQuery({ queryKey: ['health', 'app'], queryFn: () => getHealth() }).data || { health: [] }
  const [modal, setModal] = useState(false)
  const [notice, setNotice] = useState('')
  return <div className="page">
    <SectionTitle kicker="Customer concept" title="A calmer way to plan maintenance." description="A future-facing concept for clear, explainable cartridge care. Every estimate in this prototype is simulated." />
    <div className="app-layout">
      <div className="phone-shell"><div className="phone-notch" /><div className="phone-screen">
        <div className="phone-top"><span>09:41</span><span>●●● ◖</span></div>
        <div className="phone-brand"><span className="brand-icon small">F</span><span><b>Atomberg Home</b><small>concept UI</small></span><button className="avatar">R</button></div>
        <div className="greeting"><span>Good morning</span><h2>Your water system</h2><p>Last sync from the local purifier twin</p></div>
        <div className="phone-card system-status"><div><span className="dot green" /> System condition</div><b>Running as expected</b><small>Maintenance estimates are simulated.</small></div>
        <div className="phone-stage-grid">{health.map((item) => <div className="phone-stage" key={item.stage}><HealthRing value={item.health_fraction} stage={item.stage} size={48} /><span>{stageNames[item.stage] || item.stage}</span><b>{number(item.rul_days, 0)} days</b></div>)}</div>
        <div className="phone-card replace-card"><div className="eyebrow">NEXT REPLACEMENT WINDOW</div><h3>{health[0]?.stage ? stageNames[health[0].stage] : 'Cartridge'} check</h3><p>We’ll keep watching the water conditions and your usage.</p><button className="phone-button" onClick={() => setModal(true)}>Explore cartridges <ArrowUpRight size={14} /></button></div>
        <div className="phone-notice"><AlertTriangle size={15} /><span>Maintenance estimates do not certify drinking-water safety.</span></div>
        <nav className="phone-tabs"><span>⌂<small>Home</small></span><span>◷<small>Activity</small></span><span>⚙<small>Settings</small></span></nav>
      </div></div>
      <div className="app-copy"><div className="eyebrow">AT O M B E R G  H O M E / C O N C E P T</div><h2>Useful guidance.<br /><em>Without false certainty.</em></h2><p>The concept translates the twin’s stage estimates into a clear replacement window, explains whether the signal points to changing feed water or rising resistance, and keeps the user in control.</p>
        <div className="concept-features"><div><span className="feature-icon"><Activity size={17} /></span><span><b>Stage-wise estimates</b><small>Days, litres, range, confidence, and reason.</small></span></div><div><span className="feature-icon"><Droplets size={17} /></span><span><b>Cause in plain language</b><small>Feed water shift, hydraulic signal, or usage exposure.</small></span></div><div><span className="feature-icon"><AlertTriangle size={17} /></span><span><b>Safety kept explicit</b><small>The estimate is not a potability guarantee.</small></span></div></div>
        {notice && <div className="toast-inline" role="status">{notice}</div>}
      </div>
    </div>
    {modal && <Modal title="Cartridge options · concept" onClose={() => setModal(false)}><p>This interaction is a design prototype. It does not connect to a store or submit an order.</p><div className="modal-actions"><button className="button-secondary" onClick={() => setModal(false)}>Keep watching</button><button className="button-primary" onClick={() => { setModal(false); setNotice('Concept selection saved locally for this demo.') }}>Save concept choice</button></div></Modal>}
  </div>
}

function FleetPage() {
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: getMetrics }).data?.value
  const units = useQuery({ queryKey: ['units'], queryFn: getUnits }).data || []
  const business = metrics?.business_impact
  const policy = business?.policies
  const [sortKey, setSortKey] = useState<'next_rul_days' | 'scenario'>('next_rul_days')
  const sorted = [...units].sort((a, b) => sortKey === 'scenario' ? a.scenario.localeCompare(b.scenario) : a.next_rul_days - b.next_rul_days)
  const barMax = Math.max(...Object.values(policy || {}).map((x) => x.mean_useful_life_wasted_fraction || 0), 0.01)
  return <div className="page">
    <SectionTitle kicker="Fleet view / 5–10 year direction" title="Learn from patterns across households." description="A simulated fleet view shows how regional stress and household usage could guide stocking and service planning." />
    <div className="fleet-hero-grid"><Panel className="fleet-count" eyebrow="Synthetic household cohort" title="One fleet, many water stories">
      <div className="fleet-number">{number(metrics?.cohort_units.test, 0)}<small> test units</small></div><p>From named feed-water and usage scenarios. No household or customer data is used.</p>
      <div className="scenario-chips">{[...new Set(units.map((u) => u.scenario))].slice(0, 6).map((s) => <span key={s}>{s.replaceAll('_', ' ')}</span>)}</div>
    </Panel><Panel eyebrow="Regional stress view" title="Source patterns, without a map">
      <div className="region-schematic"><div className="region north"><i /><span>North · borewell</span></div><div className="region west"><i /><span>West · hard water</span></div><div className="region south"><i /><span>South · municipal</span></div><div className="region east"><i /><span>East · seasonal</span></div><div className="region-line" /></div>
      <div className="region-legend"><span><i className="dot aqua" /> Simulated stress family</span><small>Illustrative geography, not a live map</small></div>
    </Panel></div>
    <Panel eyebrow="Policy comparison" title="What risk-based service could change" action={<Provenance />}>
      {policy ? <div className="policy-grid">{Object.entries(policy).map(([name, values]) => <div className="policy-card" key={name}><div className="policy-title"><b>{name.replaceAll('_', ' ')}</b><span>{number(values.mean_useful_life_wasted_fraction * 100, 1)}% useful life wasted</span></div><div className="policy-bar"><i style={{ width: `${Math.min(100, (values.mean_useful_life_wasted_fraction / barMax) * 100)}%` }} /></div><div className="policy-stat"><span>Failures in the simulated horizon</span><b>{number(values.cartridge_failures_per_1000_households_3y, 0)}</b></div>{values.unexpected_failures_avoided_vs_fixed != null && <div className="policy-stat"><span>Failures avoided vs schedule</span><b className="tone-aqua">{number(values.unexpected_failures_avoided_vs_fixed, 0)}</b></div>}</div>)}</div> : <div className="empty-state">{errorLabel}</div>}
      <p className="fine-print">The simulation uses a generated cohort and an adjustable replacement fraction. No cartridge costs or commercial savings are assumed.</p>
    </Panel>
    <Panel eyebrow="Generated test cohort" title="Household risk table" action={<div className="select-wrap small-select"><select aria-label="Sort households" value={sortKey} onChange={(e) => setSortKey(e.target.value as typeof sortKey)}><option value="next_rul_days">Sort by next estimate</option><option value="scenario">Sort by scenario</option></select><ChevronDown size={13} /></div>}>
      <div className="table-scroll"><table><thead><tr><th>Unit</th><th>Scenario</th><th>Last simulated day</th><th>Nearest stage RUL</th><th>Source</th></tr></thead><tbody>{sorted.slice(0, 30).map((item) => <tr key={item.unit_id}><td className="mono">{item.unit_id}</td><td>{item.scenario.replaceAll('_', ' ')}</td><td>{number(item.day, 0)}</td><td><span className={item.next_rul_days < 21 ? 'risk-high' : 'risk-normal'}>{number(item.next_rul_days, 0)} days</span></td><td><Provenance /></td></tr>)}</tbody></table></div>
    </Panel>
  </div>
}

function EvidencePage() {
  const metricsResult = useQuery({ queryKey: ['metrics'], queryFn: getMetrics })
  const metrics: Metrics | undefined = metricsResult.data?.value
  const stages = metrics ? Object.keys(metrics.stages) : []
  const [selected, setSelected] = useState('ro')
  useEffect(() => { if (stages.length && !stages.includes(selected)) setSelected(stages[0]) }, [stages, selected])
  const chosen = metrics?.stages[selected]
  const data = [30, 21, 14].map((day) => ({ horizon: `${day}d`, P1: chosen?.test.p1[String(day)]?.mae_days || 0, Raw: chosen?.test.b1[String(day)]?.mae_days || 0, Schedule: chosen?.test.b0_schedule[String(day)]?.mae_days || 0, OOD: chosen?.ood.p1[String(day)]?.mae_days || 0 }))
  const signature = metrics?.signature_matrix.delta_from_baseline || {}
  return <div className="page">
    <SectionTitle kicker="Evidence / reproducible outputs" title="Numbers with their source attached." description="The model is evaluated against exact simulator labels. Test and OOD results are reported separately; neither is field validation." />
    {!metrics && <div className="error-card">{errorLabel}</div>}
    {metrics && <>
      <div className="evidence-summary-grid"><Metric label="Generated units" value={number(Object.values(metrics.cohort_units).reduce((a, b) => a + b, 0), 0)} detail="Train / validation / test / OOD" /><Metric label="Test cohort" value={number(metrics.cohort_units.test, 0)} detail="Held out by unit" tone="green" /><Metric label="OOD cohort" value={number(metrics.cohort_units.ood, 0)} detail="Unseen perturbations" tone="amber" /><Metric label="Grouped leakage check" value={metrics.grouped_split_check ? 'PASS' : 'FAIL'} detail="Disjoint unit IDs" tone={metrics.grouped_split_check ? 'green' : 'red'} /></div>
      <div className="evidence-grid">
        <Panel eyebrow="Fixed-horizon RUL error" title={`${stageNames[selected] || selected} · mean absolute error`} action={<><div className="select-wrap small-select"><select aria-label="Evidence stage" value={selected} onChange={(e) => setSelected(e.target.value)}>{stages.map((stage) => <option key={stage} value={stage}>{stageNames[stage] || stage}</option>)}</select><ChevronDown size={13} /></div><Provenance /></>}>
          <div className="chart-wrap"><ResponsiveContainer width="100%" height={250}><BarChart data={data} barGap={5} margin={{ top: 8, right: 10, bottom: 0, left: -15 }}><CartesianGrid vertical={false} stroke="rgba(137,166,180,.13)" /><XAxis dataKey="horizon" stroke="#82949e" tickLine={false} axisLine={false} /><YAxis stroke="#82949e" tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: '#17222d', border: '1px solid #3b4c58', borderRadius: 10 }} /><Bar dataKey="P1" fill={C.aqua} radius={[4, 4, 0, 0]} /><Bar dataKey="Raw" fill="#718796" radius={[4, 4, 0, 0]} /><Bar dataKey="Schedule" fill={C.amber} radius={[4, 4, 0, 0]} /><Bar dataKey="OOD" fill={C.red} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
          <div className="chart-legend"><span><i style={{ background: C.aqua }} /> P1 physics guided</span><span><i style={{ background: '#718796' }} /> Raw features</span><span><i style={{ background: C.amber }} /> Fixed schedule</span><span><i style={{ background: C.red }} /> OOD P1</span></div>
          <div className="horizon-metrics">{data.map((item, i) => { const s = chosen?.test.p1[String([30, 21, 14][i])]; return <div key={item.horizon}><span>{item.horizon} horizon</span><b>{number(s?.mae_days)} days MAE</b><small>{number((s?.mean_absolute_relative_error || 0) * 100, 1)}% relative error</small></div> })}</div>
        </Panel>
        <Panel eyebrow="Uncertainty / split conformal" title="Held-out interval coverage" action={<Provenance />}>
          <div className="coverage-list">{stages.map((stage) => <div className="coverage-row" key={stage}><span>{stageNames[stage]}</span><div className="coverage-track"><i style={{ width: `${Math.min(100, (metrics.stages[stage].test.p1['21']?.coverage || 0) * 100)}%` }} /></div><b>{number((metrics.stages[stage].test.p1['21']?.coverage || 0) * 100, 0)}%</b><small>test @21d</small></div>)}</div>
          <p className="fine-print">Calibration radii are fitted on validation only. Nominal coverage is a target; empirical coverage can miss it.</p>
          <div className="interval-pairs">{stages.map((stage) => <span key={stage}>{stageNames[stage]} <b>±{number(metrics.stages[stage].conformal_q_days_by_horizon['21'], 0)}d</b></span>)}</div>
        </Panel>
        <Panel eyebrow="Twin perturbations" title="Observable signature deltas" action={<Provenance />}>
          <div className="table-scroll"><table className="signature-table"><thead><tr><th>Controller / condition</th><th>Flow</th><th>Fill time</th><th>Current</th><th>RPM</th><th>Ripple</th><th>Outlet TDS</th><th>Normalized A</th></tr></thead><tbody>{Object.entries(signature).map(([name, values]) => <tr key={name}><td>{name.replaceAll('_', ' ').replace(':', ' / ')}</td><td className={values.flow_l_h < 0 ? 'delta-down' : ''}>{number(values.flow_l_h, 2)}</td><td>{number(values.fill_time_h, 2)}</td><td>{number(values.current_a, 2)}</td><td>{number(values.rpm, 1)}</td><td>{number(values.current_ripple_a, 3)}</td><td>{number(values.outlet_tds_mg_l, 1)}</td><td>{number(values.normalised_permeability, 2)}</td></tr>)}</tbody></table></div><p className="fine-print">Controlled equation perturbations under two assumed controller modes. These are bench hypotheses, not real-device measurements.</p>
        </Panel>
        <Panel eyebrow="Telemetry buy-down" title="Signals included by tier" action={<Provenance />}>
          <div className="tier-grid">{Object.entries(metrics.telemetry_tiers).map(([tier, info]) => { const score = info.test?.ro?.['21']?.mae_days; return <div key={tier}><span className="tier-badge">{tier}</span><b>{number(info.n_features, 0)} inputs</b><small>{info.features.join(' · ')}</small><em>RO MAE @21d: {number(score)} days · SIMULATED</em></div> })}</div>
        </Panel>
        <Panel eyebrow="Policy simulation" title="Maintenance trade-off" action={<Provenance />}>
          <div className="business-cards">{Object.entries(metrics.business_impact.policies).map(([name, value]) => <div key={name}><b>{name.replaceAll('_', ' ')}</b><strong>{number(value.mean_useful_life_wasted_fraction * 100, 1)}%</strong><small>useful life wasted</small><span>{number(value.cartridge_failures_per_1000_households_3y, 0)} simulated failures</span>{value.unexpected_failures_avoided_vs_fixed != null && <span>Difference vs schedule: {number(value.unexpected_failures_avoided_vs_fixed, 0)} (+ means avoided)</span>}</div>)}</div><p className="fine-print">Monte Carlo policy projection from generated lifetimes; assumptions are shown in `results/metrics.json`.</p>
        </Panel>
        <Panel eyebrow="Deployability" title="Model footprint & inference" action={<Provenance />}>
          <div className="latency-list">{stages.map((stage) => <div key={stage}><span>{stageNames[stage]}</span><b>{number(metrics.inference_latency_ms_per_row_by_stage[stage], 4)} ms / row</b><small>{number(metrics.model_size_bytes_by_stage[stage] / 1024, 1)} KiB model</small></div>)}</div><p className="fine-print">Measured from the local CPU run; batch and hardware performance will differ.</p>
        </Panel>
        <Panel eyebrow="External validation" title="Public-data checks" action={<Provenance />}>
          <div className="source-list">{Object.entries(metrics.public_data_checks).map(([name, item]) => <div key={name}><b>{name.replaceAll('_', ' ')}</b><span>{item.status}</span><small>{item.reason}</small></div>)}</div>
        </Panel>
      </div>
    </>}
  </div>
}

function HardwarePage() {
  const [upload, setUpload] = useState<File | null>(null)
  const [response, setResponse] = useState<IngestResponse | null>(null)
  const [error, setError] = useState('')
  async function send() {
    if (!upload) return
    setError(''); setResponse(null)
    try { setResponse(await ingestCsv(upload)) } catch (e) { setError(e instanceof Error ? e.message : 'CSV ingest failed') }
  }
  const steps = ['Clean-water baseline sweeps', 'Ground-truth pressure calibration', 'Single-stage loading', 'Paired-fault confound checks', 'Held-out cartridge run-to-failure']
  return <div className="page">
    <SectionTitle kicker="Hardware / bench readiness" title="A calibration path from twin to bench." description="The rig is a proposal. The adapter accepts instrumented CSVs; no bench measurements have been collected." />
    <div className="hardware-grid"><Panel eyebrow="Replaceable stage rig" title="Instrumentation classes"><div className="bom-grid">{[['Pump', 'Current sensor, RPM pickup, runtime logger'], ['Hydraulics', 'Flow meters, pressure transducer, back-pressure valve'], ['Water quality', 'Feed/permeate TDS, temperature, turbidity'], ['Control', 'ESP32-class timestamped logger, isolation, pressure cutoffs']].map(([name, desc]) => <div key={name}><span className="bom-icon"><HardDrive size={16} /></span><b>{name}</b><p>{desc}</p></div>)}</div><a className="text-link" href="/hardware/BENCH_RIG.md" download>Download bench-rig proposal <ArrowUpRight size={13} /></a></Panel>
      <Panel eyebrow="Calibration protocol" title="One claim at a time"><ol className="protocol-list">{steps.map((step, i) => <li key={step}><span>{String(i + 1).padStart(2, '0')}</span>{step}</li>)}</ol><div className="wiring-note"><Gauge size={17} /><span>Use an independent pressure transducer as ground truth while fitting motor current. The line may change with controller mode and pump wear.</span></div></Panel></div>
    <div className="ingest-grid"><Panel eyebrow="Bench CSV schema" title="Required channels"><div className="schema-columns"><div><b>Timestamp & unit</b><code>timestamp · unit_id</code></div><div><b>Water</b><code>inlet_tds_mg_l · outlet_tds_mg_l · turbidity_ntu · temp_c</code></div><div><b>Hydraulics</b><code>flow_l_h · inlet_pressure_bar · motor_current_a · rpm</code></div><div><b>Use</b><code>pump_runtime_h · litres_dispensed_l</code></div></div><a className="download-sample" href="/samples/bench_like.csv" download><HardDrive size={15} /> Download twin-generated sample CSV</a><small className="fine-print">Sample is SIMULATED. It is not BENCH evidence.</small></Panel>
      <Panel eyebrow="Adapter test" title="Try the ingest path"><p className="muted">Upload a CSV matching the schema. It will be normalized into the same feature and forecast path.</p><label className="upload-box"><input type="file" accept=".csv,text/csv" onChange={(e) => setUpload(e.target.files?.[0] || null)} /><span><HardDrive size={18} />{upload ? upload.name : 'Choose a bench CSV'}</span></label><button className="button-primary" disabled={!upload} onClick={send}>Validate and estimate</button>{error && <div className="error-card compact">{error}</div>}{response && <div className="ingest-result"><div><Check size={15} /> {response.accepted_rows} rows accepted <Provenance>BENCH (not yet collected)</Provenance></div><div className="ingest-estimates">{response.stage_estimates?.map((item: StageHealth) => <span key={item.stage}>{stageNames[item.stage]} · {number(item.rul_days, 0)} days</span>)}</div><small>{response.notes?.[0]}</small></div>}</Panel></div>
    <Panel eyebrow="Suggested BOM" title="Build only after confirming the product envelope"><div className="bom-table"><span>Replaceable-stage housings</span><span>Pressure-rated tubing and shutoffs</span><span>Ground-truth pressure and flow sensors</span><span>Independent chlorine assay method</span><span>Contained challenge-water reservoir and drain</span><span>Calibration solutions and timestamped logger</span></div><p className="fine-print">Proposal only; exact part numbers and operating limits require engineering and lab review.</p></Panel>
  </div>
}

function AboutPage() {
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: getMetrics }).data?.value
  const claims = [
    ['Physics-normalized RO flux', 'Golden equations and G1 result artifact', 'Twin equation check only'],
    ['Virtual pressure from pump current', 'G3 plus calibration fit utility', 'To calibrate on bench'],
    ['Stage attribution', 'Controlled signature matrix', 'Sediment / UF confounded'],
    ['Stage-wise RUL', 'Grouped synthetic holdouts and intervals', 'Simulator-only results'],
    ['Carbon exposure forecast', 'Usage-based prior feature', 'Low confidence; chlorine not directly sensed'],
    ['Drinking-water safety', 'No supporting artifact', 'Not claimed'],
  ]
  const risks = ['Synthetic trajectories share the model equations used by P1.', 'Pump controller mode, voltage, and wear may break current-to-pressure calibration.', 'System pressure and flow cannot uniquely isolate each prefilter stage.', 'Carbon breakthrough is estimated from litres and an assumed chlorine prior.', 'No compatible external RO failure series or physical bench data was imported.']
  return <div className="page">
    <SectionTitle kicker="Claims register / limitations" title="A useful prototype needs honest edges." description="The current evidence is a reproducible simulator result. The next trust-building step is a held-out bench study." />
    <Panel eyebrow="Claim to artifact" title="What the pitch can say today"><div className="table-scroll"><table><thead><tr><th>Claim</th><th>Evidence link</th><th>Status</th></tr></thead><tbody>{claims.map(([claim, artifact, status]) => <tr key={claim}><td>{claim}</td><td>{artifact}</td><td><span className="status-pill">{status}</span></td></tr>)}</tbody></table></div></Panel>
    <Panel eyebrow="Threats to validity" title="What a skeptical reviewer should challenge"><div className="risk-list">{risks.map((risk) => <div key={risk}><AlertTriangle size={16} /><span>{risk}</span></div>)}</div></Panel>
    <div className="about-bottom"><Panel eyebrow="Evidence boundary" title="Data in this build"><div className="data-status-list">{Object.entries(metrics?.public_data_checks || {}).map(([name, status]) => <div key={name}><span>{name.replaceAll('_', ' ')}</span><b>{status.status}</b></div>)}</div><div className="fine-print">No household, customer, or bench telemetry was used.</div></Panel><Panel eyebrow="Safety" title="Maintenance guidance only"><div className="safety-callout"><AlertTriangle size={20} /><p>FilterTwin predictions guide maintenance. They do not certify potability, pathogen removal, or drinking-water safety.</p></div></Panel></div>
  </div>
}

function DemoPage() {
  const navigate = useNavigate()
  const { presenter, setPresenter } = useStore()
  const { tourActive: active, setTourActive, tourElapsed: elapsed, setTourElapsed, tourExtended: extended, setTourExtended, controlsHidden, setControlsHidden } = useStore()
  const stop = extended ? 420 : 180
  const tour = [
    { route: '/twin', title: 'Start with a changing source', caption: 'Feedwater and household conditions drive the purifier twin.' },
    { route: '/why', title: 'Separate water stress from fouling', caption: 'Raw flow changes; normalized membrane permeability isolates the modeled membrane state.' },
    { route: '/evidence', title: 'Inspect how the estimate performs', caption: 'Compare the physics-guided model with raw and counter baselines.' },
    { route: '/fleet', title: 'Consider the service trade-off', caption: 'These simulated policy comparisons expose assumptions instead of inventing savings.' },
    { route: '/hardware', title: 'Close the loop on a bench', caption: 'The proposed rig tests current-to-pressure and stage signatures against ground truth.' },
    { route: '/about', title: 'End with the limits', caption: 'No field validation or drinking-water safety claim is made.' },
  ]
  const current = tour[Math.min(tour.length - 1, Math.floor(elapsed / (stop / tour.length)))]
  useEffect(() => { if (active) navigate(current.route) }, [active, current.route, navigate])
  const updateExtended = (value: boolean) => { setTourExtended(value); setTourElapsed(0) }
  return <div className="page">
    <SectionTitle kicker="Presenter mode" title="A guided, evidence-first story." description="A timed route through the twin, the normalization insight, the evaluation, and the bench plan." />
    <div className={`demo-stage ${controlsHidden ? 'controls-hidden' : ''}`}><div className="demo-visual"><div className="tour-orbit"><span><Droplets size={28} /></span><i /><i /><i /></div><div className="tour-step">{String(tour.indexOf(current) + 1).padStart(2, '0')} / {String(tour.length).padStart(2, '0')}</div><Provenance /></div><div className="demo-controls"><div className="eyebrow">{extended ? 'EXTENDED WALKTHROUGH' : 'SHORT WALKTHROUGH'}</div><h2>{current.title}</h2><p>{current.caption}</p><div className="tour-progress"><i style={{ width: `${Math.min(100, elapsed / stop * 100)}%` }} /></div><div className="tour-buttons"><button className="button-primary" onClick={() => { if (!active && elapsed >= stop) setTourElapsed(0); setTourActive(!active) }}>{active ? 'Pause walkthrough' : elapsed >= stop ? 'Replay tour' : 'Start walkthrough'}</button><button className="button-secondary" onClick={() => { setTourElapsed(0); setTourActive(false); setControlsHidden(false); navigate('/twin') }}><RotateCcw size={14} /> Reset</button></div><div className="toggle-row"><label><input type="checkbox" checked={extended} onChange={(e) => updateExtended(e.target.checked)} /> Extended mode</label><label><input type="checkbox" checked={presenter} onChange={(e) => setPresenter(e.target.checked)} /> Large type</label><label><input type="checkbox" checked={controlsHidden} onChange={(e) => setControlsHidden(e.target.checked)} /> Hide controls</label></div><div className="hotkeys"><span>SPACE <small>play / pause</small></span><span>R <small>reset to twin</small></span><span>H <small>hide / show controls</small></span></div></div></div>
    <Panel eyebrow="Tour notes" title="What the presenter should say"><div className="tour-notes">{tour.map((item, i) => <button key={item.route} className={current.route === item.route ? 'current' : ''} onClick={() => { setTourActive(false); setTourElapsed(Math.floor(i * stop / tour.length)); navigate(item.route) }}><span>{String(i + 1).padStart(2, '0')}</span><b>{item.title}</b><small>{item.caption}</small></button>)}</div></Panel>
  </div>
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onClick={onClose}><motion.div className="modal-card" role="dialog" aria-modal="true" aria-label={title} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} onClick={(e) => e.stopPropagation()}><div><h3>{title}</h3><button className="icon-btn" aria-label="Close dialog" onClick={onClose}><X size={16} /></button></div>{children}</motion.div></div>
}

function CommandPalette({ close }: { close: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const matches = nav.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
  return <div className="modal-backdrop palette-backdrop" role="presentation" onClick={close}><div className="command-palette" role="dialog" aria-label="Command palette" onClick={(e) => e.stopPropagation()}><div className="palette-search"><Search size={17} /><input autoFocus placeholder="Jump to a view…" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Escape') close(); if (e.key === 'Enter' && matches[0]) { navigate(matches[0].to); close() } }} /><kbd>ESC</kbd></div>{matches.map(({ to, label, icon: Icon }) => <button key={to} onClick={() => { navigate(to); close() }}><Icon size={15} />{label}<span>↵</span></button>)}</div></div>
}

export default function App() {
  const { theme, setTheme, commandOpen, setCommandOpen, presenter, setPresenter, controlsHidden, setControlsHidden, tourActive, tourElapsed, tourExtended, setTourElapsed, setTourActive } = useStore()
  const location = useLocation()
  const navigate = useNavigate()
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: getMetrics })
  const [toast, setToast] = useState('')
  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen(true) }
      if (location.pathname === '/demo' && event.code === 'Space') { event.preventDefault(); setTourActive(!tourActive) }
      if (location.pathname === '/demo' && event.key.toLowerCase() === 'r') { setTourActive(false); setTourElapsed(0); setControlsHidden(false); navigate('/twin') }
      if (location.pathname === '/demo' && event.key.toLowerCase() === 'h') setControlsHidden(!controlsHidden)
      if (location.pathname === '/demo' && event.key.toLowerCase() === 'p') setPresenter(!presenter)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [location.pathname, presenter, controlsHidden, tourActive, setCommandOpen, setPresenter, setControlsHidden, setTourActive, setTourElapsed, navigate])
  useEffect(() => {
    if (!tourActive) return
    const duration = tourExtended ? 420 : 180
    const steps = ['/twin', '/why', '/evidence', '/fleet', '/hardware', '/about']
    const routeIndex = Math.min(steps.length - 1, Math.floor(tourElapsed / (duration / steps.length)))
    if (location.pathname !== steps[routeIndex]) navigate(steps[routeIndex])
    const timer = window.setTimeout(() => {
      const next = tourElapsed + 1
      if (next >= duration) setTourActive(false)
      setTourElapsed(Math.min(duration, next))
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [tourActive, tourElapsed, tourExtended, location.pathname, navigate, setTourActive, setTourElapsed])
  const offline = metrics.data?.offline ?? true
  return <div className={`app-shell ${presenter ? 'presenter' : ''}`}>
    <header className="topbar"><Link className="brand" to="/twin"><span className="brand-icon">F</span><span><b>FilterTwin</b><small>Purifier intelligence</small></span></Link>
      <nav className="main-nav" aria-label="Main navigation">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><Icon size={15} /><span>{label}</span></NavLink>)}</nav>
      <div className="top-actions"><span className={`connection ${offline ? 'offline' : ''}`}><i />{offline ? 'Demo-Safe' : 'Local API'}</span><button className="palette-trigger" onClick={() => setCommandOpen(true)} aria-label="Open command palette"><Command size={14} /><span>Search</span><kbd>⌘K</kbd></button><button className="theme-toggle" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>{theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}</button></div>
    </header>
    <main id="main"><AnimatePresence mode="wait"><motion.div initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}><Routes><Route path="/" element={<TwinPage />} /><Route path="/twin" element={<TwinPage />} /><Route path="/why" element={<WhyPage />} /><Route path="/app" element={<AppPage />} /><Route path="/fleet" element={<FleetPage />} /><Route path="/evidence" element={<EvidencePage />} /><Route path="/hardware" element={<HardwarePage />} /><Route path="/about" element={<AboutPage />} /><Route path="/demo" element={<DemoPage />} /><Route path="*" element={<TwinPage />} /></Routes></motion.div></AnimatePresence></main>
    <footer className="global-footer"><span>FilterTwin / concept prototype</span><span>Predictions support maintenance. They do not certify drinking-water safety.</span><span><Provenance /></span></footer>
    {commandOpen && <CommandPalette close={() => setCommandOpen(false)} />}
    {toast && <button className="toast" onClick={() => setToast('')}>{toast} <X size={13} /></button>}
  </div>
}
