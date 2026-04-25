export type RecommendItem = {
  id: string;
  name: string;
  cuisines: string[];
  rating: number | null;
  estimated_cost: string | null;
  cost_display: string | null;
  locality: string | null;
  explanation: string;
  rank: number;
};

export type RecommendMeta = {
  shortlist_size?: number;
  model?: string;
  prompt_version?: string;
  parse_method?: string;
  llm_called?: boolean;
  filter_reason?: string;
  duration_filter_ms?: number;
  duration_llm_ms?: number;
  duration_total_ms?: number;
  relaxed_min_rating?: number | null;
};

export type RecommendResponse = {
  summary: string;
  items: RecommendItem[];
  meta: RecommendMeta;
};

export type Preferences = {
  location: string;
  cuisine?: string | string[];
  min_rating?: number;
  budget_max_inr?: number | null;
  extras?: string;
};
