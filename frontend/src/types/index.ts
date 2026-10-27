export type TaskStatus =
  | 'RECEIVED'
  | 'ANALYZING'
  | 'NEED_INFO'
  | 'GENERATING'
  | 'VALIDATING'
  | 'RETRYING'
  | 'REVIEW_REQUIRED'
  | 'SUCCESS'
  | 'FAILED'
  | 'BLOCKED'

export type Severity = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type CheckStatus = 'PASS' | 'FAIL' | 'NEEDS_REVIEW' | 'UNDETERMINED'
export type RunMode = 'demo' | 'api'
export type ReviewDecision = 'approve' | 'reject' | 'request_changes'

export interface Finding {
  code: string
  severity: Severity
  dimension: 'structure' | 'value' | 'intent' | 'risk'
  message: string
  evidence: string
  recommendation: string
  retryable: boolean
  blocking: boolean
  rule_index: number | null
}

export interface CheckResult {
  key: string
  name: string
  status: CheckStatus
  status_label: string
  severity: Severity | null
  summary: string
  findings: Finding[]
}

export interface ValidationReport {
  passed: boolean
  status_suggestion: TaskStatus
  findings: Finding[]
  checks: CheckResult[]
  summary: Record<string, number>
  rules_evaluated: number
  config_parsed: boolean
}

export interface Intent {
  text: string
  parse_mode: string
  action: string | null
  protocol: string | null
  destination_port: number | null
  sources: string[]
  destinations: string[]
  default_action: string | null
  missing: string[]
  invalid_values: string[]
  assumptions: string[]
  notes: string[]
  widen_source_hint: string | null
  widen_destination_hint: string | null
  any_any: boolean
  stubborn_widen: boolean
  service_label: string | null
}

export interface ACLRule {
  action: string
  protocol: string
  source: string
  destination: string
  destination_port?: number | null
  description?: string | null
}

export interface ACLConfig {
  rules: ACLRule[]
  default_action: string
}

export interface TaskParams {
  mode: RunMode
  max_retries: number
  enable_feedback_fix: boolean
  enable_high_risk_block: boolean
  require_human_review: boolean
}

export interface Attempt {
  index: number
  kind: 'initial' | 'correction'
  note: string
  raw: string
  config: ACLConfig | null
  validation: ValidationReport | null
  created_at: string
  generation_source: string
  error: string | null
}

export interface TaskEvent {
  seq: number
  at: string
  level: 'info' | 'success' | 'warning' | 'error'
  status: string | null
  message: string
  detail: string | null
}

export interface Decision {
  step: number
  status: string
  error_codes: string[]
  action: string
  reason: string
  requires_human_review: boolean
  retry_count: number
  attempt: number
}

export interface ReviewRecord {
  decision: ReviewDecision | 'escalate'
  comment: string
  reviewer: string
  at: string
  high_risk_acknowledged: boolean
}

export interface UsageStats {
  demo_generation_calls: number
  api_calls: number
  prompt_tokens: number | null
  completion_tokens: number | null
}

export interface Task {
  id: string
  requirement: string
  params: TaskParams
  status: TaskStatus
  status_label: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  intent: Intent | null
  attempts: Attempt[]
  events: TaskEvent[]
  decisions: Decision[]
  missing_fields: string[]
  review: ReviewRecord | null
  usage: UsageStats
  retry_count: number
  origin: 'manual' | 'test-case'
  test_case_id: string | null
  deployed: boolean
  final_config: ACLConfig | null
  final_validation: ValidationReport | null
  token_display: string
  mode_label: string
  is_terminal: boolean
  awaiting_user: boolean
  awaiting_review: boolean
}

export interface Health {
  status: string
  mode: RunMode
  api_mode_available: boolean
  model: string | null
  version: string
  notices: string[]
}

export interface TestCase {
  id: string
  name: string
  category: string
  requirement: string
  target: string
  config_payload: ACLConfig | null
  params: TaskParams
  expected_status: TaskStatus
  expected_codes: string[]
  ground_truth_has_risk: boolean
  ground_truth_compliant: boolean
  notes: string
  last_results: Record<string, CaseRunResult>
}

export interface CaseRunResult {
  case_id: string
  case_name: string
  group: string
  group_label: string
  actual_status: string
  actual_status_label: string
  expected_status: string
  codes: string[]
  missing_codes: string[]
  unexpected_codes: string[]
  matched_expected: boolean
  structure_valid: boolean | null
  compliant: boolean | null
  risk_detected: boolean | null
  ground_truth_has_risk: boolean
  ground_truth_compliant: boolean
  attempts: number
  duration_ms: number
  generation_calls: number
  tokens: number | null
  detail: string
  task_id: string | null
}

export interface TestRunResponse {
  group: string
  group_label: string
  mode: RunMode
  started_at: string
  finished_at: string
  results: CaseRunResult[]
  passed: number
  total: number
  notice: string
}

export interface MetricValue {
  key: string
  label: string
  display: string
  value: number | null
  numerator: number | null
  denominator: number | null
  note: string
}

export interface GroupMetrics {
  group: string
  label: string
  description: string
  metrics: MetricValue[]
}

export interface Metrics {
  status: 'NOT_RUN' | 'COMPLETED'
  mode: RunMode | null
  generated_at: string | null
  case_count: number
  groups: GroupMetrics[]
  notices: string[]
}
