import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Form, Select, Input, InputNumber, Slider, Button, Space,
  message, Spin, Alert, Typography, Row, Col,
} from 'antd';
import {
  ApiOutlined, SaveOutlined, LinkOutlined,
  KeyOutlined, GlobalOutlined, RobotOutlined,
} from '@ant-design/icons';
import api from '../services/api';

const { Title, Text } = Typography;
const { Option } = Select;

/** Provider → default Base URL mapping */
const PROVIDER_DEFAULT_URLS: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  deepseek: 'https://api.deepseek.com/v1',
  tongyi: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  custom: '',
};

interface LLMConfigFormValues {
  provider_name: string;
  api_key: string;
  base_url: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
}

interface TestResult {
  ok: boolean;
  message: string;
  model?: string;
  response_time_ms?: number;
}

const LLMConfigPage: React.FC = () => {
  const [form] = Form.useForm<LLMConfigFormValues>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);

  // Load existing config on mount
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/llm-config/config');
      if (data.configured) {
        form.setFieldsValue({
          provider_name: data.provider_name || 'openai',
          api_key: data.api_key_masked || '',
          base_url: data.base_url || '',
          model_name: data.model_name || '',
          temperature: data.temperature ?? 0.7,
          max_tokens: data.max_tokens ?? 2048,
        });
      }
      setConfigLoaded(true);
    } catch {
      message.error('加载配置失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Auto-fill Base URL when provider changes
  const handleProviderChange = (value: string) => {
    const defaultUrl = PROVIDER_DEFAULT_URLS[value] ?? '';
    form.setFieldsValue({ base_url: defaultUrl });
  };

  // Test connectivity
  const handleTestConnection = async () => {
    try {
      const values = await form.validateFields();
      setTesting(true);
      setTestResult(null);
      const { data } = await api.post('/llm-config/config/test', values);
      setTestResult(data);
    } catch (err: any) {
      if (err?.response?.data) {
        setTestResult({ ok: false, message: err.response.data.detail || '测试失败' });
      } else if (err?.errorFields) {
        // form validation error — do nothing
      } else {
        setTestResult({ ok: false, message: '网络错误，请检查连接' });
      }
    } finally {
      setTesting(false);
    }
  };

  // Save config
  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.post('/llm-config/config', values);
      message.success('配置保存成功');
    } catch (err: any) {
      if (err?.response?.data) {
        message.error(err.response.data.detail || '保存失败');
      } else if (!err?.errorFields) {
        message.error('保存失败，请稍后重试');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24 }}>
        <ApiOutlined style={{ marginRight: 8 }} />
        LLM 配置
      </Title>

      <Spin spinning={loading}>
        <Card
          bordered={false}
          style={{ borderRadius: 12, boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}
        >
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              provider_name: 'openai',
              base_url: PROVIDER_DEFAULT_URLS.openai,
              temperature: 0.7,
              max_tokens: 2048,
            }}
          >
            {/* Provider */}
            <Form.Item
              name="provider_name"
              label="服务商"
              rules={[{ required: true, message: '请选择服务商' }]}
            >
              <Select
                placeholder="请选择 LLM 服务商"
                onChange={handleProviderChange}
              >
                <Option value="openai">OpenAI</Option>
                <Option value="deepseek">DeepSeek</Option>
                <Option value="tongyi">通义千问</Option>
                <Option value="custom">自定义</Option>
              </Select>
            </Form.Item>

            {/* API Key */}
            <Form.Item
              name="api_key"
              label="API Key"
              rules={[{ required: true, message: '请输入 API Key' }]}
            >
              <Input.Password
                prefix={<KeyOutlined />}
                placeholder="请输入 API Key"
              />
            </Form.Item>

            {/* Base URL */}
            <Form.Item
              name="base_url"
              label="Base URL"
              rules={[{ required: true, message: '请输入 Base URL' }]}
            >
              <Input
                prefix={<GlobalOutlined />}
                placeholder="请输入 API Base URL"
              />
            </Form.Item>

            {/* Model Name */}
            <Form.Item
              name="model_name"
              label="模型名称"
              rules={[{ required: true, message: '请输入模型名称' }]}
            >
              <Input
                prefix={<RobotOutlined />}
                placeholder="例如：gpt-3.5-turbo、deepseek-chat"
              />
            </Form.Item>

            {/* Temperature */}
            <Form.Item label="Temperature" style={{ marginBottom: 0 }}>
              <Row gutter={16} align="middle">
                <Col flex="auto">
                  <Form.Item name="temperature" noStyle>
                    <Slider
                      min={0}
                      max={2}
                      step={0.1}
                      marks={{ 0: '0', 0.7: '0.7', 1: '1.0', 2: '2.0' }}
                    />
                  </Form.Item>
                </Col>
                <Col>
                  <Form.Item
                    name="temperature"
                    noStyle
                  >
                    <InputNumber
                      min={0}
                      max={2}
                      step={0.1}
                      style={{ width: 80 }}
                    />
                  </Form.Item>
                </Col>
              </Row>
              <Text type="secondary" style={{ fontSize: 12 }}>
                值越高回答越有创意，值越低回答越确定。推荐访谈场景使用 0.7
              </Text>
            </Form.Item>

            {/* Max Tokens */}
            <Form.Item
              name="max_tokens"
              label="Max Tokens"
              rules={[
                { required: true, message: '请输入 Max Tokens' },
                { type: 'number', min: 1, max: 32000, message: '范围：1 - 32000' },
              ]}
              style={{ marginTop: 16 }}
            >
              <InputNumber
                min={1}
                max={32000}
                style={{ width: '100%' }}
                placeholder="最大生成 token 数（1-32000）"
              />
            </Form.Item>

            {/* Test result */}
            {testResult && (
              <Alert
                type={testResult.ok ? 'success' : 'error'}
                showIcon
                message={testResult.ok ? '连接成功' : '连接失败'}
                description={
                  testResult.ok
                    ? `模型: ${testResult.model || '-'}，响应时间: ${testResult.response_time_ms ?? '-'}ms`
                    : testResult.message
                }
                style={{ marginBottom: 16 }}
                closable
                onClose={() => setTestResult(null)}
              />
            )}

            {/* Action buttons */}
            <Form.Item style={{ marginBottom: 0, marginTop: 24 }}>
              <Space>
                <Button
                  icon={<LinkOutlined />}
                  onClick={handleTestConnection}
                  loading={testing}
                >
                  测试连接
                </Button>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSave}
                  loading={saving}
                  style={{
                    borderRadius: 8,
                    fontWeight: 600,
                    background: 'linear-gradient(135deg, #667eea, #764ba2)',
                    border: 'none',
                  }}
                >
                  保存配置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
};

export default LLMConfigPage;
