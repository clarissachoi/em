import { getHome } from '../api/client'
import { RawSection } from '../components/Raw'

/** Home dashboard. Scaffold: raw mock data. */
export default function Home() {
  return (
    <>
      <h1>Home</h1>
      <RawSection title="GET /home" fn={getHome} />
    </>
  )
}
