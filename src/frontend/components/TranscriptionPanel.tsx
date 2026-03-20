/**
 * TranscriptionPanel – 实时转录文本与 AI 提纲展示面板
 *
 * 接收转录结果数组按序展示，录音中自动滚动至最新文本，
 * 展示最新 CompletionOutline（新提纲替换旧提纲）。
 * 使用独特背景色/边框与聊天消息列表视觉区分。
 *
 * 需求: 4.1, 4.2, 4.3, 5.4, 5.5
 */

import React, { useEffect, useRef } from 'react';
import { Card, Tag, Empty } from 'antd';
import { SoundOutlined, FileTextOutlined } from '@ant-design/icons';
import type { PartialTranscript, CompletionOutline } from '../types/asr';

// ---------------------------------------------------------------------------
// Props – exported for testing
// ---------------------------------------------------------------------------

export interface TranscriptionPanelProps {
  transcripts: PartialTranscript[];
  isRecording: boolean;
  outline: CompletionOutline | null;
}

// ---------------------------------------------------------------------------
// Styles – visually distinct from chat messages (#e6f7ff / #f6ffed)
// ---------------------------------------------------------------------------

const panelStyle: React.CSSProperties = {
  background: '#fffbe6',
  border: '1px solid #ffe58f',
  borderRadius: 8,
  marginBottom: 8,
};

const transcriptAreaStyle: React.CSSProperties = {
  maxHeight: 200,
  overflowY: 'auto',
  padding: '8px 12px',
};

const transcriptItemStyle: React.CSSProperties = {
  padding: '2px 0',
  fontSize: 14,
  lineHeight: 1.6,
};

const finalTextStyle: React.CSSProperties = {
  ...transcriptItemStyle,
  color: 'rgba(0, 0, 0, 0.88)',
};

const partialTextStyle: React.CSSProperties = {
  ...transcriptItemStyle,
  color: 'rgba(0, 0, 0, 0.45)',
  fontStyle: 'italic',
};

const outlineCardStyle: React.CSSProperties = {
  background: '#f6ffed',
  border: '1px solid #b7eb8f',
  borderRadius: 6,
  margin: '8px 12px 12px',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const TranscriptionPanel: React.FC<TranscriptionPanelProps> = ({
  transcripts,
  isRecording,
  outline,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest transcript while recording
  useEffect(() => {
    if (isRecording && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts, isRecording]);

  const hasContent = transcripts.length > 0 || outline !== null;

  if (!hasContent && !isRecording) {
    return null;
  }

  return (
    <div style={panelStyle} data-testid="transcription-panel">
      {/* Header */}
      <div
        style={{
          padding: '8px 12px',
          borderBottom: '1px solid #ffe58f',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <SoundOutlined style={{ color: '#faad14' }} />
        <span style={{ fontWeight: 500, fontSize: 14 }}>
          {isRecording ? '实时转录中...' : '转录结果'}
        </span>
        {isRecording && (
          <Tag color="processing" style={{ marginLeft: 'auto' }}>
            录音中
          </Tag>
        )}
      </div>

      {/* Transcript list */}
      <div ref={scrollRef} style={transcriptAreaStyle} data-testid="transcript-list">
        {transcripts.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="等待语音输入..."
            style={{ margin: '12px 0' }}
          />
        ) : (
          transcripts.map((t, idx) => (
            <div
              key={idx}
              style={t.is_final ? finalTextStyle : partialTextStyle}
              data-testid="transcript-item"
            >
              {t.text}
            </div>
          ))
        )}
      </div>

      {/* AI Outline – latest replaces previous (Property 12) */}
      {outline && outline.topics.length > 0 && (
        <Card
          size="small"
          style={outlineCardStyle}
          data-testid="outline-section"
          title={
            <span>
              <FileTextOutlined style={{ marginRight: 6 }} />
              AI 提纲
            </span>
          }
        >
          {outline.topics.map((topic, idx) => (
            <div key={idx} style={{ marginBottom: idx < outline.topics.length - 1 ? 8 : 0 }}>
              <Tag color="green">{topic.topic_name}</Tag>
              <span style={{ fontSize: 13, color: 'rgba(0,0,0,0.65)' }}>
                {topic.description}
              </span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
};

export default TranscriptionPanel;
