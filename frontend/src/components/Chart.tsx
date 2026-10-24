import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, MarkAreaComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'
import { usePrefersDark } from '../hooks'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, MarkAreaComponent, SVGRenderer])

/** Chart colours, read from the CSS tokens so charts follow light/dark mode. */
export function chartTokens() {
  const css = getComputedStyle(document.documentElement)
  const v = (name: string) => css.getPropertyValue(name).trim()
  return {
    series: v('--series-1'),
    seriesSoft: v('--series-1-soft'),
    series2: v('--series-2'),
    series3: v('--series-3'),
    band: v('--band'),
    surface: v('--surface'),
    text: v('--text'),
    textSecondary: v('--text-secondary'),
    muted: v('--text-muted'),
    grid: v('--grid'),
    axis: v('--axis'),
  }
}

export type Tokens = ReturnType<typeof chartTokens>

type Props = {
  build: (tokens: Tokens) => EChartsCoreOption
  height?: number
  ariaLabel: string
  onClick?: (dataIndex: number) => void
}

/** Thin wrapper around ECharts: renders `build(tokens)` and re-renders when the
 *  options, the container size or the colour scheme change. */
export default function Chart({ build, height = 300, ariaLabel, onClick }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const instance = useRef<echarts.ECharts | null>(null)
  const dark = usePrefersDark()

  useEffect(() => {
    if (!ref.current) return
    const chart = echarts.init(ref.current, undefined, { renderer: 'svg' })
    instance.current = chart
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(ref.current)
    return () => {
      observer.disconnect()
      chart.dispose()
      instance.current = null
    }
  }, [])

  useEffect(() => {
    instance.current?.setOption(build(chartTokens()), { notMerge: true })
  }, [build, dark])

  useEffect(() => {
    const chart = instance.current
    if (!chart || !onClick) return
    const handler = (params: { dataIndex: number }) => onClick(params.dataIndex)
    chart.on('click', handler)
    return () => {
      chart.off('click', handler)
    }
  }, [onClick])

  return <div ref={ref} className="chart" style={{ height }} role="img" aria-label={ariaLabel} />
}
