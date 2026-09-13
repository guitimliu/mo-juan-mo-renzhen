/** Convert an optional ROC date to the API's Gregorian YYYY-MM-DD format. */
export function parseRocDate(value: string): string | null {
  if (!value.trim()) return ''
  const match = /^(\d{1,3})[/-](\d{1,2})[/-](\d{1,2})$/.exec(value.trim())
  if (!match) return null
  const rocYear = Number(match[1])
  const year = rocYear + 1911
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(Date.UTC(year, month - 1, day))
  if (rocYear < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}
