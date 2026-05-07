/**
 * Pokemon Amigo — Shared Game Sound Engine
 * Uses Web Audio API (programmatic sounds) + Web Speech API (Pokemon name calls)
 * No audio files required. Works offline. Zero dependencies.
 *
 * Usage:
 *   GameSounds.play('correct')     — play a named sound
 *   GameSounds.speak('Charizard')  — speak a Pokemon name (Loteria caller)
 *   GameSounds.mute()              — toggle mute
 *   GameSounds.setVolume(0.5)      — 0.0 to 1.0
 */

const GameSounds = (() => {
  let ctx = null;
  let muted = localStorage.getItem('gameSoundMuted') === 'true';
  let volume = parseFloat(localStorage.getItem('gameSoundVolume') || '0.55');

  // Lazy-init AudioContext on first user interaction (browser requirement)
  function getCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
    return ctx;
  }

  // Core: play a tone with envelope
  function tone(freq, duration, type = 'sine', gainPeak = 0.6, startDelay = 0) {
    if (muted) return;
    const c = getCtx();
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.connect(gain);
    gain.connect(c.destination);

    osc.type = type;
    osc.frequency.setValueAtTime(freq, c.currentTime + startDelay);

    const v = gainPeak * volume;
    gain.gain.setValueAtTime(0, c.currentTime + startDelay);
    gain.gain.linearRampToValueAtTime(v, c.currentTime + startDelay + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + startDelay + duration);

    osc.start(c.currentTime + startDelay);
    osc.stop(c.currentTime + startDelay + duration + 0.02);
  }

  // Sweep from one frequency to another
  function sweep(freqStart, freqEnd, duration, type = 'sine', gainPeak = 0.4, startDelay = 0) {
    if (muted) return;
    const c = getCtx();
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.connect(gain);
    gain.connect(c.destination);

    osc.type = type;
    osc.frequency.setValueAtTime(freqStart, c.currentTime + startDelay);
    osc.frequency.exponentialRampToValueAtTime(freqEnd, c.currentTime + startDelay + duration);

    const v = gainPeak * volume;
    gain.gain.setValueAtTime(0, c.currentTime + startDelay);
    gain.gain.linearRampToValueAtTime(v, c.currentTime + startDelay + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + startDelay + duration);

    osc.start(c.currentTime + startDelay);
    osc.stop(c.currentTime + startDelay + duration + 0.02);
  }

  // Noise burst (for buzz/wrong)
  function noise(duration, gainPeak = 0.3, startDelay = 0) {
    if (muted) return;
    const c = getCtx();
    const bufferSize = c.sampleRate * duration;
    const buffer = c.createBuffer(1, bufferSize, c.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1;

    const source = c.createBufferSource();
    source.buffer = buffer;

    const gain = c.createGain();
    const filter = c.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = 400;

    source.connect(filter);
    filter.connect(gain);
    gain.connect(c.destination);

    const v = gainPeak * volume;
    gain.gain.setValueAtTime(v, c.currentTime + startDelay);
    gain.gain.exponentialRampToValueAtTime(0.001, c.currentTime + startDelay + duration);

    source.start(c.currentTime + startDelay);
  }

  // Sound definitions
  const sounds = {

    // UI click / button press
    click() {
      tone(900, 0.07, 'square', 0.25);
    },

    // Correct answer in Silhouette Tower
    correct() {
      tone(659, 0.12, 'sine', 0.5);
      tone(880, 0.18, 'sine', 0.45, 0.1);
    },

    // Wrong answer in Silhouette Tower
    wrong() {
      tone(220, 0.15, 'sawtooth', 0.35);
      tone(180, 0.25, 'sawtooth', 0.3, 0.12);
    },

    // Cash out / Ryo earned
    coin() {
      tone(784, 0.1, 'sine', 0.5);
      tone(1047, 0.1, 'sine', 0.5, 0.1);
      tone(1319, 0.1, 'sine', 0.5, 0.2);
      tone(1568, 0.2, 'sine', 0.55, 0.3);
    },

    // Card flip (Memory)
    flip() {
      sweep(380, 220, 0.18, 'triangle', 0.3);
    },

    // Match found (Memory)
    match() {
      tone(523, 0.1, 'sine', 0.5);
      tone(659, 0.1, 'sine', 0.5, 0.1);
      tone(784, 0.18, 'sine', 0.55, 0.2);
    },

    // Mismatch (Memory) — soft buzz
    mismatch() {
      tone(200, 0.08, 'square', 0.2);
      tone(180, 0.15, 'square', 0.18, 0.07);
    },

    // Timer warning (Memory) — urgent tick
    tick() {
      tone(1047, 0.05, 'square', 0.3);
    },

    // Game/run complete — small victory
    victory() {
      tone(523, 0.1, 'sine', 0.5);
      tone(659, 0.1, 'sine', 0.5, 0.12);
      tone(784, 0.1, 'sine', 0.5, 0.24);
      tone(1047, 0.3, 'sine', 0.6, 0.36);
    },

    // Rare card reveal
    rare() {
      sweep(600, 1200, 0.3, 'sine', 0.4);
      tone(880, 0.25, 'sine', 0.3, 0.2);
    },

    // Secret rare / holo reveal — dramatic
    secret() {
      sweep(300, 1400, 0.4, 'sine', 0.5);
      tone(1047, 0.2, 'sine', 0.4, 0.3);
      tone(1319, 0.2, 'sine', 0.4, 0.45);
      tone(1568, 0.35, 'sine', 0.5, 0.6);
    },

    // Sticker placed in album
    place() {
      tone(1200, 0.06, 'square', 0.3);
      tone(1500, 0.08, 'sine', 0.25, 0.05);
    },

    // Dust earned (sparkle descend)
    dust() {
      tone(1047, 0.08, 'sine', 0.35);
      tone(880, 0.08, 'sine', 0.3, 0.09);
      tone(784, 0.1, 'sine', 0.25, 0.18);
    },

    // Loteria pattern win (cheer burst)
    loteriaWin() {
      tone(523, 0.08, 'sine', 0.45);
      tone(659, 0.08, 'sine', 0.45, 0.09);
      tone(784, 0.08, 'sine', 0.45, 0.18);
      tone(1047, 0.08, 'sine', 0.5, 0.27);
      tone(1319, 0.08, 'sine', 0.55, 0.36);
      tone(1568, 0.25, 'sine', 0.6, 0.45);
    },

    // Loteria new card drawn (subtle chime)
    loteriaDraw() {
      sweep(440, 660, 0.18, 'sine', 0.3);
    },

    // Floor advance in Silhouette Tower
    floorUp() {
      sweep(300, 500, 0.15, 'sine', 0.3);
    },
  };

  // Public API
  function play(name) {
    if (muted) return;
    if (sounds[name]) {
      try {
        sounds[name]();
      } catch (e) {
        // Silently fail — audio is enhancement only
      }
    }
  }

  // Web Speech API — speak a Pokemon name (for Loteria)
  let speechQueue = [];
  let speaking = false;

  // Kid/playful voice: high pitch + slower rate = sounds younger & more animated
  // No browser has a real "child voice" but pitch 1.65+ on any voice mimics it well.
  const KID_VOICE_DEFAULTS = { rate: 0.82, pitch: 1.68 };

  function speak(name, options = {}) {
    if (muted) return;
    if (!window.speechSynthesis) return;

    // Merge kid voice defaults, allow caller overrides
    const merged = Object.assign({}, KID_VOICE_DEFAULTS, options);
    speechQueue.push({ name, options: merged });
    if (!speaking) processQueue();
  }

  function processQueue() {
    if (speechQueue.length === 0) { speaking = false; return; }
    speaking = true;
    const { name, options } = speechQueue.shift();

    const utt = new SpeechSynthesisUtterance(name);
    utt.rate = options.rate;
    utt.pitch = options.pitch;
    utt.volume = options.volume || Math.min(volume * 1.4, 1.0);
    utt.lang = 'en-US';

    // Voice priority: Google US English (Chrome) > Samantha (macOS/iOS) > Alex > any en-US
    // High pitch on these voices produces the most convincing kid-like caller effect
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.lang.startsWith('en') && v.name.includes('Google US English'))
      || voices.find(v => v.name.includes('Samantha'))
      || voices.find(v => v.name.includes('Alex'))
      || voices.find(v => v.lang.startsWith('en-US'))
      || voices.find(v => v.lang.startsWith('en'));
    if (preferred) utt.voice = preferred;

    utt.onend = () => { speaking = false; processQueue(); };
    utt.onerror = () => { speaking = false; processQueue(); };

    window.speechSynthesis.speak(utt);
  }

  function mute() {
    muted = !muted;
    localStorage.setItem('gameSoundMuted', muted);
    if (muted) {
      if (window.speechSynthesis) window.speechSynthesis.cancel();
    } else {
      // Unmuting — unlock AudioContext so sounds can play immediately
      getCtx();
    }
    return muted;
  }

  function setMuted(val) {
    muted = val;
    localStorage.setItem('gameSoundMuted', muted);
  }

  function setVolume(val) {
    volume = Math.max(0, Math.min(1, val));
    localStorage.setItem('gameSoundVolume', volume);
  }

  function isMuted() { return muted; }

  // Cache for decoded AudioBuffers keyed by URL
  const _bufferCache = {};

  /**
   * Fetch a WAV/MP3 URL, decode it, and play through the shared AudioContext.
   * Uses the same volume/mute settings as programmatic sounds.
   * Caches the decoded buffer so repeated calls are instant.
   */
  function playUrl(url) {
    if (muted) return;
    const audioCtx = getCtx();

    function _play(buffer) {
      const source = audioCtx.createBufferSource();
      source.buffer = buffer;
      const gainNode = audioCtx.createGain();
      gainNode.gain.value = volume;
      source.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      source.start(0);
    }

    if (_bufferCache[url]) {
      _play(_bufferCache[url]);
      return;
    }

    fetch(url)
      .then(r => r.arrayBuffer())
      .then(data => audioCtx.decodeAudioData(data))
      .then(buffer => {
        _bufferCache[url] = buffer;
        _play(buffer);
      })
      .catch(err => console.warn('[GameSounds] playUrl failed:', url, err));
  }

  // Init AudioContext on first interaction (required by browsers)
  document.addEventListener('click', () => getCtx(), { once: true });
  document.addEventListener('keydown', () => getCtx(), { once: true });

  // Preload voices for Speech API
  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }

  return { play, speak, mute, setMuted, setVolume, isMuted, playUrl };
})();

// Global alias for convenience
window.GameSounds = GameSounds;
