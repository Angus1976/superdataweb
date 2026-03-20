/**
 * InterviewStartPage – 项目创建页面 (/interview/start)
 *
 * 客户可在此创建项目、选择行业、上传需求文档并查看实体提取结果。
 */

import React, { useState } from 'react';
import {
  Typography,
  Card,
  Form,
  Input,
  Button,
  Upload,
  message,
  Alert,
  Collapse,
  Spin,
} from 'antd';
import { UploadOutlined, PlusOutlined, AudioOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { useNavigate } from 'react-router-dom';
import InterviewLayout from '../layouts/InterviewLayout';
import api from '../services/api';

const { Title } = Typography;
const { TextArea } = Input;

const SUPPORTED_FORMATS = '.docx,.xlsx,.pdf,.pptx,.ppt,.csv,.txt,.md,.json,.xml,.html,.rtf,.jpg,.jpeg,.png,.gif,.bmp,.webp,.svg,.tiff,.mp4,.avi,.mov,.mkv,.wmv,.flv,.webm,.m4v,.zip,.rar,.7z';
const SUPPORTED_AUDIO_FORMATS = '.mp3,.wav,.flac,.ogg,.m4a,.aac,.wma,.opus,.amr';

interface TranscriptionData {
  text: string;
  language: string;
  duration_seconds: number;
  segments: Array<{ start: number; end: number; text: string }>;
}

const InterviewStartPage: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [transcriptionResult, setTranscriptionResult] =
    useState<TranscriptionData | null>(null);
  const [audioUploading, setAudioUploading] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);

  const handleCreateProject = async (values: {
    name: string;
    industry?: string;
    business_domain?: string;
  }) => {
    setLoading(true);
    try {
      const { data } = await api.post('/interview/projects', values);
      message.success('项目创建成功');
      form.resetFields();
      // Navigate to session page to start interview
      if (data?.id) {
        navigate(`/interview/session/${data.id}`);
      }
    } catch {
      message.error('项目创建失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const [uploadedFiles, setUploadedFiles] = useState<Array<{id: string; file_name: string; category: string}>>([]);

  const handleUpload = async (file: UploadFile) => {
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', file as unknown as Blob);

    try {
      const { data } = await api.post('/files/upload', formData);
      setUploadedFiles(prev => [...prev, { id: data.id, file_name: data.file_name, category: data.category }]);
      message.success(`${data.file_name} 上传成功`);
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || '文件上传失败，请重试');
    }
    return false;
  };

  const handleAudioUpload = async (file: UploadFile) => {
    setAudioError(null);
    setTranscriptionResult(null);
    setAudioUploading(true);

    const formData = new FormData();
    formData.append('file', file as unknown as Blob);

    try {
      const { data } = await api.post('/interview/temp-project/upload-audio', formData);
      setTranscriptionResult(data.transcription);
      message.success('录音转写完成');
    } catch (err: any) {
      setAudioError(err.response?.data?.detail || err.response?.data?.message || '录音上传失败，请重试');
    } finally {
      setAudioUploading(false);
    }
    return false;
  };

  return (
    <InterviewLayout>
      <Card style={{ maxWidth: 720, margin: '0 auto' }}>
        <Title level={3}>创建访谈项目</Title>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateProject}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="输入项目名称" maxLength={255} />
          </Form.Item>

          <Form.Item name="industry" label="行业">
            <Input placeholder="输入所属行业（可选）" maxLength={100} />
          </Form.Item>

          <Form.Item name="business_domain" label="业务领域">
            <TextArea rows={2} placeholder="描述业务领域（可选）" />
          </Form.Item>

          <Form.Item label="文件上传（文档/图片/视频/压缩包等）">
            <Upload
              accept={SUPPORTED_FORMATS}
              beforeUpload={handleUpload}
              multiple
              showUploadList
            >
              <Button icon={<UploadOutlined />}>
                上传文件 (Word/Excel/PDF/PPT/图片/视频/ZIP 等)
              </Button>
            </Upload>
          </Form.Item>

          <Form.Item label="录音文件上传（ASR 语音识别）">
            <Spin spinning={audioUploading} tip="正在转写录音，请稍候...">
              <Upload
                accept={SUPPORTED_AUDIO_FORMATS}
                beforeUpload={handleAudioUpload}
                maxCount={1}
                showUploadList
              >
                <Button icon={<AudioOutlined />}>
                  上传录音 (MP3/WAV/FLAC/OGG/M4A/AAC 等)
                </Button>
              </Upload>
            </Spin>
          </Form.Item>

          {audioError && (
            <Alert
              type="error"
              message={audioError}
              showIcon
              closable
              onClose={() => setAudioError(null)}
              style={{ marginBottom: 16 }}
            />
          )}

          {transcriptionResult && (
            <Collapse
              defaultActiveKey={['transcription']}
              style={{ marginBottom: 16 }}
              items={[
                {
                  key: 'transcription',
                  label: `录音转写结果 (语言: ${transcriptionResult.language}, 时长: ${transcriptionResult.duration_seconds}s)`,
                  children: (
                    <div>
                      <div style={{ marginBottom: 12, padding: 12, background: '#f5f5f5', borderRadius: 8 }}>
                        <Typography.Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                          {transcriptionResult.text}
                        </Typography.Paragraph>
                      </div>
                      {transcriptionResult.segments.length > 0 && (
                        <Collapse
                          size="small"
                          items={[{
                            key: 'segments',
                            label: `分段详情 (${transcriptionResult.segments.length} 段)`,
                            children: (
                              <div style={{ maxHeight: 200, overflow: 'auto' }}>
                                {transcriptionResult.segments.map((seg, i) => (
                                  <div key={i} style={{ marginBottom: 4, fontSize: 12 }}>
                                    <span style={{ color: '#667eea', fontFamily: 'monospace' }}>
                                      [{seg.start.toFixed(1)}s - {seg.end.toFixed(1)}s]
                                    </span>{' '}
                                    {seg.text}
                                  </div>
                                ))}
                              </div>
                            ),
                          }]}
                        />
                      )}
                    </div>
                  ),
                },
              ]}
            />
          )}

          {uploadError && (
            <Alert
              type="error"
              message={uploadError}
              showIcon
              closable
              style={{ marginBottom: 16 }}
            />
          )}

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              icon={<PlusOutlined />}
            >
              创建项目
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </InterviewLayout>
  );
};

export default InterviewStartPage;
