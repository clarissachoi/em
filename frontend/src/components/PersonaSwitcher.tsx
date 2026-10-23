import { useEffect, useState } from 'react'
import { getUsers, type UserSummary } from '../api/client'
import { usePersona } from '../hooks/usePersona'

/** Header dropdown that switches the demo persona (sets X-User-Id). */
export default function PersonaSwitcher() {
  const { persona, setPersona } = usePersona()
  const [users, setUsers] = useState<UserSummary[]>([])

  useEffect(() => {
    getUsers()
      .then((list) => {
        setUsers(list)
        // A saved persona that no longer exists falls back to the first one
        if (list.length && !list.some((u) => u.id === persona)) setPersona(list[0].id)
      })
      .catch(() => setUsers([]))
    // Load the list once; persona changes don't need a re-fetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <label className="persona">
      <span className="muted">Viewing as</span>
      <select value={persona} onChange={(e) => setPersona(e.target.value)}>
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
