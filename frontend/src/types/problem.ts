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

export interface ProblemRawData {
  source?: string;
  strategy?: string;
  category?: string;
  industry?: string;
  score?: number;
  host?: string;
  scraped_at?: string;
  [key: string]: unknown;
}

export interface Problem {
  id: string;
  source_id: string;
  external_id: string;
  title: string;
  raw_data: ProblemRawData | null;
  description: string | null;
  url: string | null;
  problem_frequency: string | null;
  existing_solutions: string | null;
  pricing_estimate: string | null;
  problem_author: string | null;
  solution_tags: string[] | null;
  solution_approach: string | null;
  tech_stack_options: TechStackOption[] | null;
  recommended_tech_stack: TechStack | null;
  tech_stack_justification: string | null;
  fetched_at: string;
  created_at: string;
  updated_at: string;
}

export const SOURCE_LABELS: Record<string, string> = {
  problemhunt: "PROBLEMHUNT",
  "razorpay-fix-my-itch": "RAZORPAY",
};

export const sourceLabel = (raw: ProblemRawData | null): string => {
  if (!raw?.source) return "UNKNOWN";
  return SOURCE_LABELS[raw.source] ?? raw.source.toUpperCase();
};

export interface FetchResult {
  source_id: string;
  source_name: string;
  items_fetched: number;
  items_new: number;
  items_updated: number;
  duration_seconds: number;
}
