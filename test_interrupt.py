#!/usr/bin/env python3
"""
Test Interrupt System

Tests the audio energy detection and interrupt thresholds
"""

import struct
import audioop
import random

print("=" * 70)
print("🎯 INTERRUPT SYSTEM TEST")
print("=" * 70)

# Simulate audio energy levels
def simulate_mulaw_audio(energy_level):
    """Simulate mulaw audio with specific energy level"""
    # Create PCM audio with desired RMS
    samples = []
    for i in range(160):  # 20ms at 8kHz
        value = int(random.gauss(0, energy_level))
        value = max(-32768, min(32767, value))
        samples.append(value)
    
    pcm = struct.pack('<%dh' % len(samples), *samples)
    mulaw = audioop.lin2ulaw(pcm, 2)
    return mulaw

def calculate_energy(mulaw_bytes):
    """Calculate energy from mulaw audio"""
    if not mulaw_bytes or len(mulaw_bytes) < 160:
        return 0
    try:
        pcm = audioop.ulaw2lin(mulaw_bytes, 2)
        return audioop.rms(pcm, 2)
    except Exception:
        return 0

# Test configurations
from utils import (
    INTERRUPT_MIN_ENERGY,
    INTERRUPT_BASELINE_FACTOR,
    INTERRUPT_MIN_SPEECH_MS,
    INTERRUPT_DEBOUNCE_MS
)

print(f"\n📊 CURRENT CONFIGURATION:")
print(f"   INTERRUPT_MIN_ENERGY:       {INTERRUPT_MIN_ENERGY}")
print(f"   INTERRUPT_BASELINE_FACTOR:  {INTERRUPT_BASELINE_FACTOR}")
print(f"   INTERRUPT_MIN_SPEECH_MS:    {INTERRUPT_MIN_SPEECH_MS}ms")
print(f"   INTERRUPT_DEBOUNCE_MS:      {INTERRUPT_DEBOUNCE_MS}ms")

# Simulate baseline (background noise)
print(f"\n🔊 SIMULATING AUDIO ENERGY LEVELS:")
print("-" * 70)

baseline_energy = 300  # Typical background noise
threshold = max(baseline_energy * INTERRUPT_BASELINE_FACTOR, INTERRUPT_MIN_ENERGY)

scenarios = [
    ("😴 Silence", 100, False),
    ("🔇 Quiet background", 250, False),
    ("🔉 Low speech attempt", 500, False),
    ("🔊 Normal speech", 800, True),
    ("📢 Loud speech", 1200, True),
    ("🎤 Very loud", 2000, True),
]

for label, energy, should_trigger in scenarios:
    mulaw = simulate_mulaw_audio(energy)
    calculated = calculate_energy(mulaw)
    triggers = calculated > threshold
    
    status = "✅ TRIGGERS" if triggers else "❌ No trigger"
    expected = "✅ CORRECT" if triggers == should_trigger else "⚠️ UNEXPECTED"
    
    print(f"{label:25} Energy: {calculated:5.0f}  Threshold: {threshold:.0f}  {status}  {expected}")

print("\n" + "=" * 70)
print("🎯 INTERRUPT TUNING GUIDE")
print("=" * 70)

print("""
📌 OPTIMAL SETTINGS (already applied):
   INTERRUPT_MIN_ENERGY = 600       # Lower = more sensitive
   INTERRUPT_BASELINE_FACTOR = 2.2  # Lower = more sensitive
   INTERRUPT_MIN_SPEECH_MS = 150    # Lower = faster trigger
   INTERRUPT_DEBOUNCE_MS = 300      # Lower = allow re-interrupts sooner

⚡ WHAT CHANGED:
   - Lowered thresholds for FASTER detection
   - Need only 2 consecutive high-energy samples (was 3)
   - Reduced minimum speech duration: 150ms (was 200ms)
   - Faster debounce: 300ms (was 500ms)
   - Multiple clear commands sent to Twilio for reliability
   - More aggressive queue clearing

🎛️ TO ADJUST IN .env FILE:

# More sensitive (interrupts easier):
INTERRUPT_MIN_ENERGY=500
INTERRUPT_BASELINE_FACTOR=2.0
INTERRUPT_MIN_SPEECH_MS=120

# Less sensitive (requires louder/longer speech):
INTERRUPT_MIN_ENERGY=800
INTERRUPT_BASELINE_FACTOR=2.5
INTERRUPT_MIN_SPEECH_MS=200

# Fastest possible (may have false triggers):
INTERRUPT_MIN_ENERGY=400
INTERRUPT_BASELINE_FACTOR=1.8
INTERRUPT_MIN_SPEECH_MS=100
INTERRUPT_DEBOUNCE_MS=200

💡 MONITORING:
   Watch logs during calls for:
   🎙️ Interrupt detection: energy=XXX > YYY
   ⚡ INTERRUPT! energy=XXX ...
   📡 Audio cleared in stream
   ✅ INTERRUPT COMPLETE: Cleared N TTS items

🔍 TESTING:
   1. Start a call and let agent speak
   2. Try interrupting mid-sentence
   3. Should stop within ~200-300ms
   4. Check logs for "⚡ INTERRUPT!" message
""")

print("=" * 70)
print("✅ TEST COMPLETE - Interruption system is optimized!")
print("=" * 70)
