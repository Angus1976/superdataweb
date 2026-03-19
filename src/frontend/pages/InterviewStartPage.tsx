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
  Select,
  Button,
  Upload,
  message,
  Alert,
  Collapse,
} from 'antd';
import { UploadOutlined, PlusOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import InterviewLayout from '../layouts/InterviewLayout';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const INDUSTRY_OPTIONS = [
  { value: 'finance', label: '金融' },
  { value: 'ecommerce', label: '电商' },
  { value: 'manufacturing', label: '制造' },
];

const SUPPORTED_FORMATS = '.docx,.xlsx,.pdf';

interface ExtractionResultData {
  entities: Array<{ id: string; name: string; type: string }>;
  rules: Array<{ id: string; name: string }>;
  relations: Array<{ id: string; relation_type: string }>;
  confidence: number;
}

const InterviewStartPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [extractionResult, setExtractionResult] =
    useState<ExtractionResultData | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleCreateProject = async (values: {
    name: string;
    industry: string;
    business_domain?: string;
  }) => {
    setLoading(true);
    try {
      const resp = await fetch('/api/interview/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      if (!resp.ok) throw new Error('项目创建失败');
      message.success('项目创建成功');
      form.resetFields();
    } catch {
      message.error('项目创建失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (file: UploadFile) => {
    setUploadError(null);
    setExtractionResult(null);

    const ext = file.name?.split('.').pop()?.toLowerCase() || '';
    if (!['docx', 'xlsx', 'pdf'].includes(ext)) {
      setUploadError(
        `不支持的文件格式: .${ext}。支持格式: ${SUPPORTED_FORMATS}`,
      );
      return false;
    }

    const formData = new FormData();
    formData.append('file', file as unknown as Blob);

    try {
      const resp = await fetch(
        '/api/interview/temp-project/upload-document',
        { method: 'POST', body: formData },
      );
      if (!resp.ok) {
        const err = await resp.json();
        setUploadError(err.message || '文档解析失败');
        return false;
      }
      const data = await resp.json();
      setExtractionResult(data.extraction_result);
      message.success('文档解析完成');
    } catch {
      setUploadError('文档上传失败，请重试');
    }
    return false; // prevent default upload
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

          <Form.Item
            name="industry"
            label="行业"
            rules={[{ required: true, message: '请选择行业' }]}
          >
            <Select placeholder="选择行业">
              {INDUSTRY_OPTIONS.map((opt) => (
                <Option key={opt.value} value={opt.value}>
                  {opt.label}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="business_domain" label="业务领域">
            <TextArea rows={2} placeholder="描述业务领域（可选）" />
          </Form.Item>

          <Form.Item label="需求文档上传">
            <Upload
              accept={SUPPORTED_FORMATS}
              beforeUpload={handleUpload}
              maxCount={1}
              showUploadList
            >
              <Button icon={<UploadOutlined />}>
                上传文档 (Word/Excel/PDF)
              </Button>
            </Upload>
          </Form.Item>

          {uploadError && (
            <Alert
              type="error"
              message={uploadError}
              showIcon
              closable
              style={{ marginBottom: 16 }}
            />
          )}

          {extractionResult && (
            <Collapse
              defaultActiveKey={['result']}
              style={{ marginBottom: 16 }}
              items={[
                {
                  key: 'result',
                  label: `实体提取结果 (置信度: ${(extractionResult.confidence * 100).toFixed(0)}%)`,
                  children: (
                    <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
                      {JSON.stringify(extractionResult, null, 2)}
                    </pre>
                  ),
                },
              ]}
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
