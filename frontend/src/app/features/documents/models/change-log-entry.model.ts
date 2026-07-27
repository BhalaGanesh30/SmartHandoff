/** Client-side model for a single change log entry (mirrors ChangeLogEntryResponse). */
export interface ChangeLogEntry {
  field: string;
  old_value: unknown;
  new_value: unknown;
  author_id: string;
  timestamp: string;              // ISO 8601 UTC string
  author_display_name: string | null;
}
