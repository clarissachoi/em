import { useEffect, useState } from 'react'
import { getUsers, type UserId, type UserSummary } from '../api/client'
import { usePersona } from '../hooks/usePersona'

/** Header dropdown that switches the demo persona (sets X-User-Id). */
export default function PersonaSwitcher() {
  const { persona, setPersona } = usePersona()
  const [users, setUsers] = useState<UserSummary[]>([])

  useEffect(() => {
    getUsers().then(setUsers).catch(() => setUsers([]))
  }, [])

  return (
    <label className="persona">
      <span className="muted">Viewing as</span>
      <select value={persona} onChange={(e) => setPersona(e.target.value as UserId)}>
        {users.length === 0 && <option value={persona}>{persona}</option>}
        {users.map((u) => (
          <option key={u.id} value={u.id} title={u.tagline}>
            {u.name}, {u.age}
          </option>
        ))}
      </select>
    </label>
  )
}
