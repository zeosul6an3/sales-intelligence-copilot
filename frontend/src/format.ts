// Display formatting only. Values arrive already calculated from the API.

export function money(value: number | null | undefined, currency: string, compact = false): string {
  if (value === null || value === undefined) return '–'
  try {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency,
      notation: compact ? 'compact' : 'standard',
      maximumFractionDigits: compact ? 1 : 0,
    }).format(value)
  } catch {
    // Unknown currency code: fall back to a plain number with the code.
    return `${number(value, compact)} ${currency}`
  }
}

export function moneyExact(value: number | null | undefined, currency: string): string {
  if (value === null || value === undefined) return '–'
  try {
    return new Intl.NumberFormat('en-GB', { style: 'currency', currency }).format(value)
  } catch {
    return `${value.toFixed(2)} ${currency}`
  }
}

export function number(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined) return '–'
  return new Intl.NumberFormat('en-GB', {
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: compact ? 1 : 0,
  }).format(value)
}

export function percentChange(current: number | null, previous: number | null): number | null {
  if (current === null || previous === null || previous === 0) return null
  return ((current - previous) / Math.abs(previous)) * 100
}

export function shortDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function monthLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
}
