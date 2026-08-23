/**
 * AudioWorkletProcessor que roda na thread de áudio, pega os samples crus do
 * microfone (float32, na sampleRate nativa do browser -- geralmente 48000)
 * e reamostra para 16000 Hz PCM16, que é o formato que o backend/Voice Live
 * espera. Envia chunks prontos pro main thread via postMessage.
 */
class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.inputSampleRate = sampleRate; // global do AudioWorkletGlobalScope
    this.resampleRatio = this.inputSampleRate / this.targetSampleRate;
    this.buffer = [];
    this.chunkSize = 2048; // amostras já em 16kHz por chunk (~128ms)
  }

  // reamostragem simples por interpolação linear
  _resample(float32In) {
    const outLength = Math.floor(float32In.length / this.resampleRatio);
    const out = new Float32Array(outLength);
    for (let i = 0; i < outLength; i++) {
      const srcIndex = i * this.resampleRatio;
      const i0 = Math.floor(srcIndex);
      const i1 = Math.min(i0 + 1, float32In.length - 1);
      const frac = srcIndex - i0;
      out[i] = float32In[i0] * (1 - frac) + float32In[i1] * frac;
    }
    return out;
  }

  _floatToInt16(float32) {
    const int16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return int16;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0]; // mono
    const resampled = this.resampleRatio === 1 ? channelData : this._resample(channelData);

    for (let i = 0; i < resampled.length; i++) {
      this.buffer.push(resampled[i]);
    }

    while (this.buffer.length >= this.chunkSize) {
      const chunkFloat = new Float32Array(this.buffer.splice(0, this.chunkSize));
      const int16 = this._floatToInt16(chunkFloat);
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }

    return true;
  }
}

registerProcessor("pcm-recorder-processor", PCMRecorderProcessor);
