/**
 * IndustryTemplatePage — 行业模板管理页面 (/interview/templates)
 *
 * 展示预置和自定义行业模板，支持新增、编辑、删除。
 * 后端接口: GET/POST /api/interview/templates, PUT /api/interview/templates/:id
 *
 * 模板编辑弹窗使用结构化四分区编辑器（角色定义、任务描述、行为规则、输出格式），
 * 保存时拼接为完整 system_prompt，编辑时解析回四分区。
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card, Button, Typography, message, Modal, Form, Input, Select, Tag, Space, Empty, Spin,
  Row, Col, Collapse, Tooltip, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined,
  BankOutlined, ShoppingCartOutlined, ToolOutlined, AppstoreOutlined,
  ExperimentOutlined, EyeOutlined,
} from '@ant-design/icons';
import InterviewLayout from '../layouts/InterviewLayout';
import api from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

/* ───────── Constants ───────── */

const MAX_PROMPT_LENGTH = 8000;

const SECTION_MARKERS = {
  role_definition: '## 角色定义',
  task_description: '## 任务描述',
  behavior_rules: '## 行为规则',
  output_format: '## 输出格式',
} as const;

interface StructuredPrompt {
  role_definition: string;
  task_description: string;
  behavior_rules: string;
  output_format: string;
}

/** Assemble four sections into a single system_prompt string. */
function assemblePrompt(p: StructuredPrompt): string {
  return `## 角色定义\n${p.role_definition}\n\n## 任务描述\n${p.task_description}\n\n## 行为规则\n${p.behavior_rules}\n\n## 输出格式\n${p.output_format}`;
}

/**
 * Parse a system_prompt string back into four sections.
 * If parsing fails (missing markers), put everything into role_definition.
 */
function parsePrompt(systemPrompt: string): StructuredPrompt {
  const empty: StructuredPrompt = { role_definition: '', task_description: '', behavior_rules: '', output_format: '' };
  if (!systemPrompt) return empty;

  const markers = [
    SECTION_MARKERS.role_definition,
    SECTION_MARKERS.task_description,
    SECTION_MARKERS.behavior_rules,
    SECTION_MARKERS.output_format,
  ];

  const indices = markers.map((m) => systemPrompt.indexOf(m));

  // If any marker is missing, fallback: everything into role_definition
  if (indices.some((i) => i === -1)) {
    return { ...empty, role_definition: systemPrompt };
  }

  // Ensure markers appear in order
  for (let i = 1; i < indices.length; i++) {
    if (indices[i] <= indices[i - 1]) {
      return { ...empty, role_definition: systemPrompt };
    }
  }

  const extract = (startIdx: number, markerLen: number, endIdx: number | undefined) => {
    const raw = endIdx !== undefined
      ? systemPrompt.slice(startIdx + markerLen, endIdx)
      : systemPrompt.slice(startIdx + markerLen);
    // Trim leading newline and trailing whitespace between sections
    return raw.replace(/^\n/, '').replace(/\n{1,2}$/, '');
  };

  return {
    role_definition: extract(indices[0], markers[0].length, indices[1]),
    task_description: extract(indices[1], markers[1].length, indices[2]),
    behavior_rules: extract(indices[2], markers[2].length, indices[3]),
    output_format: extract(indices[3], markers[3].length, undefined),
  };
}

/* ───────── Types ───────── */

interface TemplateRecord {
  id: string;
  name: string;
  industry: string;
  system_prompt: string;
  config: Record<string, any>;
  is_builtin: boolean;
  created_at: string;
}

const INDUSTRY_OPTIONS = [
  { value: 'finance', label: '金融', icon: <BankOutlined /> },
  { value: 'ecommerce', label: '电商', icon: <ShoppingCartOutlined /> },
  { value: 'manufacturing', label: '制造', icon: <ToolOutlined /> },
  { value: 'healthcare', label: '医疗', icon: <AppstoreOutlined /> },
  { value: 'education', label: '教育', icon: <AppstoreOutlined /> },
  { value: 'other', label: '其他', icon: <AppstoreOutlined /> },
];

const industryColorMap: Record<string, string> = {
  finance: '#1890ff', ecommerce: '#52c41a', manufacturing: '#fa8c16',
  healthcare: '#eb2f96', education: '#722ed1', other: '#8c8c8c',
};

const industryLabelMap: Record<string, string> = {
  finance: '金融', ecommerce: '电商', manufacturing: '制造',
  healthcare: '医疗', education: '教育', other: '其他',
};

/* ───────── Component ───────── */

