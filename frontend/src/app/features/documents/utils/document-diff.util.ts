/**
 * Client-side diff computation for document fields.
 * 
 * Compares baseline content against edited content to identify changes
 * for debounced auto-save. Returns a diff object with only changed fields.
 */

export interface FieldDiff {
  old_value: string | null;
  new_value: string | null;
}

export interface DiffResult {
  [field: string]: FieldDiff;
}

/**
 * Compute client-side diff between baseline and edited content.
 * 
 * @param baseline - The original AI-generated or last-saved content
 * @param edited - The current editor state
 * @returns Diff object containing only changed fields
 */
export function computeClientDiff(
  baseline: Record<string, any>,
  edited: Record<string, any>
): DiffResult {
  const diff: DiffResult = {};
  
  // Get all unique keys from both objects
  const allKeys = new Set([
    ...Object.keys(baseline),
    ...Object.keys(edited)
  ]);
  
  // Compare each field
  for (const field of allKeys) {
    const oldValue = baseline[field] ?? null;
    const newValue = edited[field] ?? null;
    
    // Only include if values are different
    if (oldValue !== newValue) {
      diff[field] = {
        old_value: oldValue,
        new_value: newValue
      };
    }
  }
  
  return diff;
}
