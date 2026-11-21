/** Follow-up dates are calendar dates in the operator's local timezone. */
export function isOverdueFollowUp(value: string | null | undefined, status: string, now = new Date()): boolean {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value) || ["resolved", "verified"].includes(status)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) return false;
  const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"), String(now.getDate()).padStart(2, "0")].join("-");
  return value < today;
}
