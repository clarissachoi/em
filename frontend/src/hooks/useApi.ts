// Fetch an endpoint for the current persona, re-fetching when the persona changes.

import { useEffect, useRef, useState } from 'react'
import type { UserId } from '../api/client'
import { usePersona } from './usePersona'

export type ApiState<T> = { status: 'loading' } | { status: 'ok'; data: T } | { status: 'error'; error: string }

/** Call an API function once per persona. Results from a previous persona read as loading. */
export function useApi<T>(fn: () => Promise<T>): ApiState<T> {
  const { persona } = usePersona()
  const fnRef = useRef(fn)
  const [result, setResult] = useState<{ persona: UserId; state: ApiState<T> } | null>(null)

  useEffect(() => {
    let cancelled = false
    fnRef
      .current()
      .then((data) => !cancelled && setResult({ persona, state: { status: 'ok', data } }))
      .catch((err: unknown) => !cancelled && setResult({ persona, state: { status: 'error', error: String(err) } }))
    return () => {
      cancelled = true
    }
  }, [persona])

  return result?.persona === persona ? result.state : { status: 'loading' }
}
