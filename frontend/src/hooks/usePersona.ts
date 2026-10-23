// Persona context shared by PersonaProvider and its consumers.

import { createContext, useContext } from 'react'
import type { UserId } from '../api/client'

export interface PersonaContextValue {
  persona: UserId
  setPersona: (id: UserId) => void
}

export const PersonaContext = createContext<PersonaContextValue | null>(null)

/** Access the current persona. */
export function usePersona() {
  const ctx = useContext(PersonaContext)
  if (!ctx) throw new Error('usePersona must be used inside PersonaProvider')
  return ctx
}
