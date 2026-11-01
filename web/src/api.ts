import type { EventKind, IngestResponse, Metrics, Reading, Replay, Scenario, SimulateRequest, StageHealth, WhatIfResponse } from './types'

const API = 'http://127.0.0.1:8000'

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json() as Promise<T>
}

export async function getMetrics(): Promise<{ value: Metrics; offline: boolean }> {
  try { return { value: await json<Metrics>(`${API}/evidence/metrics`), offline: false } }
  catch { return { value: await json<Metrics>('/evidence/metrics.json'), offline: true } }
}

export async function getReplay(): Promise<Replay> {
  return json<Replay>('/replays/showcase.json')
}

export async function getScenarios(): Promise<Scenario[]> {
  try { return await json<Scenario[]>(`${API}/scenarios`) }
  catch { return json<Scenario[]>('/evidence/scenarios.json') }
}

export async function getUnits(): Promise<{ unit_id: string; scenario: string; day: number; next_rul_days: number }[]> {
  try { return await json(`${API}/units`) }
  catch {
    const replay = await getReplay()
    const ids = [...new Set(replay.readings.map((row) => row.unit_id))]
    return ids.map((unit_id) => {
      const row = replay.readings.find((reading) => reading.unit_id === unit_id)!
      return { unit_id, scenario: row.scenario, day: row.day, next_rul_days: Math.min(row.rul_ro_d, row.rul_sediment_d) }
    })
  }
}

export async function getTelemetry(unitId?: string): Promise<{ readings: Reading[]; offline: boolean }> {
  try {
    const units = await json<{ unit_id: string }[]>(`${API}/units`)
    const id = unitId || units[0]?.unit_id
    if (!id) throw new Error('no generated unit')
    return { readings: await json<Reading[]>(`${API}/units/${id}/telemetry?limit=1000`), offline: false }
  } catch {
    const replay = await getReplay()
    const id = unitId || replay.readings[0]?.unit_id
    return { readings: replay.readings.filter((row) => row.unit_id === id), offline: true }
  }
}

export async function getHealth(unitId?: string): Promise<{ health: StageHealth[]; offline: boolean }> {
  try {
    const units = await json<{ unit_id: string }[]>(`${API}/units`)
    const id = unitId || units[0]?.unit_id
    if (!id) throw new Error('no generated unit')
    return { health: await json<StageHealth[]>(`${API}/units/${id}/health`), offline: false }
  } catch {
    const [{ readings }, metrics] = await Promise.all([getTelemetry(unitId), getMetrics()])
    const row = readings.at(-1)
    if (!row) return { health: [], offline: true }
    const first = readings[0]
    const resistanceRatio = (row.hydraulic_resistance_index || 1) / Math.max(first.hydraulic_resistance_index || 1, 0.01)
    const stages = ['sediment', 'uf', 'carbon', 'ro'] as const
    const healthByStage = {
      sediment: Math.max(0, Math.min(1, 1 - 0.05 * (resistanceRatio - 1))),
      uf: Math.max(0, Math.min(1, 1 - 0.04 * (resistanceRatio - 1))),
      carbon: Math.max(0, Math.min(1, 1 - (row.carbon_exposure_index || 0))),
      ro: Math.max(0, Math.min(1, row.ro_permeability_est_lmh_bar / 8)),
    }
    const dailyLitres = row.daily_litres_mean_l || row.litres_dispensed_l || 0
    return { offline: true, health: stages.flatMap((stage) => {
      const rul_days = row[`pred_p1_${stage}_d`]
      if (rul_days == null) return []
      const q = metrics.value.stages[stage]?.conformal_q_days_by_horizon?.['21'] || 0
      return [{
      stage, rul_days: Math.max(0, rul_days), rul_litres: Math.max(0, rul_days * dailyLitres),
      health_fraction: healthByStage[stage], interval_days: [Math.max(0, rul_days - q), rul_days + q],
      confidence: stage === 'carbon' ? 'low' : 'medium', cause: stage === 'carbon' ? 'Usage and assumed exposure' : 'Twin-derived estimate',
      explanation: 'Offline replay estimate. It is simulated and not field validated.', provenance: 'SIMULATED',
    }] }) }
  }
}

export async function simulateEvent(scenario: string, kind: EventKind): Promise<Reading[]> {
  try {
    const request: SimulateRequest = { scenario, seed: 20261101, events: [{ kind, day: 30, duration_days: 7 }] }
    const response = await json<{ readings: Reading[] }>(`${API}/simulate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
    return response.readings
  } catch {
    const replays = await json<{ bundles: Record<string, { readings: Reading[] }> }>('/replays/events.json')
    const replay = replays.bundles[`${scenario}:${kind}`]
    if (!replay) throw new Error(`No offline replay is available for ${scenario} / ${kind}`)
    return replay.readings
  }
}

export async function whatIf(values: { tds_mg_l: number; temperature_c: number; membrane_permeability_lmh_bar: number }): Promise<WhatIfResponse> {
  return json(`${API}/whatif`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...values, pressure_bar: 4.5, permeate_pressure_bar: 0.15, area_m2: 0.4 }) })
}

export async function ingestCsv(file: File): Promise<IngestResponse> {
  const body = new FormData(); body.append('file', file)
  return json(`${API}/ingest`, { method: 'POST', body })
}
