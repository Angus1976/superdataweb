/**
 * VoiceRecorder – 实时语音录制组件
 *
 * 使用 MediaRecorder API 采集 webm/opus 音频，通过 WebSocket 流式传输至后端 ASR 引擎，
 * 接收转录结果和 AI 提纲推送。
 *
 * 需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.5
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Button, message } from 'antd';
import { AudioOutlined, PauseCircleOutlined } from '@ant-design/icons';
import type { PartialTranscript, CompletionOutline, ASRWebSocketMessage } from '../types/asr';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface VoiceRecorderProps {
  sessionId: string;
  disabled: boolean;
  onTranscript: (transcript: PartialTranscript) => void;
  onOutline: (outline: CompletionOutline) => void;
  onRecordingStart: () => void;
  onRecordingStop: (accumulatedText: string) => void;
  onError: (error: string) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_INTERVAL_MS = 3000;
const MAX_RECORDING_MS = 30 * 60 * 1000; // 30 minutes
const AUDIO_CHUNK_INTERVAL_MS = 1000; // 1 second

// ---------------------------------------------------------------------------
// Helper – exported for Property 1 testing
// ---------------------------------------------------------------------------

/**
 * Build the ASR WebSocket URL for a given session and JWT token.
 *
 * Uses the current page location to derive the ws/wss protocol and host,
 * appending the token as a query parameter.
 */