const IndustryTemplatePage: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [templates, setTemplates] = useState<TemplateRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [filterIndustry, setFilterIndustry] = useState<string>('');

  // Structured prompt state (kept outside form for real-time preview)
  const [structuredPrompt, setStructuredPrompt] = useState<StructuredPrompt>({
    role_definition: '', task_description: '', behavior_rules: '', output_format: '',
  });

  // LLM configuration status
  const [llmConfigured, setLlmConfigured] = useState(false);
  const [testingPrompt, setTestingPrompt] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  // Assembled prompt for preview and validation
  const assembledPrompt = useMemo(() => assemblePrompt(structuredPrompt), [structuredPrompt]);
  const promptLength = assembledPrompt.length;
  const isOverLimit = promptLength > MAX_PROMPT_LENGTH;

  /* ── Data fetching ── */

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (filterIndustry) params.industry = filterIndustry;
      const { data } = await api.get('/interview/templates', { params });
      setTemplates(data);
    } catch {
      message.error('加载模板失败');
    } finally {
      setLoading(false);
    }
  }, [filterIndustry]);

  // Check if LLM is configured
  const checkLlmConfig = useCallback(async () => {
    try {
      const { data } = await api.get('/llm-config/config');
      setLlmConfigured(!!data.configured);
    } catch {
      setLlmConfigured(false);
    }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);
  useEffect(() => { checkLlmConfig(); }, [checkLlmConfig]);

  /* ── Structured prompt helpers ── */

  const updateSection = (key: keyof StructuredPrompt, value: string) => {
    setStructuredPrompt((prev) => ({ ...prev, [key]: value }));
  };

  /* ── Modal open/close ── */

  const openCreate = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({ config: '{"max_rounds": 30, "focus_areas": []}' });
    setStructuredPrompt({ role_definition: '', task_description: '', behavior_rules: '', output_format: '' });
    setTestResult(null);
    setModalOpen(true);
  };

  const openEdit = (t: TemplateRecord) => {
    setEditingId(t.id);
    form.setFieldsValue({
      name: t.name,
      industry: t.industry,
      config: JSON.stringify(t.config, null, 2),
    });
    // Parse existing system_prompt into four sections
    const parsed = parsePrompt(t.system_prompt);
    setStructuredPrompt(parsed);
    setTestResult(null);
    setModalOpen(true);
  };

  /* ── Save ── */

  const handleSave = async () => {
    if (isOverLimit) {
      message.error(`提示词总长度不能超过 ${MAX_PROMPT_LENGTH} 字符（当前 ${promptLength} 字符）`);
      return;
    }
    try {
      const values = await form.validateFields();
      let config = {};
      try { config = JSON.parse(values.config || '{}'); } catch { /* ignore */ }

      // Assemble the four sections into a single system_prompt
      const system_prompt = assemblePrompt(structuredPrompt);
      const payload = { name: values.name, industry: values.industry, system_prompt, config };

      setSaving(true);
      if (editingId) {
        await api.put(`/interview/templates/${editingId}`, payload);
        message.success('模板已更新');
      } else {
        await api.post('/interview/templates', payload);
        message.success('模板已创建');
      }
      setModalOpen(false);
      fetchTemplates();
    } catch (err: any) {
      if (err?.response?.data?.detail) message.error(err.response.data.detail);
    } finally {
      setSaving(false);
    }
  };

  /* ── Test prompt ── */

  const handleTestPrompt = async () => {
    if (!llmConfigured) return;
    setTestingPrompt(true);
    setTestResult(null);
    try {
      const system_prompt = assemblePrompt(structuredPrompt);
      const { data } = await api.post('/llm-config/config/test', {
        system_prompt,
        test_message: '请简单介绍你的角色和能力',
      });
      if (data.ok) {
        setTestResult(data.message || '测试成功');
      } else {
        setTestResult(`测试失败: ${data.message || '未知错误'}`);
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.response?.data?.message || '测试请求失败';
      setTestResult(`测试失败: ${detail}`);
    } finally {
      setTestingPrompt(false);
    }
  };

  /* ── Render ── */

  return (
    <InterviewLayout>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>行业模板</Title>
          <Space>
            <Select
              value={filterIndustry}
              onChange={setFilterIndustry}
              style={{ width: 120 }}
              options={[{ value: '', label: '全部行业' }, ...INDUSTRY_OPTIONS]}
              allowClear
            />
            {isAdmin && (
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增模板</Button>
            )}
          </Space>
        </div>

        <Spin spinning={loading}>
          {templates.length === 0 ? (
            <Card><Empty description="暂无模板" /></Card>
          ) : (
            <Row gutter={[16, 16]}>
              {templates.map(t => (
                <Col key={t.id} xs={24} sm={12} lg={8}>
                  <Card
                    hoverable
                    style={{ borderRadius: 12, height: '100%' }}
                    actions={isAdmin && !t.is_builtin ? [
                      <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(t)} key="edit">编辑</Button>,
                    ] : isAdmin ? [
                      <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(t)} key="edit">编辑</Button>,
                    ] : undefined}
                  >
                    <div style={{ marginBottom: 12 }}>
                      <Space>
                        <Tag color={industryColorMap[t.industry] || '#8c8c8c'}>
                          {industryLabelMap[t.industry] || t.industry}
                        </Tag>
                        {t.is_builtin && <Tag>内置</Tag>}
                      </Space>
                    </div>
                    <Title level={5} style={{ marginBottom: 8 }}>{t.name}</Title>
                    <Paragraph ellipsis={{ rows: 3 }} type="secondary" style={{ fontSize: 13 }}>
                      {t.system_prompt}
                    </Paragraph>
                    {t.config?.focus_areas && (
                      <div>
                        {(t.config.focus_areas as string[]).map((area, i) => (
                          <Tag key={i} style={{ marginBottom: 4 }}>{area}</Tag>
                        ))}
                      </div>
                    )}
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
                      最大轮次: {t.config?.max_rounds || 30}
                    </Text>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Spin>
      </div>

      {/* Create / Edit Modal */}
      <Modal
        title={editingId ? '编辑模板' : '新增模板'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
        okText="保存"
        width={720}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input placeholder="如：金融行业模板" maxLength={100} />
          </Form.Item>
          <Form.Item name="industry" label="行业" rules={[{ required: true, message: '请选择行业' }]}>
            <Select options={INDUSTRY_OPTIONS} placeholder="选择行业" />
          </Form.Item>

          {/* ── Structured Prompt Editor ── */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text strong>系统提示词（结构化编辑）</Text>
              <Text type={isOverLimit ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
                {promptLength} / {MAX_PROMPT_LENGTH} 字符
              </Text>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>角色定义</Text>
                <TextArea
                  rows={3}
                  placeholder="定义 AI 的角色身份，例如：你是一位资深金融行业分析师..."
                  value={structuredPrompt.role_definition}
                  onChange={(e) => updateSection('role_definition', e.target.value)}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>任务描述</Text>
                <TextArea
                  rows={3}
                  placeholder="描述 AI 需要完成的任务，例如：通过访谈了解用户的投资偏好..."
                  value={structuredPrompt.task_description}
                  onChange={(e) => updateSection('task_description', e.target.value)}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>行为规则</Text>
                <TextArea
                  rows={3}
                  placeholder="设定 AI 的行为约束，例如：每次只问一个问题，保持专业友好..."
                  value={structuredPrompt.behavior_rules}
                  onChange={(e) => updateSection('behavior_rules', e.target.value)}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>输出格式</Text>
                <TextArea
                  rows={3}
                  placeholder="指定输出格式要求，例如：以 JSON 格式返回分析结果..."
                  value={structuredPrompt.output_format}
                  onChange={(e) => updateSection('output_format', e.target.value)}
                />
              </div>
            </div>

            {isOverLimit && (
              <Alert
                type="error"
                message={`提示词总长度超出限制（当前 ${promptLength} 字符，上限 ${MAX_PROMPT_LENGTH} 字符）`}
                style={{ marginTop: 8 }}
                showIcon
              />
            )}
          </div>

          {/* ── Preview Panel ── */}
          <Collapse
            ghost
            items={[{
              key: 'preview',
              label: (
                <Space>
                  <EyeOutlined />
                  <span>预览完整提示词</span>
                </Space>
              ),
              children: (
                <pre style={{
                  background: '#f5f5f5',
                  padding: 12,
                  borderRadius: 8,
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                  maxHeight: 300,
                  overflow: 'auto',
                  margin: 0,
                }}>
                  {assembledPrompt}
                </pre>
              ),
            }]}
            style={{ marginBottom: 16 }}
          />

          {/* ── Test Prompt Button ── */}
          <div style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Tooltip title={!llmConfigured ? '请先在 LLM 配置页面完成服务商配置' : undefined}>
                <Button
                  icon={<ExperimentOutlined />}
                  onClick={handleTestPrompt}
                  loading={testingPrompt}
                  disabled={!llmConfigured}
                >
                  测试提示词
                </Button>
              </Tooltip>
              {testResult && (
                <Alert
                  type={testResult.startsWith('测试失败') ? 'error' : 'success'}
                  message={testResult}
                  showIcon
                  closable
                  onClose={() => setTestResult(null)}
                  style={{ whiteSpace: 'pre-wrap' }}
                />
              )}
            </Space>
          </div>

          <Form.Item name="config" label="配置 (JSON)" tooltip="包含 max_rounds、focus_areas 等配置">
            <TextArea rows={4} placeholder='{"max_rounds": 30, "focus_areas": ["风控规则"]}' />
          </Form.Item>
        </Form>
      </Modal>
    </InterviewLayout>
  );
};

export default IndustryTemplatePage;
