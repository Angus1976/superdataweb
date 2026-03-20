/**
 * InterviewHistoryPage — 访谈记录页面 (/interview/history)
 *
 * 展示当前用户的项目列表及其访谈会话状态。
 * 支持查看项目详情、继续访谈、查看历史会话。
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Typography, Tag, Space, message, Empty, Tooltip,
} from 'antd';
import {
  MessageOutlined, PlusOutlined, EyeOutlined, PlayCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
import InterviewLayout from '../layouts/InterviewLayout';
import api from '../services/api';

const { Title, Text } = Typography;

interface ProjectRecord {
  id: string;
  tenant_id: string;
  name: string;
  industry: string | null;
  business_domain: string | null;
  status: string;
  created_at: string;
}

const industryLabelMap: Record<string, string> = {
  finance: '金融', ecommerce: '电商', manufacturing: '制造',
  healthcare: '医疗', education: '教育',
};

const statusColorMap: Record<string, string> = {
  active: 'green', completed: 'blue', archived: 'default',
};

const statusLabelMap: Record<string, string> = {
  active: '进行中', completed: '已完成', archived: '已归档',
};

const InterviewHistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/interview/projects');
      setProjects(Array.isArray(data) ? data : []);
    } catch {
      message.error('加载项目列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleStartSession = (projectId: string) => {
    navigate(`/interview/session/${projectId}`);
  };

  const columns: ColumnsType<ProjectRecord> = [
    {
      title: '项目名称', dataIndex: 'name', key: 'name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '行业', dataIndex: 'industry', key: 'industry', width: 100,
      render: (val: string | null) => val ? (
        <Tag>{industryLabelMap[val] || val}</Tag>
      ) : <Text type="secondary">-</Text>,
    },
    {
      title: '业务领域', dataIndex: 'business_domain', key: 'business_domain', ellipsis: true, width: 200,
      render: (val: string | null) => val || <Text type="secondary">-</Text>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => (
        <Tag color={statusColorMap[s] || 'default'}>{statusLabelMap[s] || s}</Tag>
      ),
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '操作', key: 'actions', width: 200,
      render: (_: unknown, record: ProjectRecord) => (
        <Space size="small">
          <Tooltip title="开始/继续访谈">
            <Button type="link" icon={<PlayCircleOutlined />} onClick={() => handleStartSession(record.id)} size="small">
              访谈
            </Button>
          </Tooltip>
          <Tooltip title="查看标签">
            <Button type="link" icon={<EyeOutlined />} onClick={() => navigate(`/interview/labels/${record.id}`)} size="small">
              标签
            </Button>
          </Tooltip>
          <Tooltip title="导入离线数据">
            <Button type="link" icon={<MessageOutlined />} onClick={() => navigate(`/interview/import/${record.id}`)} size="small">
              导入
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <InterviewLayout>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>访谈记录</Title>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/interview/start')}>
            新建项目
          </Button>
        </div>

        <Card style={{ borderRadius: 12 }}>
          {projects.length === 0 && !loading ? (
            <Empty description="暂无项目，点击右上角创建新项目">
              <Button type="primary" onClick={() => navigate('/interview/start')}>创建项目</Button>
            </Empty>
          ) : (
            <Table<ProjectRecord>
              rowKey="id"
              columns={columns}
              dataSource={projects}
              loading={loading}
              pagination={{ pageSize: 20, showTotal: n => `共 ${n} 个项目` }}
              scroll={{ x: 800 }}
            />
          )}
        </Card>
      </div>
    </InterviewLayout>
  );
};

export default InterviewHistoryPage;
