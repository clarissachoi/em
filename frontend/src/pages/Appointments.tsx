import { getAppointments, getLabs, getProviders, getRecords, getSlots } from '../api/client'
import { RawSection } from '../components/Raw'

/** Appointments, labs, and records. Scaffold: raw mock data. */
export default function Appointments() {
  return (
    <>
      <h1>Appointments</h1>
      <RawSection title="GET /appointments" fn={getAppointments} />
      <RawSection title="GET /appointments/slots" fn={() => getSlots()} />
      <RawSection title="GET /providers" fn={() => getProviders()} />
      <RawSection title="GET /labs" fn={getLabs} />
      <RawSection title="GET /records" fn={getRecords} />
    </>
  )
}
