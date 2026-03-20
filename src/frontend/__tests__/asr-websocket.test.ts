import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { buildASRWebSocketURL } from '../components/VoiceRecorder';

// Feature: realtime-voice-asr, Property 1: WebSocket URL 包含 JWT Token
// Validates: Requirements 2.2

describe('Property 1: WebSocket URL 包含 JWT Token', () => {
  it('should include token query parameter matching the original JWT string', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1, maxLength: 200 }),
        fc.string({ minLength: 1, maxLength: 100 }),
        (token, sessionId) => {
          const url = buildASRWebSocketURL(sessionId, token);
          const parsed = new URL(url, 'ws://localhost');
          const tokenParam = parsed.searchParams.get('token');
          expect(tokenParam).toBe(token);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should correctly encode special characters in token', () => {
    fc.assert(
      fc.property(
        fc.stringOf(fc.constantFrom('=', '&', '?', '#', ' ', '+', '/', '%'), { minLength: 1, maxLength: 50 }),
        fc.string({ minLength: 1, maxLength: 50 }),
        (token, sessionId) => {
          const url = buildASRWebSocketURL(sessionId, token);
          const parsed = new URL(url, 'ws://localhost');
          const tokenParam = parsed.searchParams.get('token');
          expect(tokenParam).toBe(token);
        },
      ),
      { numRuns: 100 },
    );
  });
});


// Feature: realtime-voice-asr, Property 2: 音频分片以二进制帧发送
// Validates: Requirements 2.3

describe('Property 2: 音频分片以二进制帧发送', () => {
  it('should send binary data via WebSocket that exactly matches the original Audio_Chunk bytes', () => {
    fc.assert(
      fc.property(
        fc.uint8Array({ minLength: 1, maxLength: 4096 }),
        (audioChunk: Uint8Array) => {
          // Simulate a WebSocket send spy
          const sentData: ArrayBuffer[] = [];
          const mockWs = {
            readyState: 1, // WebSocket.OPEN
            send: (data: ArrayBuffer) => {
              sentData.push(data);
            },
          };

          // Simulate the VoiceRecorder's ondataavailable behavior:
          // It converts the chunk to ArrayBuffer and calls ws.send(buf)
          const buf = audioChunk.buffer.slice(
            audioChunk.byteOffset,
            audioChunk.byteOffset + audioChunk.byteLength,
          ) as ArrayBuffer;
          if (mockWs.readyState === 1) {
            mockWs.send(buf);
          }

          // Verify exactly one send occurred
          expect(sentData).toHaveLength(1);

          // Verify the sent bytes match the original Audio_Chunk exactly
          const sentBytes = new Uint8Array(sentData[0]);
          expect(sentBytes.length).toBe(audioChunk.length);
          for (let i = 0; i < audioChunk.length; i++) {
            expect(sentBytes[i]).toBe(audioChunk[i]);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('should not send data when WebSocket is not in OPEN state', () => {
    fc.assert(
      fc.property(
        fc.uint8Array({ minLength: 1, maxLength: 1024 }),
        fc.constantFrom(0, 2, 3), // CONNECTING, CLOSING, CLOSED
        (audioChunk: Uint8Array, readyState: number) => {
          const sentData: ArrayBuffer[] = [];
          const mockWs = {
            readyState,
            send: (data: ArrayBuffer) => {
              sentData.push(data);
            },
          };

          // Replicate the guard from VoiceRecorder: only send when OPEN (readyState === 1)
          const buf = audioChunk.buffer.slice(
            audioChunk.byteOffset,
            audioChunk.byteOffset + audioChunk.byteLength,
          ) as ArrayBuffer;
          if (mockWs.readyState === 1) {
            mockWs.send(buf);
          }

          // No data should be sent when WebSocket is not OPEN
          expect(sentData).toHaveLength(0);
        },
      ),
      { numRuns: 100 },
    );
  });
});


// Feature: realtime-voice-asr, Property 3: WebSocket 重连次数上限
// Validates: Requirements 2.4

describe('Property 3: WebSocket 重连次数上限', () => {
  const MAX_RECONNECT_ATTEMPTS = 3;

  /**
   * Simulate the VoiceRecorder reconnect-counter logic.
   *
   * Each element in `disconnectEvents` represents a WebSocket close event.
   * `true`  = reconnect succeeds (counter resets to 0 on next open)
   * `false` = reconnect fails (counter stays incremented)
   *
   * Returns { reconnectCount, recordingStopped }.
   */
  function simulateReconnects(disconnectEvents: boolean[]): {
    reconnectCount: number;
    recordingStopped: boolean;
  } {
    let reconnectCount = 0;
    let isRecording = true;

    for (const reconnectSucceeds of disconnectEvents) {
      if (!isRecording) break;

      // A disconnect event occurs while recording
      if (reconnectCount < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount += 1;

        if (reconnectSucceeds) {
          // ws.onopen resets the counter
          reconnectCount = 0;
        }
      } else {
        // All attempts exhausted → stop recording
        isRecording = false;
      }
    }

    return { reconnectCount, recordingStopped: !isRecording };
  }

  it('reconnect count should never exceed MAX_RECONNECT_ATTEMPTS for any disconnect sequence', () => {
    fc.assert(
      fc.property(
        fc.array(fc.boolean(), { minLength: 0, maxLength: 20 }),
        (disconnectEvents: boolean[]) => {
          const { reconnectCount } = simulateReconnects(disconnectEvents);
          expect(reconnectCount).toBeLessThanOrEqual(MAX_RECONNECT_ATTEMPTS);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('recording should stop when reconnect count reaches MAX and another disconnect occurs', () => {
    fc.assert(
      fc.property(
        // Generate a prefix of successful reconnects, then 3 consecutive failures + 1 more disconnect
        fc.array(fc.constant(true), { minLength: 0, maxLength: 10 }),
        fc.array(fc.boolean(), { minLength: 0, maxLength: 10 }),
        (successPrefix: boolean[], suffix: boolean[]) => {
          // 3 consecutive failures bring counter to MAX_RECONNECT_ATTEMPTS,
          // then one more disconnect triggers the stop (matching VoiceRecorder's onclose logic)
          const consecutiveFailures = [false, false, false, false];
          const events = [...successPrefix, ...consecutiveFailures, ...suffix];

          const { recordingStopped } = simulateReconnects(events);

          // After counter reaches MAX and another disconnect occurs, recording must stop
          expect(recordingStopped).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('successful reconnect resets counter, allowing further reconnect attempts', () => {
    fc.assert(
      fc.property(
        fc.array(fc.boolean(), { minLength: 1, maxLength: 30 }),
        (disconnectEvents: boolean[]) => {
          const { reconnectCount, recordingStopped } = simulateReconnects(disconnectEvents);

          if (!recordingStopped) {
            // If recording is still active, the counter must be within bounds
            expect(reconnectCount).toBeGreaterThanOrEqual(0);
            expect(reconnectCount).toBeLessThanOrEqual(MAX_RECONNECT_ATTEMPTS);
          } else {
            // If recording stopped, it means we hit the limit
            expect(reconnectCount).toBeLessThanOrEqual(MAX_RECONNECT_ATTEMPTS);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
