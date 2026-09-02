export interface TechStackOption {
  name: string;
  technologies: string[];
  pros: string;
  cons: string;
}

export interface TechStack {
  name: string;
  technologies: string[];
}

export interface Problem {
  id: string;
  source_id: string;
  external_id: string;
  title: string;
  description: string | null;
  url: string | null;
  problem_frequency: string | null;
  existing_solutions: string | null;
  pricing_estimate: string | null;
  tech_stack_options: TechStackOption[] | null;
  recommended_tech_stack: TechStack | null;
  tech_stack_justification: string | null;
  fetched_at: string;
  created_at: string;
  updated_at: string;
}

export interface FetchResult {
  source_id: string;
  source_name: string;
  items_fetched: number;
  items_new: number;
  items_updated: number;
  duration_seconds: number;
}
