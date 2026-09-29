// TypeScript view of the sidecar contract. The single source is the Pydantic
// models in engine/contracts/ingest.py, exported to
// contracts/ingest-result.schema.json; the tests validate real output against
// that schema, so these types cannot drift unnoticed.

export type Grade = 'A' | 'B' | 'C' | 'U'
export type Route = 'text' | 'ocr' | 'sheet'
export type ExitTier = 'signals' | 'layout' | 'model' | 'person' | 'none'
export type Bbox = [number, number, number, number]
export type Scalar = string | number | boolean | null

export interface IngestFile {
  file_id: string
  sha256: string
  original_name: string
  content_type: string
  /** Never used to classify (F-09.1). Not read by this service at all. */
  label_hint?: string | null
}

export interface IngestRequest {
  case_ref: string
  config_version: string
  files: IngestFile[]
}

export interface PageInfo {
  n: number
  route: Route
  grade: Grade
  reasons: string[]
  ocr_confidence: number | null
}

export interface Candidate {
  type_id: string
  confidence: number
}

export interface Classification {
  types: string[]
  confidence: number
  exit_tier: ExitTier
  signals: string[]
  candidates: Candidate[]
}

export interface ExtractedField {
  field: string
  value: Scalar
  raw: string | null
  page: number | null
  bbox: Bbox | null
  method: 'deterministic' | 'model'
  confidence_components: Record<string, number>
  missing_reason: string | null
}

export type DefectCode = 'pages_absent' | 'period_gap' | 'unsigned' | 'unstamped' | 'plain_paper' | 'pagination_break'

export interface DocumentDefect {
  code: DefectCode
  detail: string
  pages: number[]
}

export interface IngestDocument {
  doc_key: string
  file_id: string
  page_from: number
  page_to: number
  pages: PageInfo[]
  classification: Classification
  instance_key: string | null
  fields: ExtractedField[]
  identity: Record<string, string>
  defects: DocumentDefect[]
  duplicate_of_key: string | null
  split_uncertain: boolean
}

export interface IngestFileOutcome {
  file_id: string
  status: 'processed' | 'exception' | 'rejected'
  reason: string | null
}

export type Stage = 'read' | 'grade' | 'split' | 'classify' | 'extract' | 'validate'

export interface StageTiming {
  stage: Stage
  file_id: string
  ms: number
}

export interface IngestResult {
  case_ref: string
  config_version: string
  engine_version: string
  model_provider: string
  files: IngestFileOutcome[]
  documents: IngestDocument[]
  timings: StageTiming[]
}
