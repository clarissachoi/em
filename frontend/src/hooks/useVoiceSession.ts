// Live voice session with Em: mic capture, WebSocket relay to the backend, and gapless playback.

import { useCallback, useEffect, useRef, useState } from 'react'
import { urgentAudioUrl, voiceSocketUrl, type CheckinResult, type VoiceEvent } from '../api/client'

const EM_RATE = 24000 // Em's audio from the backend: 16-bit mono PCM

export type VoiceStatus = 'idle' | 'connecting' | 'live' | 'error'
export interface Turn { role: 'user' | 'em'; text: string }
export interface VoiceAction { name: string; summary: string; changed: boolean }

/** Plays queued PCM chunks back to back and can drop everything on interrupt. */
class Player {
  private ctx = new AudioContext()
  private nextStart = 0
  private sources = new Set<AudioBufferSourceNode>()

  /** Queue one chunk of 16-bit PCM. */
  play(pcm: ArrayBuffer) {
    const samples = new Int16Array(pcm)
    if (samples.length === 0) return
    const buf = this.ctx.createBuffer(1, samples.length, EM_RATE)
    const ch = buf.getChannelData(0)
    for (let i = 0; i < samples.length; i++) ch[i] = samples[i] / 0x8000
    const src = this.ctx.createBufferSource()
    src.buffer = buf
    src.connect(this.ctx.destination)
    const start = Math.max(this.ctx.currentTime + 0.03, this.nextStart)
    src.start(start)
    this.nextStart = start + buf.duration
    this.sources.add(src)
    src.onended = () => this.sources.delete(src)
  }

  /** True while queued audio is still playing. */
  get speaking() {
    return this.nextStart > this.ctx.currentTime
  }

  /** Stop and drop everything queued. */
  flush() {
    for (const src of this.sources) src.stop()
    this.sources.clear()
    this.nextStart = 0
  }

  /** Release the audio device. */
  close() {
    this.flush()
    void this.ctx.close()
  }
}

/** Read the fixed urgent text aloud: the server recording, or browser speech if that fails. */
function speakUrgent(message: string) {
  const fallback = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.speak(new SpeechSynthesisUtterance(message))
  }
  const audio = new Audio(urgentAudioUrl)
  audio.onerror = fallback
  audio.play().catch(fallback)
}

