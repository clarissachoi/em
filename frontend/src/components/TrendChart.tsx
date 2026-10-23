import type { TrendPoint } from '../api/client'

const W = 320
const H = 96
const PAD = 8

/** Smooth path through points using Catmull-Rom converted to cubic Beziers. */
function smoothPath(pts: [number, number][]): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] ?? p2
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    d += ` C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${p2[0]} ${p2[1]}`
  }
  return d
}

/** 7-day readiness line with a dashed average line and today's point highlighted. */
export default function TrendChart({ points }: { points: TrendPoint[] }) {
  if (points.length < 2) return null
  const values = points.map((p) => p.readiness)
  const lo = Math.min(...values) - 5
  const hi = Math.max(...values) + 5
  const x = (i: number) => PAD + (i * (W - PAD * 2)) / (points.length - 1)
  const y = (v: number) => PAD + (1 - (v - lo) / (hi - lo)) * (H - PAD * 2)
  const pts = values.map((v, i) => [x(i), y(v)] as [number, number])
  const line = smoothPath(pts)
  const avg = values.reduce((a, b) => a + b, 0) / values.length
  const last = pts[pts.length - 1]
  const days = points.map((p) => new Date(`${p.date}T12:00:00`).toLocaleDateString('en-US', { weekday: 'narrow' }))

  return (
    <figure className="trend">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Readiness this week: ${values.join(', ')}`}>
        <defs>
          <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-fill)" stopOpacity="0.55" />
            <stop offset="100%" stopColor="var(--chart-fill)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${line} L ${last[0]} ${H} L ${pts[0][0]} ${H} Z`} fill="url(#trend-fill)" />
        <line x1={PAD} x2={W - PAD} y1={y(avg)} y2={y(avg)} className="trend-avg" />
        <path d={line} className="trend-line" />
        <circle cx={last[0]} cy={last[1]} r="4.5" className="trend-dot" />
      </svg>
      <figcaption className="trend-days">
        {days.map((d, i) => <span key={i}>{d}</span>)}
      </figcaption>
    </figure>
  )
}
