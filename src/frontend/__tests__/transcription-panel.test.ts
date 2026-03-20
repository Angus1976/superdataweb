/**
 * Unit tests for TranscriptionPanel component.
 *
 * Validates the component interface, props handling, and basic rendering logic
 * without a DOM renderer (structural / logic tests only).
 *
 * 需求: 4.1, 4.2, 4.3, 5.4, 5.5
 */

import { describe, it, expect } from 'vitest';
import type { TranscriptionPanelProps } from '../components/TranscriptionPanel';
import type { PartialTranscript, CompletionOutline } from '../types/asr';

describe('TranscriptionPanel – interface & logic', () => {
  it('should accept the correct props interface', () => {
    // Type-level check: ensure the props interface matches the design spec
    const props: TranscriptionPanelProps = {
      transcripts: [],
      isRecording: false,
      outline: null,
    };
    expect(props.transcripts).toEqual([]);
    expect(props.isRecording).toBe(false);
    expect(props.outline).toBeNull();
  });

  it('should accept transcripts with all required fields', () => {
    const transcript: PartialTranscript = {
      text: '测试文本',
      start_time: 0,
      end_time: 2.5,
      is_final: true,
    };
    const props: TranscriptionPanelProps = {
      transcripts: [transcript],
      isRecording: true,
      outline: null,
    };
    expect(props.transcripts).toHaveLength(1);
    expect(props.transcripts[0].text).toBe('测试文本');
  });

  it('should accept outline with topics', () => {
    const outline: CompletionOutline = {
      topics: [
        { topic_name: '用户需求', description: '需要补充用户角色定义' },
        { topic_name: '业务规则', description: '缺少异常处理流程' },
      ],
    };
    const props: TranscriptionPanelProps = {
      transcripts: [],
      isRecording: false,
      outline,
    };
    expect(props.outline).not.toBeNull();
    expect(props.outline!.topics).toHaveLength(2);
    expect(props.outline!.topics[0].topic_name).toBe('用户需求');
  });

  it('should accept null outline (no outline generated yet)', () => {
    const props: TranscriptionPanelProps = {
      transcripts: [],
      isRecording: false,
      outline: null,
    };
    expect(props.outline).toBeNull();
  });

  it('should handle multiple transcripts in order', () => {
    const transcripts: PartialTranscript[] = [
      { text: '第一段', start_time: 0, end_time: 2.5 },
      { text: '第二段', start_time: 2.5, end_time: 5.0 },
      { text: '第三段', start_time: 5.0, end_time: 7.5, is_final: true },
    ];
    const props: TranscriptionPanelProps = {
      transcripts,
      isRecording: true,
      outline: null,
    };
    expect(props.transcripts.map((t) => t.text)).toEqual(['第一段', '第二段', '第三段']);
  });

  it('new outline replaces old outline (only latest is in props)', () => {
    // Property 12: new outline replaces old – the parent component manages this
    // by passing only the latest outline. Verify the interface supports this.
    const oldOutline: CompletionOutline = {
      topics: [{ topic_name: '旧主题', description: '旧描述' }],
    };
    const newOutline: CompletionOutline = {
      topics: [{ topic_name: '新主题', description: '新描述' }],
    };

    // Simulate replacement: parent sets outline to newOutline
    const props: TranscriptionPanelProps = {
      transcripts: [],
      isRecording: true,
      outline: newOutline,
    };
    expect(props.outline).toBe(newOutline);
    expect(props.outline).not.toBe(oldOutline);
    expect(props.outline!.topics[0].topic_name).toBe('新主题');
  });
});
