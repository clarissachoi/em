import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getVoiceSettings, putVoiceSettings } from '../api/client'
import { useVoiceSession } from '../hooks/useVoiceSession'

/** "Talk to Em" card: live voice conversation, typed fallback, actions, and the urgent banner. */
export default function VoicePanel() {
  const [voiceAlerts, setVoiceAlerts] = useState(true)
  const [draft, setDraft] = useState('')
  const voice = useVoiceSession(voiceAlerts)
  const transcriptEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getVoiceSettings().then((s) => setVoiceAlerts(s.voice_alerts)).catch(() => {})
  }, [])

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: 'nearest' })
  }, [voice.turns])

  const toggleAlerts = (on: boolean) => {
    setVoiceAlerts(on)
    putVoiceSettings({ voice_alerts: on }).catch(() => setVoiceAlerts(!on))
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    voice.sendText(draft)
    setDraft('')
  }

  const live = voice.status === 'live'
  const busy = voice.status === 'connecting'
  const statusText = busy
    ? 'Connecting...'
    : live
      ? voice.emSpeaking
        ? 'Em is speaking'
        : voice.micOn
          ? 'Listening'
          : 'Mic muted'
      : 'Tap to start a conversation'

  return (
    <section className="voice card">
      {voice.urgent && (
        <div className="urgent" role="alert">
          <p>{voice.urgent}</p>
          <div className="urgent-actions">
            <a className="btn danger" href="tel:911">Call 911</a>
            <a className="btn" href="tel:988">Call 988</a>
            <a className="btn" href="sms:988">Text 988</a>
            <button className="btn ghost" onClick={voice.dismissUrgent}>Dismiss</button>
          </div>
        </div>
      )}

      <div className="voice-head">
        <div>
          <h2>Talk to Em</h2>
          <p className={`voice-status ${live ? 'on' : ''}`}>
            <span className="dot" aria-hidden />
            {statusText}
          </p>
        </div>
        <div className="voice-controls">
          {live && (
            <button className="btn ghost" onClick={voice.toggleMic} aria-pressed={!voice.micOn}>
              {voice.micOn ? 'Mute mic' : 'Unmute mic'}
            </button>
          )}
          <button
            className={`mic ${live ? 'live' : ''} ${voice.emSpeaking ? 'speaking' : ''}`}
            onClick={live || busy ? voice.stop : voice.start}
            aria-label={live || busy ? 'End conversation' : 'Start talking to Em'}
          >
            {live || busy ? 'End' : 'Talk'}
          </button>
        </div>
      </div>

      {voice.error && <p className="error">{voice.error}</p>}

      {voice.turns.length > 0 && (
        <div className="transcript" aria-live="polite">
          {voice.turns.map((t, i) => (
            <p key={i} className={`bubble ${t.role}`}>{t.text}</p>
          ))}
          <div ref={transcriptEnd} />
        </div>
      )}

      {voice.actions.length > 0 && (
        <ul className="actions">
          {voice.actions.map((a, i) => (
            <li key={i} className={a.changed ? 'changed' : ''}>{a.summary}</li>
          ))}
        </ul>
      )}

      {voice.checkin && (
        <div className="checkin">
          <strong>Check-in saved</strong>
          <span className="muted">
            Mood {voice.checkin.mood}/5 · Energy {voice.checkin.energy}/5 · Stress {voice.checkin.stress}/5
            {voice.checkin.sleep_quality != null && ` · Sleep ${voice.checkin.sleep_quality}/5`}
          </span>
          {voice.checkin.symptoms.length > 0 && <span className="muted">Symptoms: {voice.checkin.symptoms.join(', ')}</span>}
        </div>
      )}

      {live && (
        <form className="type-row" onSubmit={submit}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Or type to Em" aria-label="Message Em" />
          <button className="btn" type="submit" disabled={!draft.trim()}>Send</button>
        </form>
      )}

      <label className="setting">
        <input type="checkbox" checked={voiceAlerts} onChange={(e) => toggleAlerts(e.target.checked)} />
        <span>
          Read urgent alerts aloud
          <span className="muted"> · Safety messages always show on screen</span>
        </span>
      </label>
      <p className="hint muted">Headphones work best so Em does not hear herself.</p>
    </section>
  )
}