/** Connect to Em over /api/voice. `voiceAlerts` is read live so toggling mid-session applies immediately. */
export function useVoiceSession(voiceAlerts: boolean) {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [actions, setActions] = useState<VoiceAction[]>([])
  const [checkin, setCheckin] = useState<CheckinResult | null>(null)
  const [urgent, setUrgent] = useState<string | null>(null)
  const [micOn, setMicOn] = useState(true)
  const [emSpeaking, setEmSpeaking] = useState(false)

  const ws = useRef<WebSocket | null>(null)
  const player = useRef<Player | null>(null)
  const mic = useRef<{ ctx: AudioContext; stream: MediaStream } | null>(null)
  const micOnRef = useRef(true)
  const alertsRef = useRef(voiceAlerts)
  const emTurnOpen = useRef(false)

  useEffect(() => {
    alertsRef.current = voiceAlerts
  }, [voiceAlerts])

  /** Append a transcript chunk, starting a new bubble when the speaker changes. */
  const addText = useCallback((role: Turn['role'], text: string) => {
    setTurns((prev) => {
      const last = prev[prev.length - 1]
      const continues = last && last.role === role && (role === 'user' || emTurnOpen.current)
      if (role === 'em') emTurnOpen.current = true
      if (continues) return [...prev.slice(0, -1), { role, text: last.text + text }]
      return [...prev, { role, text: text.trimStart() }]
    })
  }, [])

  /** Tear down socket, mic, and playback. */
  const stop = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ type: 'end' }))
    ws.current?.close()
    ws.current = null
    mic.current?.stream.getTracks().forEach((t) => t.stop())
    void mic.current?.ctx.close()
    mic.current = null
    player.current?.close()
    player.current = null
    setEmSpeaking(false)
    setStatus((s) => (s === 'error' ? s : 'idle'))
  }, [])

  /** Handle one JSON event from the backend. */
  const onEvent = useCallback(
    (ev: VoiceEvent) => {
      switch (ev.type) {
        case 'ready':
          setStatus('live')
          break
        case 'transcript':
          addText(ev.role, ev.text)
          break
        case 'turn_complete':
          emTurnOpen.current = false
          break
        case 'interrupted':
          player.current?.flush()
          emTurnOpen.current = false
          break
        case 'tool':
          setActions((prev) => [...prev, { name: ev.name, summary: ev.summary, changed: ev.changed }])
          break
        case 'checkin':
          setCheckin(ev.checkin)
          break
        case 'urgent':
          player.current?.flush()
          setUrgent(ev.message)
          if (alertsRef.current) speakUrgent(ev.message)
          break
        case 'error':
          setError(ev.message)
          setStatus('error')
          break
      }
    },
    [addText],
  )

  /** Ask for the mic, open the socket, and start streaming. */
  const start = useCallback(async () => {
    setError(null)
    setStatus('connecting')
    setTurns([])
    setActions([])
    setCheckin(null)
    emTurnOpen.current = false
    if (alertsRef.current) fetch(urgentAudioUrl).catch(() => {}) // warm the cache so an alert plays instantly

    // Create audio contexts inside the click, before any await, so the browser lets them play.
    const ctx = new AudioContext()
    player.current = new Player()

    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch {
      setError('Microphone access was blocked. You can still type to Em below.')
      stream = new MediaStream()
    }

    mic.current = { ctx, stream }

    const socket = new WebSocket(voiceSocketUrl())
    socket.binaryType = 'arraybuffer'
    ws.current = socket
    socket.onmessage = (msg) => {
      if (msg.data instanceof ArrayBuffer) player.current?.play(msg.data)
      else onEvent(JSON.parse(msg.data) as VoiceEvent)
    }
    socket.onclose = (e) => {
      if (ws.current !== socket) return
      if (e.code === 4404) setError('Unknown persona.')
      stop()
    }
    socket.onerror = () => {
      setError('Could not reach Em. Is the backend running?')
      setStatus('error')
    }

    if (stream.getAudioTracks().length > 0) {
      await ctx.audioWorklet.addModule('/worklets/pcm-recorder.js')
      const node = new AudioWorkletNode(ctx, 'pcm-recorder')
      node.port.onmessage = (e: MessageEvent<ArrayBuffer>) => {
        if (micOnRef.current && socket.readyState === WebSocket.OPEN) socket.send(e.data)
      }
      ctx.createMediaStreamSource(stream).connect(node)
    }
  }, [onEvent, stop])

  /** Send a typed message instead of speaking. */
  const sendText = useCallback(
    (text: string) => {
      if (ws.current?.readyState !== WebSocket.OPEN || !text.trim()) return
      player.current?.flush()
      emTurnOpen.current = false
      ws.current.send(JSON.stringify({ type: 'text', text }))
    },
    [],
  )

  /** Mute or unmute the mic without ending the session. */
  const toggleMic = useCallback(() => {
    micOnRef.current = !micOnRef.current
    setMicOn(micOnRef.current)
  }, [])

  // Poll playback so the UI can show when Em is talking.
  useEffect(() => {
    if (status !== 'live') return
    const id = window.setInterval(() => setEmSpeaking(player.current?.speaking ?? false), 150)
    return () => window.clearInterval(id)
  }, [status])

  useEffect(() => stop, [stop])

  return {
    status, error, turns, actions, checkin, urgent, micOn, emSpeaking,
    start, stop, sendText, toggleMic, dismissUrgent: () => setUrgent(null),
  }
}