export function buildASRWebSocketURL(sessionId: string, token: string): string {
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : 'localhost';
  return `${protocol}//${host}/api/interview/sessions/${encodeURIComponent(sessionId)}/asr?token=${encodeURIComponent(token)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const VoiceRecorder: React.FC<VoiceRecorderProps> = ({
  sessionId,
  disabled,
  onTranscript,
  onOutline,
  onRecordingStart,
  onRecordingStop,
  onError,
}) => {
  // ---- state ----
  const [isRecording, setIsRecording] = useState(false);
  const [duration, setDuration] = useState(0); // seconds

  // ---- refs (mutable across renders, no re-render on change) ----
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const durationTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const maxRecordingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const accumulatedTextRef = useRef('');
  const isStoppingRef = useRef(false);
  const isRecordingRef = useRef(false);

  // Keep isRecordingRef in sync so callbacks can read latest value.
  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  // ---- cleanup on unmount ----
  useEffect(() => {
    return () => {
      cleanupAll();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ------------------------------------------------------------------
  // Cleanup helpers
  // ------------------------------------------------------------------

  const cleanupTimers = useCallback(() => {
    if (durationTimerRef.current) {
      clearInterval(durationTimerRef.current);
      durationTimerRef.current = null;
    }
    if (maxRecordingTimerRef.current) {
      clearTimeout(maxRecordingTimerRef.current);
      maxRecordingTimerRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const cleanupMediaRecorder = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
    }
    if (mediaRecorderRef.current?.stream) {
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
    }
    mediaRecorderRef.current = null;
  }, []);

  const cleanupWebSocket = useCallback(() => {
    if (wsRef.current) {
      try {
        wsRef.current.onopen = null;
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close();
        }
      } catch {
        // ignore
      }
      wsRef.current = null;
    }
  }, []);

  const cleanupAll = useCallback(() => {
    cleanupTimers();
    cleanupMediaRecorder();
    cleanupWebSocket();
  }, [cleanupTimers, cleanupMediaRecorder, cleanupWebSocket]);

  // ------------------------------------------------------------------
  // WebSocket message handler
  // ------------------------------------------------------------------

  const handleWSMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg: ASRWebSocketMessage = JSON.parse(event.data);
        switch (msg.type) {
          case 'transcript':
            if (msg.text) {
              accumulatedTextRef.current += msg.text;
              onTranscript({
                text: msg.text,
                start_time: msg.start_time ?? 0,
                end_time: msg.end_time ?? 0,
                is_final: msg.is_final,
              });
            }
            break;
          case 'outline':
            if (msg.topics) {
              onOutline({ topics: msg.topics });
            }
            break;
          case 'error':
            onError(msg.error_message ?? '转录过程中发生错误');
            break;
          case 'session_message':
            // AI response after recording stop – handled by parent via onRecordingStop
            break;
          default:
            break;
        }
      } catch {
        // Non-JSON frame – ignore
      }
    },
    [onTranscript, onOutline, onError],
  );

  // ------------------------------------------------------------------
  // WebSocket connection
  // ------------------------------------------------------------------

  const connectWebSocket = useCallback(() => {
    const token = localStorage.getItem('access_token') ?? '';
    const url = buildASRWebSocketURL(sessionId, token);

    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectCountRef.current = 0;
    };

    ws.onmessage = handleWSMessage;

    ws.onclose = () => {
      // Only attempt reconnect if we are still recording and not intentionally stopping
      if (!isRecordingRef.current || isStoppingRef.current) return;

      if (reconnectCountRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(() => {
          if (isRecordingRef.current && !isStoppingRef.current) {
            connectWebSocket();
          }
        }, RECONNECT_INTERVAL_MS);
      } else {
        // All reconnect attempts exhausted
        message.error('WebSocket 连接失败，录音已停止');
        stopRecordingInternal(true);
      }
    };

    ws.onerror = () => {
      // onerror is always followed by onclose – handle there
    };
  }, [sessionId, handleWSMessage]); // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------------
  // Stop recording (internal)
  // ------------------------------------------------------------------

  const stopRecordingInternal = useCallback(
    (isError = false) => {
      if (isStoppingRef.current) return;
      isStoppingRef.current = true;

      // Send stop signal before closing
      if (!isError && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: 'stop' }));
        } catch {
          // ignore
        }
      }

      cleanupTimers();
      cleanupMediaRecorder();

      // Give a short delay for final messages before closing WS
      setTimeout(() => {
        cleanupWebSocket();
        const accumulated = accumulatedTextRef.current;
        setIsRecording(false);
        setDuration(0);
        isStoppingRef.current = false;
        onRecordingStop(accumulated);
      }, 300);
    },
    [cleanupTimers, cleanupMediaRecorder, cleanupWebSocket, onRecordingStop],
  );

  // ------------------------------------------------------------------
  // Start recording
  // ------------------------------------------------------------------

  const startRecording = useCallback(async () => {
    // Guard: browser support
    if (typeof MediaRecorder === 'undefined') {
      onError('当前浏览器不支持语音录入功能');
      return;
    }

    // Guard: microphone permission
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError('请允许麦克风权限以使用语音输入');
      return;
    }

    // Reset state
    accumulatedTextRef.current = '';
    reconnectCountRef.current = 0;
    isStoppingRef.current = false;

    // Determine MIME type
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm';

    const recorder = new MediaRecorder(stream, {
      mimeType,
      audioBitsPerSecond: 32000,
    });
    mediaRecorderRef.current = recorder;

    // Connect WebSocket first
    connectWebSocket();

    // Send audio chunks as binary frames
    recorder.ondataavailable = (e: BlobEvent) => {
      if (e.data.size > 0 && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        e.data.arrayBuffer().then((buf) => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(buf);
          }
        });
      }
    };

    recorder.start(AUDIO_CHUNK_INTERVAL_MS);
    setIsRecording(true);
    setDuration(0);
    onRecordingStart();

    // Duration timer (tick every second)
    durationTimerRef.current = setInterval(() => {
      setDuration((d) => d + 1);
    }, 1000);

    // Auto-stop after 30 minutes
    maxRecordingTimerRef.current = setTimeout(() => {
      message.info('录音已达到 30 分钟上限，自动停止');
      stopRecordingInternal();
    }, MAX_RECORDING_MS);
  }, [connectWebSocket, onRecordingStart, onError, stopRecordingInternal]);

  // ------------------------------------------------------------------
  // Toggle handler
  // ------------------------------------------------------------------

  const handleToggle = useCallback(() => {
    if (isRecording) {
      stopRecordingInternal();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecordingInternal]);

  // ------------------------------------------------------------------
  // Format duration as mm:ss
  // ------------------------------------------------------------------

  const formatDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <Button
        shape="circle"
        type={isRecording ? 'primary' : 'default'}
        danger={isRecording}
        icon={isRecording ? <PauseCircleOutlined /> : <AudioOutlined />}
        onClick={handleToggle}
        disabled={disabled}
        title={disabled ? '会话已结束' : isRecording ? '停止录音' : '开始录音'}
      />
      {isRecording && (
        <span style={{ fontSize: 13, color: '#ff4d4f', fontVariantNumeric: 'tabular-nums' }}>
          ● 录音中 {formatDuration(duration)}
        </span>
      )}
    </span>
  );
};

export default VoiceRecorder;
