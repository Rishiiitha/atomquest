import type { components, paths } from './generated/api'

export type Provenance = 'SIMULATED' | 'PUBLIC DATA' | 'BENCH (not yet collected)'
export type ApiPaths = paths
export type EventKind = components['schemas']['EventInput']['kind']
export type SimulateRequest = components['schemas']['SimulateRequest']
export type WhatIfResponse = components['schemas']['WhatIfResponse']
export type IngestResponse = components['schemas']['IngestResponse']

export type Reading = {
  unit_id: string
  day: number
  scenario: string
  tds_in_mg_l: number
  turbidity_ntu: number
  temp_c: number
  flow_l_h: number
  motor_current_a: number
  pressure_virtual_bar: number
  outlet_tds_mg_l: number
  ro_permeability_est_lmh_bar: number
  raw_resistance_proxy?: number
  hydraulic_resistance_index?: number
  carbon_exposure_index?: number
  daily_litres_mean_l?: number
  litres_dispensed_l?: number
  rul_sediment_d: number
  rul_uf_d: number
  rul_carbon_d: number
  rul_ro_d: number
  pred_p1_sediment_d?: number
  pred_p1_uf_d?: number
  pred_p1_carbon_d?: number
  pred_p1_ro_d?: number
}

export type Replay = { provenance: Provenance; units: number; readings: Reading[] }

export type StageStats = {
  n_units: number
  mae_days: number | null
  median_absolute_error_days: number | null
  mean_absolute_relative_error: number | null
  nasa_score: number | null
  mae_litres: number | null
  coverage?: number
  conformal_q_days?: number
  mean_interval_width_days?: number
}

export type Metrics = {
  provenance: Provenance
  seed: number
  cohort_units: Record<string, number>
  cohort_rows: Record<string, number>
  grouped_split_check: boolean
  horizons_days: number[]
  stages: Record<string, {
    test: Record<string, Record<string, StageStats>>
    ood: Record<string, Record<string, StageStats>>
    conformal_q_days_by_horizon: Record<string, number>
    warning: Record<string, Record<string, number | null>>
  }>
  warning_policy: Record<string, { tau: number; false_alarms_per_unit_year: number; recall: number }>
  telemetry_tiers: Record<string, {
    n_features: number
    features: string[]
    provenance: Provenance
    test: Record<string, Record<string, StageStats>>
    ood: Record<string, Record<string, StageStats>>
  }>
  signature_matrix: {
    provenance: Provenance
    baseline_by_controller: Record<string, Record<string, number>>
    controller_modes: string[]
    delta_from_baseline: Record<string, Record<string, number>>
    conditions: string[]
    interpretation: string
  }
  business_impact: { assumptions: Record<string, number>; policies: Record<string, Record<string, number>> }
  public_data_checks: Record<string, { status: string; reason: string }>
  model_size_bytes_by_stage: Record<string, number>
  inference_latency_ms_per_row_by_stage: Record<string, number>
}

export type StageHealth = components['schemas']['StageHealth']
export type Scenario = components['schemas']['ScenarioSummary']
