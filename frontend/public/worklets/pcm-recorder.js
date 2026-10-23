// Mic capture worklet: downsamples to 16 kHz mono and posts 40 ms chunks of 16-bit PCM.

const TARGET_RATE = 16000
const CHUNK = 640 // 40 ms at 16 kHz

class PcmRecorder extends AudioWorkletProcessor {
  constructor() {
    super()
    this.ratio = sampleRate / TARGET_RATE
    this.out = new Int16Array(CHUNK)
    this.n = 0
    this.acc = 0 // running sum for the current output sample
    this.count = 0 // input samples in the running sum
    this.pos = 0 // input samples consumed toward the next output sample
  }

  /** Average input samples into each output sample (cheap low-pass), then emit full chunks. */
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch) return true
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i]
      this.count++
      this.pos++
      if (this.pos >= this.ratio) {
        const s = Math.max(-1, Math.min(1, this.acc / this.count))
        this.out[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff
        this.acc = 0
        this.count = 0
        this.pos -= this.ratio
        if (this.n === CHUNK) {
          this.port.postMessage(this.out.buffer.slice(0))
          this.n = 0
        }
      }
    }
    return true
  }
}

registerProcessor('pcm-recorder', PcmRecorder)
