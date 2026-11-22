export type Kind = "photo" | "video" | "document";
export interface Fact { key: string; label: string; value: string }
export type Status = "queued" | "processing" | "ready" | "failed";

export interface Match { chunk_id: string; type: string; page: number | null; start_ms: number | null; end_ms: number | null; snippet: string }
export interface Asset {
  asset_id: string; kind: Kind; title: string; status: Status; status_detail: string | null;
  thumb_url: string | null; preview_url: string | null; taken_at: string | null; added_at: string | null;
  place: string | null; lat: number | null; lon: number | null; width: number | null; height: number | null;
  duration_ms: number | null; page_count: number | null; language: string | null; tags: string[]; caption_user: string | null;
  score?: number | null; snippet?: string; match?: Match | null; matches?: Match[];
  original_url?: string; video_url?: string | null; size_bytes?: number; mime_type?: string; years_ago?: number;
  doc_type?: string | null; doc_label?: string | null; people?: string[]; why?: string[];
  facts?: Fact[]; details?: Fact[];
  display_title?: string; auto_caption?: string | null; file_type?: string | null;
}
export interface Filters {
  kinds: Kind[]; date_from: string | null; date_to: string | null; place: string | null; tags: string[]; language: string | null; collection_id: string | null;
  doc_types: string[]; person: string | null; self_ref: boolean;
}
export interface Parsed {
  raw: string; language: string | null; intent: string; semantic_query: string; semantic_query_en: string | null; filters: Filters; followup: boolean;
  action?: string | null; doc_labels?: Record<string, string | null>;
}
export interface Citation { label: string; asset_id: string; title: string; page: number | null; start_ms: number | null; chunk_id: string }
export interface User {
  id: string; email: string | null; phone?: string | null; username?: string | null; display_name: string | null; language: string; timezone: string;
  is_admin: boolean; google?: boolean; has_password?: boolean; must_change_password?: boolean;
}
export interface Collection { id: string; name: string; description: string | null; count: number; covers: Asset[]; items?: Asset[] }
export interface SavedSearch { id: string; name: string | null; query: { query?: string; parsed?: Parsed }; pinned: boolean }
