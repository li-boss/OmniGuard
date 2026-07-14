import { describe, expect, it } from 'vitest'

import { encodePcmWav } from './microphone'

describe('encodePcmWav', () => {
  it('creates a valid mono 16-bit PCM WAV chunk', async () => {
    const samples = new Float32Array([0, 0.5, -0.5, 1, -1])
    const blob = encodePcmWav([samples], samples.length, 16000)
    const arrayBuffer = await new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result)
      reader.onerror = () => reject(reader.error)
      reader.readAsArrayBuffer(blob)
    })
    const view = new DataView(arrayBuffer)
    const text = (offset, length) => Array.from(
      { length },
      (_, index) => String.fromCharCode(view.getUint8(offset + index)),
    ).join('')

    expect(text(0, 4)).toBe('RIFF')
    expect(text(8, 4)).toBe('WAVE')
    expect(view.getUint16(22, true)).toBe(1)
    expect(view.getUint32(24, true)).toBe(16000)
    expect(view.getUint16(34, true)).toBe(16)
    expect(view.getUint32(40, true)).toBe(samples.length * 2)
    expect(blob.size).toBe(44 + samples.length * 2)
  })
})
