// Types mirroring the FastAPI response models (backend/src/adaptive_rag/api/*).

export type Mode = "vector" | "hybrid" | "graph" | "graph_hybrid";
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
  strategy: "" | "vector" | "hybrid" | "graph_hybrid";
  strategy_reason: string;
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
  index_to_build: "bm25" | "graph" | "bm25+graph";
  message: string;
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
}

export interface QueryOut {
  query_id: string;
  answer: string;
  citations: Citation[];
  insufficient_evidence: boolean;
  query_type: string;
  classified_by: "rules" | "llm";
  mode: Mode;
  ideal_mode: Mode;
  routing_reason: string;
  recommendation: Recommendation | null;
  recommendation_document_ids: string[];
  rewrites: string[];
  graph_paths: GraphPath[];
  scores: { relevance: number; relevance_history: number[]; grounding: number | null };
  quality: RetrievalQuality | null;
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
