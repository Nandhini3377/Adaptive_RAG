// Types mirroring the FastAPI response models (backend/src/adaptive_rag/api/*).

export type Mode = "vector" | "keyword" | "hybrid" | "graph" | "graph_hybrid";
export type IndexName = "vector" | "bm25" | "graph";

/** What each mode searches; a strategy builds exactly its mode's indexes (schemas.MODE_INDEXES). */
export const MODE_INDEXES: Record<Mode, IndexName[]> = {
  vector: ["vector"],
  keyword: ["bm25"],
  hybrid: ["vector", "bm25"],
  graph: ["graph"],
  graph_hybrid: ["vector", "bm25", "graph"],
};
export type Intent = "facts" | "exact_terms" | "connections" | "compare";
export type DocumentStatus = "scanning" | "awaiting_intent" | "indexing" | "ready" | "failed";

export interface DocumentOut {
  id: string;
  filename: string;
  file_type: string;
  status: DocumentStatus;
  progress: number;
  stage: string;
  error: string;
  strategy: "" | Mode;
  strategy_reason: string;
  has_vector: boolean;
  has_bm25: boolean;
  graph_status: "none" | "candidate" | "building" | "ready";
  created_at: string;
}

export interface DocumentProfile {
  page_count: number;
  section_count: number;
  heading_count: number;
  table_count: number;
  list_count: number;
  link_count: number;
  word_count: number;
  cross_ref_rate: number;
  relationship_phrase_rate: number;
  identifier_density: number;
  table_share: number;
  sampled_section_ids: string[];
  relationship_density: number;
  entity_repetition: number;
  analysis_tokens: number;
  analysis_cost_inr: number;
  sample_entities: string[];
  sample_relationships: string[];
}

export interface IntentOption {
  id: Intent;
  label: string;
  suggested: boolean;
}

export interface AnalysisOut {
  status: DocumentStatus;
  profile: DocumentProfile;
  intent_options: IntentOption[];
  suggested_intents: Intent[];
  user_intents: Intent[] | null;
  strategy: string | null;
  confidence: number | null;
  reason: string;
  rules_strategy: Mode | null; // the fixed rules' pick
  llm_strategy: Mode | null; // the LLM's pick; null if it was not asked or failed
  llm_reason: string;
  suggested_indexes: IndexName[]; // wanted by one side but not built
}

export interface Citation {
  number: number;
  chunk_id: string;
  document_id: string;
  section: string;
  page: number | null;
  text: string;
}

export interface GraphPath {
  nodes: string[];
  relations: string[];
  chunk_ids: string[];
}

export interface Recommendation {
  better_mode: Mode;
  index_to_build: string; // e.g. "bm25+graph"
  message: string;
}

/** One search mode scored against the shared, LLM-judged pool of chunks. */
export interface ModeQuality {
  mode: Mode;
  used: boolean; // the answer was written from this mode's chunks
  found: number; // chunks it returned
  relevant: number; // of those, judged relevant
  precision: number | null; // null: the mode found nothing
  recall: number | null; // null: only one mode, or nothing relevant anywhere
}

/** How good the retrieved chunks were, judged by the LLM after the answer. */
export interface RetrievalQuality {
  precision: number; // relevant chunks used / chunks used
  relative_recall: number | null; // null: no other mode to compare, or nothing relevant found
  used: number;
  relevant_used: number;
  relevant_in_pool: number; // relevant chunks found by any available mode
  pool_size: number;
  compared_modes: string[];
  modes: ModeQuality[]; // the used mode first, then every other indexed mode
  recall_scope: "modes" | "candidates"; // recall against every mode, or one mode's own fetch
}

export interface QueryOut {
  query_id: string;
  answer: string;
  citations: Citation[];
  insufficient_evidence: boolean;
  query_type: string;
  classified_by: "rules" | "llm";
  mode: Mode; // the mode the answer was written from (best measured evidence)
  router_mode: Mode; // the router's prediction from the question type
  ideal_mode: Mode;
  routing_reason: string;
  recommendation: Recommendation | null;
  recommendation_document_ids: string[];
  rewrites: string[];
  graph_paths: GraphPath[];
  scores: { relevance: number; relevance_history: number[]; grounding: number | null };
  quality: RetrievalQuality | null;
  comparison: string;
  regenerated: boolean;
  refused_reason: string;
  documents: Record<string, string>;
  timings: Record<string, number>;
  latency_ms: number;
  tokens: number;
  reasoning_tokens: number;
  llm_calls: number;
  cost_inr: number;
}

/** The Evaluation Lab's snippet: indexed in every mode, with the analysis's own pick. */
export interface LabOut {
  document: DocumentOut;
  text: string;
  strategy: Mode | null; // what a normal upload would build
  confidence: number | null;
  reason: string;
  rules_strategy: Mode | null;
  llm_strategy: Mode | null;
  modes: Mode[]; // searchable now
}

export interface LabChunk {
  section: string;
  text: string;
  relevant: boolean;
}

export interface LabMode extends ModeQuality {
  chunks: LabChunk[];
}

export interface LabQueryOut {
  question: string;
  query_type: string;
  classified_by: "rules" | "llm";
  strategy: string;
  adaptive_mode: Mode; // what Adaptive RAG would use with only the analysis's indexes
  picks: Partial<Record<"final" | "rules" | "llm", Mode>>; // the mode each decider alone leads to
  ideal_mode: Mode;
  routing_reason: string;
  best_modes: Mode[]; // empty: no mode found a relevant chunk
  relevant_in_pool: number;
  pool_size: number;
  modes: LabMode[]; // adaptive mode first
  latency_ms: number;
  tokens: number;
  llm_calls: number;
  cost_inr: number;
}
