import { getGoals, getInsights, getPlan, getSuggestions } from '../api/client'
import { RawSection } from '../components/Raw'

/** Goals, plan, suggestions, and insights. Scaffold: raw mock data. */
export default function NextSteps() {
  return (
    <>
      <h1>Next steps</h1>
      <RawSection title="GET /goals" fn={getGoals} />
      <RawSection title="GET /plan" fn={getPlan} />
      <RawSection title="GET /suggestions" fn={getSuggestions} />
      <RawSection title="GET /insights" fn={getInsights} />
    </>
  )
}
