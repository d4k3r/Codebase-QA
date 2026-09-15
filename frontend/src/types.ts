export interface AskRequest {
  question: string;
  top_k?: number;
}

export interface RetrievedSource {
  repository: string;
  file_path: string;
  symbol_type: string;
  symbol_name: string | null;
  start_line: number;
  end_line: number;
  content: string;
  cosine_distance: number;
}

export interface AskResponse {
  answer: string;
  sources: RetrievedSource[];
}
