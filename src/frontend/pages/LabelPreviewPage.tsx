import React, { useState } from 'react';
import {
  Card, Button, Tree, Descriptions, Tag, Space, Typography, Spin, message, Drawer,
} from 'antd';
import {
  SyncOutlined, CheckCircleOutlined, ExperimentOutlined,
} from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';

const { Title, Text } = Typography;

interface QualityReport {
  overall_score: number;
  dimension_scores: Record<string, number>;
  suggestions: string[];
}

interface LabelData {
  entities: Array<{ id: string; name: string; type: string; attributes?: any[] }>;
  rules: Array<{ id: string; name: string; condition: string; action: string }>;
  relations: Array<{ id: string; source_entity: string; target_entity: string; relation_type: string }>;
}

const LabelPreviewPage: React.FC<{ projectId: string }> = ({ projectId }) => {
  const [label, setLabel] = useState<LabelData | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [jsonDrawer, setJsonDrawer] = useState(false);

  const generateLabels = async () => {
    setLoading(true);
    try {
      const resp = await fetch(`/api/interview/${projectId}/generate-labels`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      });
      if (!resp.ok) throw new Error('标签生成失败');
      const data = await resp.json();
      message.success(`任务已提交: ${data.task_id}`);
      // In production: poll task status until completed, then load label
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const syncToLabelStudio = async () => {
    setSyncing(true);
    try {
      const resp = await fetch(`/api/interview/${projectId}/sync-to-label-studio`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Sync failed');
      }
      const data = await resp.json();
      message.success(`同步完成: ${data.sync_result.success_count} 个任务`);
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setSyncing(false);
    }
  };

  const buildTreeData = (data: LabelData): DataNode[] => [
    {
      title: `实体 (${data.entities.length})`,
      key: 'entities',
      children: data.entities.map((e) => ({
        title: `${e.name} [${e.type}]`,
        key: `entity-${e.id}`,
        isLeaf: true,
      })),
    },
    {
      title: `规则 (${data.rules.length})`,
      key: 'rules',
      children: data.rules.map((r) => ({
        title: `${r.name}: ${r.condition} → ${r.action}`,
        key: `rule-${r.id}`,
        isLeaf: true,
      })),
    },
    {
      title: `关系 (${data.relations.length})`,
      key: 'relations',
      children: data.relations.map((r) => ({
        title: `${r.source_entity} —[${r.relation_type}]→ ${r.target_entity}`,
        key: `rel-${r.id}`,
        isLeaf: true,
      })),
    },
  ];

  const scoreColor = (score: number) =>
    score >= 0.8 ? 'green' : score >= 0.5 ? 'orange' : 'red';

  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>AI Friendly Label 预览</Title>

      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<ExperimentOutlined />}
          onClick={generateLabels}
          loading={loading}
        >
          生成标签
        </Button>
        <Button
          icon={<SyncOutlined />}
          onClick={syncToLabelStudio}
          loading={syncing}
          disabled={!label}
        >
          同步至 Label Studio
        </Button>
        {label && (
          <Button onClick={() => setJsonDrawer(true)}>查看 JSON</Button>
        )}
      </Space>

      {label && (
        <Card title="标签结构" style={{ marginBottom: 16 }}>
          <Tree
            defaultExpandAll
            treeData={buildTreeData(label)}
            showLine
          />
        </Card>
      )}

      {quality && (
        <Card title="质量评估报告" style={{ marginBottom: 16 }}>
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="综合评分">
              <Tag color={scoreColor(quality.overall_score)} icon={<CheckCircleOutlined />}>
                {(quality.overall_score * 100).toFixed(1)}%
              </Tag>
            </Descriptions.Item>
            {Object.entries(quality.dimension_scores).map(([dim, score]) => (
              <Descriptions.Item label={dim} key={dim}>
                <Tag color={scoreColor(score)}>{(score * 100).toFixed(1)}%</Tag>
              </Descriptions.Item>
            ))}
          </Descriptions>
          {quality.suggestions.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Text strong>建议:</Text>
              <ul>
                {quality.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {!label && !loading && (
        <Card>
          <Text type="secondary">点击"生成标签"开始构建 AI Friendly Label</Text>
        </Card>
      )}

      <Drawer
        title="AI Friendly Label JSON"
        open={jsonDrawer}
        onClose={() => setJsonDrawer(false)}
        width={600}
      >
        <pre style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
          {label ? JSON.stringify(label, null, 2) : ''}
        </pre>
      </Drawer>
    </div>
  );
};

export default LabelPreviewPage;
