import { useEffect, useState, type FormEvent } from 'react'
import { getInsurance, type BenefitAccount, type Coverage as CoverageData, type EmployerBenefit, type VisitCost } from '../api/client'
import Icon from '../components/Icon'
import { usePersona } from '../hooks/usePersona'

const money = (n: number) => `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
const pct = (used: number, limit: number) => (limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0)

/** "Today, 5:15 PM", "Tomorrow, 9:00 AM", or "Fri Oct 30". */
function when(iso: string) {
  const d = new Date(iso)
  const days = Math.round((new Date(d.toDateString()).getTime() - new Date(new Date().toDateString()).getTime()) / 86_400_000)
  const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  if (days === 0) return `Today, ${time}`
  if (days === 1) return `Tomorrow, ${time}`
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

/** Icon for a visit, from its plan and specialty. */
function visitIcon(v: VisitCost) {
  if (v.plan === 'dental') return 'tooth'
  if (v.plan === 'vision') return 'eye'
  if (v.for_name || /pediatric/i.test(v.specialty)) return 'baby'
  if (/ob-gyn|prenatal|ultrasound|glucose/i.test(`${v.specialty} ${v.title}`)) return 'heart'
  return 'calendar'
}

/** Icon for an employer benefit, from its name. */
function benefitIcon(b: EmployerBenefit) {
  const n = b.name.toLowerCase()
  if (n.includes('counsel')) return 'chat'
  if (n.includes('fitness')) return 'run'
  if (n.includes('child')) return 'baby'
  if (n.includes('travel')) return 'globe'
  if (n.includes('doula') || n.includes('pump') || n.includes('leave')) return 'heart'
  return 'gift'
}

const BENEFIT_TONE: Record<EmployerBenefit['status'], string> = { available: 'green', plan_ahead: 'violet', not_started: 'violet', in_use: '' }

/** One FSA or HSA tile. */
function Account({ a }: { a: BenefitAccount }) {
  const isHsa = a.type === 'hsa'
  const tag = isHsa ? 'Rolls over' : a.type === 'health_fsa' ? 'Use it or lose it' : 'Daycare'
  const tone = isHsa ? 'green' : a.type === 'health_fsa' ? 'warn' : 'violet'
  const contributed = (a.contributed_you ?? 0) + (a.contributed_employer ?? 0)
  return (
    <div className="cov-account">
      <div className="cov-account-top">
        <h3>{a.name}</h3>
        <span className={`cov-tag ${tone}`}>{tag}</span>
      </div>
      <div className="cov-left">
        {money(a.balance)}
        <small>{a.elected != null ? `left of ${money(a.elected)}` : 'balance'}</small>
      </div>
      {a.elected != null && (
        <div className={`cov-bar ${a.type === 'health_fsa' ? 'coral' : 'violet'}`}><span style={{ width: `${pct(a.spent ?? 0, a.elected)}%` }} /></div>
      )}
      {isHsa && a.annual_limit != null && (
        <div className="cov-bar green"><span style={{ width: `${pct(contributed, a.annual_limit)}%` }} /></div>
      )}
      <p>
        {a.note}
        {isHsa && a.annual_limit != null &&
          ` This year you added ${money(a.contributed_you ?? 0)} and your employer added ${money(a.contributed_employer ?? 0)}, out of a ${money(a.annual_limit)} limit.`}
      </p>
    </div>
  )
}

/** Coverage screen: plan, what upcoming visits cost, what she has paid, FSA/HSA, and employer perks. */
export default function Coverage({ onAsk }: { onAsk: (prompt?: string) => void }) {
  const { persona } = usePersona()
  const [state, setState] = useState<{ persona: string; data: CoverageData } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    let cancelled = false
    getInsurance()
      .then((data) => {
        if (cancelled) return
        setState({ persona, data })
        setError(null)
      })
      .catch((err: unknown) => !cancelled && setError(String(err)))
    return () => {
      cancelled = true
    }
  }, [persona])

  if (error) return <p className="error page-msg">Could not load coverage. {error}</p>
  if (state?.persona !== persona) return <p className="muted page-msg">Loading...</p>
  const { plan, upcoming, tips, spending: s, accounts, employer_benefits: perks, ask_suggestions, disclaimer } = state.data

  const ask = (e: FormEvent) => {
    e.preventDefault()
    onAsk(draft.trim() || undefined)
    setDraft('')
  }
  const upcomingTotal = upcoming.reduce((t, v) => t + (v.cost ?? 0), 0)
  const yearMax = Math.max(1, ...s.by_year.map((y) => y.total))
  const parts = [plan.medical && 'Medical', plan.dental && 'Dental', plan.vision && 'Vision'].filter(Boolean) as string[]
  const accountLabel = accounts.some((a) => a.type === 'hsa') ? 'HSA' : 'FSA'

  return (
    <div className="home">
      <div className="status-row">
        <span className="pill"><span className="dot green" aria-hidden /> Coverage active</span>
        <span className="pill">
          Plan year {plan.plan_year} · resets {new Date(`${plan.resets_on}T00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </span>
      </div>

      <h1 className="greeting">Your coverage, made simple</h1>
      <p className="quote">What is covered, what you will pay, and money you can still use.</p>

      <form className="ask" onSubmit={ask}>
        <button type="button" className="ask-mic" onClick={() => onAsk()} aria-label="Talk to Em">
          <Icon name="mic" size={18} />
        </button>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Ask Em about your coverage..." aria-label="Ask Em" />
        <button type="submit" className="ask-send" aria-label="Send to Em">
          <Icon name="arrow" size={16} />
        </button>
      </form>
      <div className="cov-chips">
        {ask_suggestions.map((q) => (
          <button key={q} type="button" className="chip" onClick={() => onAsk(q)}>{q}</button>
        ))}
      </div>

      <div className="cards">
        <section className="card glass cov-plan">
          <div className="cov-plan-main">
            <span className="cov-plan-badge"><Icon name="shield" size={22} /></span>
            <div>
              <span className="eyebrow">My plan · through {plan.employer}</span>
              <div className="cov-plan-name">{plan.name}</div>
              <div className="cov-plan-facts">
                <span>Member ID <b>{plan.member_id}</b></span>
                <span>Group <b>{plan.group_number}</b></span>
                <span>Covers <b>{plan.covers.join(' and ')}</b></span>
              </div>
            </div>
          </div>
          <div className="cov-plan-side">
            {parts.map((p) => <span key={p} className="cov-tag green">{p} ✓</span>)}
          </div>
        </section>

        <section className="card glass">
          <header className="card-head">
            <h2><span className="dot coral" aria-hidden /> Coming up: what you will pay</h2>
            <span className="eyebrow">{money(upcomingTotal)} total</span>
          </header>
          <ul className="focus-list">
            {upcoming.length === 0 && <li className="muted small">No upcoming visits.</li>}
            {upcoming.map((v) => (
              <li key={v.appointment_id} className="focus-item">
                <span className="focus-icon"><Icon name={visitIcon(v)} /></span>
                <div className="focus-text">
                  <strong>{v.title}{v.for_name ? ` for ${v.for_name}` : ''}</strong>
                  <span className="muted">{when(v.datetime)} · {v.provider}</span>
                </div>
                <div className={`cov-price ${v.cost === 0 ? 'free' : ''}`}>
                  <b>{v.cost == null ? '?' : money(v.cost)}</b>
                  <span>{v.cost_label}{v.pay_with ? ` · ${v.pay_with} ok` : ''}</span>
                </div>
              </li>
            ))}
            {tips.map((t) => (
              <li key={t.title} className="focus-item cov-tip">
                <span className="focus-icon"><Icon name="shield" /></span>
                <div className="focus-text">
                  <strong>{t.title}</strong>
                  <span className="muted">{t.text}</span>
                </div>
              </li>
            ))}
          </ul>
          <p className="cov-foot">{disclaimer}</p>
        </section>

        <section className="card glass">
          <header className="card-head">
            <h2><span className="dot violet" aria-hidden /> What you have paid</h2>
            <span className="pill small">Out of pocket</span>
          </header>
          <div className="cov-total">
            <span className="cov-big">{money(s.total)}</span>
            <span className="muted small">so far in {s.year}</span>
          </div>
          <div className="cov-years">
            {s.by_year.slice(0, 2).map((y) => (
              <div key={y.year} className={`cov-year ${y.year === s.year ? 'on' : ''}`}>
                <span className="eyebrow">{y.year === s.year ? `${y.year} so far` : y.year}</span>
                <b>{money(y.total)}</b>
                <div className="cov-bar coral thin"><span style={{ width: `${pct(y.total, yearMax)}%` }} /></div>
              </div>
            ))}
          </div>
          <ul className="cov-breakdown">
            {s.by_category.map((c) => (
              <li key={c.category}><span>{c.label}</span><b>{money(c.amount)}</b></li>
            ))}
          </ul>
          <div className="cov-meter">
            <div className="cov-meter-top"><b>Deductible</b><span className="muted">{money(s.deductible.used)} of {money(s.deductible.limit)}</span></div>
            <div className="cov-bar coral"><span style={{ width: `${pct(s.deductible.used, s.deductible.limit)}%` }} /></div>
          </div>
          <div className="cov-meter">
            <div className="cov-meter-top"><b>Out-of-pocket max</b><span className="muted">{money(s.out_of_pocket.used)} of {money(s.out_of_pocket.limit)}</span></div>
            <div className="cov-bar violet"><span style={{ width: `${pct(s.out_of_pocket.used, s.out_of_pocket.limit)}%` }} /></div>
          </div>
          {s.premiums > 0 && <p className="cov-foot">Plus {money(s.premiums)} in premiums taken from your paycheck this year.</p>}
        </section>

        <section className="card glass">
          <header className="card-head">
            <h2><span className="dot green" aria-hidden /> Money you can use</h2>
            <span className="eyebrow">{accountLabel}</span>
          </header>
          <div className="cov-accounts">
            {accounts.map((a) => <Account key={a.type} a={a} />)}
          </div>
        </section>

        <section className="card glass">
          <header className="card-head">
            <h2><span className="dot coral" aria-hidden /> Perks from {plan.employer}</h2>
            <span className="eyebrow">{perks.length} benefits</span>
          </header>
          <ul className="focus-list">
            {perks.map((b) => (
              <li key={b.name} className="focus-item">
                <span className={`focus-icon cov-icon ${BENEFIT_TONE[b.status]}`}><Icon name={benefitIcon(b)} /></span>
                <div className="focus-text">
                  <strong>{b.name}</strong>
                  <span className="muted">{b.detail}</span>
                </div>
                <span className={`cov-tag ${BENEFIT_TONE[b.status]}`}>{b.status_label}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}
