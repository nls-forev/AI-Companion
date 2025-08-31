class PCMDownsamplerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._targetRate = 16000;
    this._lastRemainder = new Float32Array(0);
  }

  static get parameterDescriptors() { return []; }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || input.length === 0 || input[0].length === 0) return true;

    const channelData = input[0]; // mono preferred; if stereo, take ch0
    const floatData = channelData;

    // Concatenate previous remainder with new data
    const merged = new Float32Array(this._lastRemainder.length + floatData.length);
    merged.set(this._lastRemainder, 0);
    merged.set(floatData, this._lastRemainder.length);

    // Downsample from sampleRate to 16k
    const inRate = sampleRate; // AudioWorklet global
    const ratio = inRate / this._targetRate;
    const newLen = Math.floor(merged.length / ratio);
    const down = new Float32Array(newLen);

    let inIndex = 0;
    for (let i = 0; i < newLen; i++) {
      const start = Math.floor(i * ratio);
      const end = Math.floor((i + 1) * ratio);
      let sum = 0.0;
      let count = 0;
      for (let j = start; j < end && j < merged.length; j++) {
        sum += merged[j];
        count++;
      }
      down[i] = count > 0 ? sum / count : 0.0;
      inIndex = end;
    }

    // Save remainder samples that were not processed
    const remainderStart = Math.floor(newLen * ratio);
    this._lastRemainder = merged.slice(remainderStart);

    // Convert to 16-bit PCM little-endian
    if (down.length > 0) {
      const pcm = new Int16Array(down.length);
      for (let i = 0; i < down.length; i++) {
        let s = Math.max(-1, Math.min(1, down[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.port.postMessage({ type: 'pcm16', sampleRate: this._targetRate, buffer: pcm.buffer }, [pcm.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-downsampler', PCMDownsamplerProcessor); 