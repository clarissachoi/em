// Current demo persona. Keeps the API client's X-User-Id header in sync and remembers the choice.

import { useState, type ReactNode } from 'react'
import { setUserId } from '../api/client'
import { PersonaContext } from '../hooks/usePersona'

const STORAGE_KEY = 'emcare.persona'

/** Read the saved persona, falling back to maya if storage is empty or blocked. */
function loadPersona(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? 'maya'
  } catch {
    return 'maya'
  }
}

/** Provide the persona to the app and apply it to the API client. */
export default function PersonaProvider({ children }: { children: ReactNode }) {
  const [persona, setPersonaState] = useState(() => {
    const initial = loadPersona()
    setUserId(initial)
    return initial
  })

  const setPersona = (id: string) => {
    setUserId(id)
    setPersonaState(id)
    try {
      localStorage.setItem(STORAGE_KEY, id)
    } catch {
      // storage blocked; the choice just won't persist
    }
  }

  return <PersonaContext.Provider value={{ persona, setPersona }}>{children}</PersonaContext.Provider>
}
