import { SoundTouchNode } from '@soundtouchjs/audio-worklet';
import processorUrl from '@soundtouchjs/audio-worklet/processor?url';

export class AudioEngine {
  context: AudioContext | null = null;
  buffers: Record<string, AudioBuffer> = {};
  gains: Record<string, GainNode> = {};
  sources: AudioBufferSourceNode[] = [];
  playing = false;
  offset = 0;
  started = 0;
  duration = 0;
  disposed = false;
  tempo = 1;
  semitones = 0;
  processor: SoundTouchNode | null = null;

  async load(projectId: string, stems: string[], renderId?: string) {
    this.context = new AudioContext();
    await this.context.resume();
    await SoundTouchNode.register(this.context, processorUrl);
    // Sequential decoding limits peak memory from simultaneous encoded files.
    for (const stem of stems) {
      const response = await fetch(renderId ? `/api/projects/${projectId}/renders/${renderId}/${stem}` : `/api/projects/${projectId}/audio/${stem}`);
      if (!response.ok) throw new Error(`Could not load ${stem}`);
      const buffer = await this.context.decodeAudioData(await response.arrayBuffer());
      if (this.disposed) throw new Error('Audio loading cancelled');
      this.buffers[stem] = buffer;
      const gain = this.context.createGain();
      this.gains[stem] = gain;
    }
    this.duration = Math.min(...Object.values(this.buffers).map(b => b.duration));
  }

  time() {
    return Math.min(this.duration, this.offset + (this.playing && this.context ? Math.max(0, this.context.currentTime - this.started) * this.tempo : 0));
  }

  async play() {
    if (!this.context || !Object.keys(this.buffers).length) return;
    await this.context.resume();
    if (this.playing) return;
    if (this.offset >= this.duration) this.offset = 0;
    const when = this.context.currentTime + 0.05;
    // Process the mixed signal once: all stems keep the same DSP latency.
    this.processor = new SoundTouchNode({ context: this.context });
    this.processor.playbackRate.value = this.tempo;
    this.processor.pitchSemitones.value = this.semitones;
    this.processor.connect(this.context.destination);
    for (const gain of Object.values(this.gains)) gain.connect(this.processor);
    for (const [stem, buffer] of Object.entries(this.buffers)) {
      const source = this.context.createBufferSource();
      source.buffer = buffer;
      source.playbackRate.value = this.tempo;
      source.connect(this.gains[stem]);
      source.start(when, this.offset);
      this.sources.push(source);
    }
    this.started = when;
    this.playing = true;
  }

  pause() {
    this.offset = Math.max(0, this.time());
    this.sources.forEach(source => { try { source.stop(); } catch { /* Already ended. */ } source.disconnect(); });
    this.sources = [];
    for (const gain of Object.values(this.gains)) gain.disconnect();
    this.processor?.disconnect();
    this.processor?.port.close();
    this.processor = null;
    this.playing = false;
  }

  seek(time: number) {
    this.pause();
    this.offset = Math.max(0, Math.min(this.duration, time));
  }

  controls(tempo: number, semitones: number) {
    if (!Number.isFinite(tempo) || tempo < .5 || tempo > 1.5 ||
        !Number.isInteger(semitones) || Math.abs(semitones) > 12) return;
    // Integrate elapsed source time before changing speed, avoiding playhead jumps.
    this.offset = this.time();
    if (this.context) this.started = Math.max(this.started, this.context.currentTime);
    this.tempo = tempo;
    this.semitones = semitones;
    if (!this.context || !this.processor) return;
    const when = Math.max(this.started, this.context.currentTime);
    for (const source of this.sources) source.playbackRate.setValueAtTime(tempo, when);
    this.processor.playbackRate.setValueAtTime(tempo, when);
    this.processor.pitchSemitones.setValueAtTime(semitones, when);
  }

  mix(volumes: Record<string, number>, muted: string[], solo: string[]) {
    for (const [name, gain] of Object.entries(this.gains)) {
      const audible = !muted.includes(name) && (!solo.length || solo.includes(name));
      gain.gain.setTargetAtTime(audible ? (volumes[name] ?? 1) : 0, this.context!.currentTime, 0.015);
    }
  }

  dispose() {
    this.disposed = true;
    this.pause();
    const context = this.context;
    this.context = null;
    if (context && context.state !== 'closed') void context.close().catch(() => {});
    this.buffers = {};
    this.gains = {};
  }
}
