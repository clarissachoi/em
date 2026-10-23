// Persona context shared by PersonaProvider and its consumers.

import { createContext, useContext } from 'react'

export interface PersonaContextValue {
  persona: string
  setPersona: (id: string) => void
}

export const PersonaContext = createContext<PersonaContextValue | null>(null)

/** Access the current persona. */
export function usePersona() {
  const ctx = useContext(PersonaContext)
  if (!ctx) throw new Error('usePersona must be used inside PersonaProvider')
  return ctx
}
