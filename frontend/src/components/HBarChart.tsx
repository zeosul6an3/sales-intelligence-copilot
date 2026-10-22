import { useCallback } from 'react'
import { money, moneyExact } from '../format'
import Chart, { type Tokens } from './Chart'

type Props = {
  rows: { label: string; value: number }[]
  currency: string
  ariaLabel: string
  onSelect?: (index: number) => void
}

/** Ranked horizontal bars for one money metric, largest at the top. Each bar is
 *  labelled with its value, so the chart reads without hovering. */
export default function HBarChart({ rows, currency, ariaLabel, onSelect }: Props) {
  const build = useCallback(
    (t: Tokens) => {
      const ordered = [...rows].reverse() // ECharts draws the first category at the bottom
      return {
        animation: false,
        grid: { left: 8, right: 64, top: 4, bottom: 4, containLabel: true },
        tooltip: {
          trigger: 'item',
          backgroundColor: t.surface,
          borderColor: t.axis,
          textStyle: { color: t.text, fontSize: 12 },
          formatter: (p: { dataIndex: number }) =>
            `${ordered[p.dataIndex].label}<br/><strong>${moneyExact(ordered[p.dataIndex].value, currency)}</strong>`,
        },
        xAxis: { type: 'value', show: false },
        yAxis: {
          type: 'category',
          data: ordered.map((r) => (r.label.length > 30 ? `${r.label.slice(0, 29)}…` : r.label)),
          axisLine: { lineStyle: { color: t.axis } },
          axisTick: { show: false },
          axisLabel: { color: t.textSecondary, fontSize: 11 },
        },
        series: [
          {
            type: 'bar',
            barMaxWidth: 16,
            data: ordered.map((r) => ({
              value: r.value,
              itemStyle: { color: t.series, borderRadius: r.value >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4] },
            })),
            label: {
              show: true,
              position: 'right',
              color: t.textSecondary,
              fontSize: 11,
              formatter: (p: { value: number }) => money(p.value, currency, true),
            },
            cursor: onSelect ? 'pointer' : 'default',
          },
        ],
      }
    },
    [rows, currency, onSelect],
  )
  const handleClick = useCallback(
    (index: number) => onSelect?.(rows.length - 1 - index),
    [onSelect, rows.length],
  )
  return (
    <Chart
      build={build}
      ariaLabel={ariaLabel}
      height={Math.max(120, rows.length * 28 + 16)}
      onClick={onSelect ? handleClick : undefined}
    />
  )
}
