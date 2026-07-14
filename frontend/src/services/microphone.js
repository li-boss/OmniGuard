export function encodePcmWav(chunks, frameCount, sampleRate) {
  const buffer = new ArrayBuffer(44 + frameCount * 2)
  const view = new DataView(buffer)

  const writeText = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index))
    }
  }

  writeText(0, 'RIFF')
  view.setUint32(4, 36 + frameCount * 2, true)
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeText(36, 'data')
  view.setUint32(40, frameCount * 2, true)

  let offset = 44
  for (const chunk of chunks) {
    for (let index = 0; index < chunk.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, chunk[index]))
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
      offset += 2
    }
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

export class MicrophoneChunkRecorder {
  constructor({ chunkSeconds = 0.5, onChunk, onLevel }) {
    this.chunkSeconds = chunkSeconds
    this.onChunk = onChunk
    this.onLevel = onLevel
    this.stream = null
    this.context = null
    this.source = null
    this.processor = null
    this.silentGain = null
    this.chunks = []
    this.frameCount = 0
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('当前浏览器不支持麦克风采集')
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      video: false,
    })
    const AudioContext = window.AudioContext || window.webkitAudioContext
    this.context = new AudioContext()
    await this.context.resume()
    this.source = this.context.createMediaStreamSource(this.stream)
    this.processor = this.context.createScriptProcessor(4096, 1, 1)
    this.silentGain = this.context.createGain()
    this.silentGain.gain.value = 0
    this.processor.onaudioprocess = (event) => this.capture(event)
    this.source.connect(this.processor)
    this.processor.connect(this.silentGain)
    this.silentGain.connect(this.context.destination)
  }

  capture(event) {
    const input = event.inputBuffer.getChannelData(0)
    const copy = new Float32Array(input)
    this.chunks.push(copy)
    this.frameCount += copy.length

    let sum = 0
    for (let index = 0; index < copy.length; index += 1) sum += copy[index] ** 2
    this.onLevel?.(Math.sqrt(sum / copy.length))

    const targetFrames = this.context.sampleRate * this.chunkSeconds
    if (this.frameCount >= targetFrames) {
      const blob = encodePcmWav(this.chunks, this.frameCount, this.context.sampleRate)
      this.chunks = []
      this.frameCount = 0
      this.onChunk?.(blob)
    }
  }

  async stop() {
    if (this.processor) this.processor.onaudioprocess = null
    this.source?.disconnect()
    this.processor?.disconnect()
    this.silentGain?.disconnect()
    this.stream?.getTracks().forEach((track) => track.stop())
    if (this.context && this.context.state !== 'closed') await this.context.close()
    this.stream = null
    this.context = null
    this.source = null
    this.processor = null
    this.silentGain = null
    this.chunks = []
    this.frameCount = 0
    this.onLevel?.(0)
  }
}
