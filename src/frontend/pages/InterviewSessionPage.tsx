/**
 * InterviewSessionPage – 访谈对话页面 (/interview/session/:projectId)
 *
 * 聊天式智能访谈界面，含消息发送、AI 响应、隐含缺口引导、
 * 一键补全、侧边栏实体展示、30 轮自动结束提示。
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Card,
  Input,
  Button,
  List,
  Typography,
  Tag,
  Modal,
  Spin,
  Alert,
  Badge,
  Space,
  Drawer,
  message as antMessage,
} from 'antd';
import {
  SendOutlined,
  BulbOutlined,
  AudioOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import InterviewLayout from '../layouts/InterviewLayout';
import VoiceRecorder from '../components/VoiceRecorder';
import TranscriptionPanel from '../components/TranscriptionPanel';
import type { PartialTranscript, CompletionOutline } from '../types/asr';

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  gaps?: Array<{ gap_description: string; suggested_question: string }>;
  source?: 'voice';
}

interface CompletionSuggestion {
  suggestion_text: string;
  category: string;
}

const InterviewSessionPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentRound, setCurrentRound] = useState(0);
  const [sessionEnded, setSessionEnded] = useState(false);
  const [completions, setCompletions] = useState<CompletionSuggestion[]>([]);
  const [showCompletions, setShowCompletions] = useState(false);
  const [showEntities, setShowEntities] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [transcripts, setTranscripts] = useState<PartialTranscript[]>([]);
  const [outline, setOutline] = useState<CompletionOutline | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const maxRounds = 30;

  useEffect(() => {
    listRef.current?.scrollTo(0, listRef.current.scrollHeight);
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading || sessionEnded) return;
    const userMsg: ChatMessage = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // Stub: in production, call POST /api/interview/sessions/{id}/messages
      const aiContent = `感谢您的信息。关于「${input.slice(0, 50)}」，请问还有哪些具体的业务规则需要补充？`;
      const gaps =
        currentRound > 1
          ? [{ gap_description: '边界条件未明确', suggested_question: '请描述极端情况的处理方式' }]
          : [];

      const aiMsg: ChatMessage = { role: 'assistant', content: aiContent, gaps };
      setMessages((prev) => [...prev, aiMsg]);
      setCurrentRound((r) => r + 1);

      if (currentRound + 1 >= maxRounds) {
        setSessionEnded(true);
        setSummary(`访谈已完成，共 ${maxRounds} 轮对话。`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCompletions = () => {
    setCompletions([
      { suggestion_text: '建议补充实体属性约束', category: 'entity_attribute' },
      { suggestion_text: '建议描述异常处理规则', category: 'business_rule' },
      { suggestion_text: '建议明确实体间关联', category: 'relation' },
      { suggestion_text: '建议补充审批流程', category: 'workflow' },
      { suggestion_text: '建议说明数据校验规则', category: 'business_rule' },
    ]);
    setShowCompletions(true);
  };

  // ------------------------------------------------------------------
  // Voice recording handlers
  // ------------------------------------------------------------------

  const handleTranscript = useCallback((transcript: PartialTranscript) => {
    setTranscripts((prev) => [...prev, transcript]);
  }, []);

  const handleOutline = useCallback((newOutline: CompletionOutline) => {
    setOutline(newOutline);
  }, []);

  const handleRecordingStart = useCallback(() => {
    setIsRecording(true);
    setTranscripts([]);
    setOutline(null);
  }, []);

  const handleRecordingStop = useCallback(
    async (accumulatedText: string) => {
      setIsRecording(false);
      if (!accumulatedText.trim()) return;

      // Submit accumulated text as a voice-sourced user message
      const userMsg: ChatMessage = { role: 'user', content: accumulatedText, source: 'voice' };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        // Stub: in production, call POST /api/interview/sessions/{id}/messages
        const aiContent = `感谢您的语音输入。关于「${accumulatedText.slice(0, 50)}」，请问还有哪些具体的业务规则需要补充？`;
        const gaps =
          currentRound > 1
            ? [{ gap_description: '边界条件未明确', suggested_question: '请描述极端情况的处理方式' }]
            : [];

        const aiMsg: ChatMessage = { role: 'assistant', content: aiContent, gaps };
        setMessages((prev) => [...prev, aiMsg]);
        setCurrentRound((r) => r + 1);

        if (currentRound + 1 >= maxRounds) {
          setSessionEnded(true);
          setSummary(`访谈已完成，共 ${maxRounds} 轮对话。`);
        }
      } finally {
        setLoading(false);
      }
    },
    [currentRound, maxRounds],
  );

  const handleVoiceError = useCallback((error: string) => {
    antMessage.error(error);
  }, []);

  return (
    <InterviewLayout>
      <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
        {/* Header */}
        <Card size="small" style={{ marginBottom: 8 }}>
          <Space>
            <Title level={5} style={{ margin: 0 }}>智能访谈</Title>
            <Badge count={`${currentRound}/${maxRounds}`} style={{ backgroundColor: currentRound >= 25 ? '#ff4d4f' : '#52c41a' }} />
            <Button size="small" icon={<UnorderedListOutlined />} onClick={() => setShowEntities(true)}>
              实体列表
            </Button>
            <Button size="small" icon={<BulbOutlined />} onClick={handleCompletions}>
              一键补全
            </Button>
          </Space>
        </Card>

        {currentRound >= 25 && !sessionEnded && (
          <Alert message={`距离自动结束还剩 ${maxRounds - currentRound} 轮`} type="warning" showIcon style={{ marginBottom: 8 }} />
        )}

        {summary && (
          <Alert message="访谈摘要" description={summary} type="success" showIcon style={{ marginBottom: 8 }} />
        )}

        {/* Transcription Panel – shown when recording or when transcripts exist */}
        {(isRecording || transcripts.length > 0) && (
          <TranscriptionPanel
            transcripts={transcripts}
            isRecording={isRecording}
            outline={outline}
          />
        )}

        {/* Messages */}
        <div ref={listRef} style={{ flex: 1, overflow: 'auto', marginBottom: 8 }}>
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item style={{ justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', border: 'none' }}>
                <Card
                  size="small"
                  style={{
                    maxWidth: '70%',
                    backgroundColor: msg.role === 'user' ? '#e6f7ff' : '#f6ffed',
                  }}
                >
                  <Text>
                    {msg.source === 'voice' && (
                      <AudioOutlined style={{ marginRight: 6, color: '#1890ff' }} title="语音输入" />
                    )}
                    {msg.content}
                  </Text>
                  {msg.gaps && msg.gaps.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {msg.gaps.map((g, i) => (
                        <Tag key={i} color="orange" style={{ marginBottom: 4, cursor: 'pointer' }}
                          onClick={() => setInput(g.suggested_question)}>
                          💡 {g.suggested_question}
                        </Tag>
                      ))}
                    </div>
                  )}
                </Card>
              </List.Item>
            )}
          />
          {loading && <Spin style={{ display: 'block', textAlign: 'center' }} />}
        </div>

        {/* Input */}
        <div style={{ display: 'flex', gap: 8 }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder={sessionEnded ? '访谈已结束' : isRecording ? '录音中，请使用语音输入...' : '输入您的业务需求...'}
            disabled={sessionEnded || isRecording}
            autoSize={{ minRows: 1, maxRows: 4 }}
            style={{ flex: 1 }}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} disabled={sessionEnded || loading || isRecording}>
            发送
          </Button>
          <VoiceRecorder
            sessionId={projectId ?? ''}
            disabled={sessionEnded}
            onTranscript={handleTranscript}
            onOutline={handleOutline}
            onRecordingStart={handleRecordingStart}
            onRecordingStop={handleRecordingStop}
            onError={handleVoiceError}
          />
        </div>
      </div>

      {/* Completions modal */}
      <Modal title="补全建议" open={showCompletions} onCancel={() => setShowCompletions(false)} footer={null}>
        <List
          dataSource={completions}
          renderItem={(s) => (
            <List.Item>
              <Tag color="blue">{s.category}</Tag>
              <Text>{s.suggestion_text}</Text>
            </List.Item>
          )}
        />
      </Modal>

      {/* Entity sidebar drawer */}
      <Drawer title="提取的实体" open={showEntities} onClose={() => setShowEntities(false)}>
        <Paragraph>实体提取结果将在对话过程中实时更新。</Paragraph>
        <pre style={{ fontSize: 12 }}>
          {JSON.stringify({ entities: [], rules: [], relations: [] }, null, 2)}
        </pre>
      </Drawer>
    </InterviewLayout>
  );
};

export default InterviewSessionPage;
