/**
 * FileManagePage — 管理员文件管理页面
 * 查询和下载客户上传的文件，支持百度网盘配置/授权/同步/分享导入
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Input, Select, Space, Tag, Typography, message,
  Alert, Tooltip, Modal, Form, Divider,
} from 'antd';
import {
  DownloadOutlined, SearchOutlined, CloudUploadOutlined, CloudOutlined,
  LinkOutlined, DisconnectOutlined, CheckCircleOutlined, SettingOutlined,
  ImportOutlined, SafetyCertificateOutlined,
  FileTextOutlined, PictureOutlined, VideoCameraOutlined,
  AudioOutlined, FileZipOutlined, FileOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import InterviewLayout from '../layouts/InterviewLayout';
import api from '../services/api';

const { Title, Text } = Typography;

interface FileRecord {
  id: string;
  original_name: string;
  size_bytes: number;
  extension: string;
  category: string;
  uploaded_by: string;
  tenant_id: string;
  created_at: string;
  baidu_pan_fs_id?: number | null;
  baidu_pan_path?: string | null;
}

interface BaiduPanStatus {
  connected: boolean;
  configured?: boolean;
  baidu_name?: string;
  expires_at?: string;
}

const CATEGORY_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'document', label: '文档' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' },
  { value: 'audio', label: '音频' },
  { value: 'archive', label: '压缩包' },
];

const categoryIcons: Record<string, React.ReactNode> = {
  document: <FileTextOutlined />,
  image: <PictureOutlined />,
  video: <VideoCameraOutlined />,
  audio: <AudioOutlined />,
  archive: <FileZipOutlined />,
  other: <FileOutlined />,
};

const categoryColors: Record<string, string> = {
  document: 'blue', image: 'green', video: 'purple',
  audio: 'orange', archive: 'cyan', other: 'default',
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

const FileManagePage: React.FC = () => {
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [loading, setLoading] = useState(false);
  const [baiduStatus, setBaiduStatus] = useState<BaiduPanStatus>({ connected: false });
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());

  // Config modal state
  const [configOpen, setConfigOpen] = useState(false);
  const [configForm] = Form.useForm();
  const [configSaving, setConfigSaving] = useState(false);
  const [configTesting, setConfigTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Share import modal state
  const [shareOpen, setShareOpen] = useState(false);
  const [shareForm] = Form.useForm();
  const [shareImporting, setShareImporting] = useState(false);

  // ---- Data fetching ----

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, size: pageSize };
      if (search) params.search = search;
      if (category) params.category = category;
      const { data } = await api.get('/files/list', { params });
      setFiles(data.items);
      setTotal(data.total);
    } catch {
      message.error('加载文件列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, category]);

  const fetchBaiduStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/baidu-pan/status');
      setBaiduStatus(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);
  useEffect(() => { fetchBaiduStatus(); }, [fetchBaiduStatus]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('baidu_connected') === '1') {
      message.success('百度网盘授权成功');
      fetchBaiduStatus();
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [fetchBaiduStatus]);

  // ---- Handlers ----

  const handleDownload = async (record: FileRecord) => {
    try {
      const response = await api.get(`/files/download/${record.id}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = record.original_name;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      message.error('下载失败');
    }
  };

  const handleConnectBaidu = async () => {
    try {
      const { data } = await api.get('/baidu-pan/auth-url');
      window.location.href = data.auth_url;
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (detail?.includes('配置')) {
        message.warning('请先配置百度网盘 API Key');
        setConfigOpen(true);
      } else {
        message.error(detail || '获取授权链接失败');
      }
    }
  };

  const handleDisconnectBaidu = async () => {
    try {
      await api.delete('/baidu-pan/disconnect');
      setBaiduStatus(prev => ({ ...prev, connected: false, baidu_name: undefined }));
      message.success('已断开百度网盘');
    } catch {
      message.error('断开失败');
    }
  };

  const handleSyncToBaidu = async (record: FileRecord) => {
    setSyncingIds(prev => new Set(prev).add(record.id));
    try {
      await api.post(`/baidu-pan/sync/${record.id}`);
      message.success(`${record.original_name} 已同步到百度网盘`);
      fetchFiles();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '同步失败');
    } finally {
      setSyncingIds(prev => { const n = new Set(prev); n.delete(record.id); return n; });
    }
  };

  // ---- Config modal handlers ----

  const openConfigModal = async () => {
    setTestResult(null);
    try {
      const { data } = await api.get('/baidu-pan/config');
      if (data.configured) {
        configForm.setFieldsValue({
          app_key: data.app_key,
          secret_key: '',
          app_dir: data.app_dir,
          redirect_uri: data.redirect_uri,
        });
      } else {
        configForm.setFieldsValue({
          app_key: '', secret_key: '',
          app_dir: '/apps/SuperInsight',
          redirect_uri: `${window.location.origin}/api/baidu-pan/callback`,
        });
      }
    } catch {
      configForm.resetFields();
    }
    setConfigOpen(true);
  };

  const handleTestConfig = async () => {
    try {
      const values = await configForm.validateFields(['app_key', 'secret_key']);
      setConfigTesting(true);
      setTestResult(null);
      const { data } = await api.post('/baidu-pan/config/test', {
        app_key: values.app_key,
        secret_key: values.secret_key,
        app_dir: configForm.getFieldValue('app_dir') || '/apps/SuperInsight',
        redirect_uri: configForm.getFieldValue('redirect_uri') || '',
      });
      setTestResult(data);
    } catch (err: any) {
      setTestResult({ ok: false, message: err?.response?.data?.detail || '测试失败' });
    } finally {
      setConfigTesting(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      await api.post('/baidu-pan/config', values);
      message.success('百度网盘配置已保存');
      setConfigOpen(false);
      fetchBaiduStatus();
    } catch (err: any) {
      if (err?.response?.data?.detail) message.error(err.response.data.detail);
    } finally {
      setConfigSaving(false);
    }
  };

  // ---- Share import handlers ----

  const handleImportShare = async () => {
    try {
      const values = await shareForm.validateFields();
      setShareImporting(true);
      const { data } = await api.post('/baidu-pan/import-share', values);
      message.success(`成功导入 ${data.transferred_count} 个文件到百度网盘`);
      setShareOpen(false);
      shareForm.resetFields();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '导入失败');
    } finally {
      setShareImporting(false);
    }
  };

  // ---- Table columns ----

  const columns: ColumnsType<FileRecord> = [
    {
      title: '文件名', dataIndex: 'original_name', key: 'original_name', ellipsis: true,
      render: (name: string, record: FileRecord) => (
        <Space>{categoryIcons[record.category] || categoryIcons.other}{name}</Space>
      ),
    },
    {
      title: '类型', dataIndex: 'category', key: 'category', width: 100,
      render: (cat: string) => <Tag color={categoryColors[cat] || 'default'}>{cat}</Tag>,
    },
    { title: '格式', dataIndex: 'extension', key: 'extension', width: 80, render: (ext: string) => `.${ext}` },
    { title: '大小', dataIndex: 'size_bytes', key: 'size_bytes', width: 100, render: (s: number) => formatSize(s) },
    {
      title: '上传时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '云端', key: 'cloud', width: 80,
      render: (_: unknown, record: FileRecord) =>
        record.baidu_pan_fs_id ? (
          <Tooltip title="已同步到百度网盘"><CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} /></Tooltip>
        ) : null,
    },
    {
      title: '操作', key: 'actions', width: 180,
      render: (_: unknown, record: FileRecord) => (
        <Space size="small">
          <Button type="link" icon={<DownloadOutlined />} onClick={() => handleDownload(record)} size="small">下载</Button>
          {baiduStatus.connected && !record.baidu_pan_fs_id && (
            <Button type="link" icon={<CloudUploadOutlined />} onClick={() => handleSyncToBaidu(record)}
              loading={syncingIds.has(record.id)} size="small">同步</Button>
          )}
        </Space>
      ),
    },
  ];

  // ---- Render ----

  return (
    <InterviewLayout>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <Title level={3} style={{ margin: 0 }}>文件管理</Title>
          <Space>
            <Button icon={<SettingOutlined />} onClick={openConfigModal}>网盘配置</Button>
            {baiduStatus.connected ? (
              <>
                <Tag icon={<CloudOutlined />} color="success">
                  百度网盘: {baiduStatus.baidu_name || '已连接'}
                </Tag>
                <Button size="small" icon={<ImportOutlined />} onClick={() => setShareOpen(true)}>
                  导入分享
                </Button>
                <Button size="small" icon={<DisconnectOutlined />} onClick={handleDisconnectBaidu} danger>
                  断开
                </Button>
              </>
            ) : (
              <Button type="primary" icon={<LinkOutlined />} onClick={handleConnectBaidu}
                disabled={!baiduStatus.configured}>
                {baiduStatus.configured ? '授权百度网盘' : '请先配置API Key'}
              </Button>
            )}
          </Space>
        </div>

        {!baiduStatus.configured && (
          <Alert
            message="尚未配置百度网盘"
            description="点击「网盘配置」按钮填写 API Key 和 Secret Key，测试通过后即可授权连接"
            type="info" showIcon style={{ marginBottom: 16 }}
          />
        )}
        {baiduStatus.configured && !baiduStatus.connected && (
          <Alert
            message="百度网盘已配置，尚未授权"
            description="点击「授权百度网盘」完成 OAuth 授权后即可同步文件"
            type="warning" showIcon style={{ marginBottom: 16 }}
          />
        )}

        {/* Search / Filter */}
        <Card style={{ borderRadius: 12, marginBottom: 16 }}>
          <Space wrap>
            <Input placeholder="搜索文件名" prefix={<SearchOutlined />} allowClear style={{ width: 240 }}
              onChange={e => { setSearch(e.target.value); setPage(1); }} />
            <Select value={category} onChange={v => { setCategory(v); setPage(1); }}
              style={{ width: 140 }} options={CATEGORY_OPTIONS} />
          </Space>
        </Card>

        {/* File table */}
        <Card style={{ borderRadius: 12 }}>
          <Table<FileRecord> rowKey="id" columns={columns} dataSource={files} loading={loading}
            pagination={{
              current: page, pageSize, total,
              onChange: p => setPage(p),
              showTotal: n => `共 ${n} 个文件`,
            }}
            scroll={{ x: 800 }}
          />
        </Card>
      </div>

      {/* ---- Config Modal ---- */}
      <Modal
        title="百度网盘 API 配置"
        open={configOpen}
        onCancel={() => setConfigOpen(false)}
        footer={[
          <Button key="test" icon={<SafetyCertificateOutlined />} loading={configTesting} onClick={handleTestConfig}>
            测试连通
          </Button>,
          <Button key="cancel" onClick={() => setConfigOpen(false)}>取消</Button>,
          <Button key="save" type="primary" loading={configSaving} onClick={handleSaveConfig}>保存</Button>,
        ]}
        width={520}
      >
        <Form form={configForm} layout="vertical" autoComplete="off">
          <Form.Item name="app_key" label="App Key" rules={[{ required: true, message: '请输入 App Key' }]}>
            <Input placeholder="百度网盘开放平台 App Key" />
          </Form.Item>
          <Form.Item name="secret_key" label="Secret Key" rules={[{ required: true, message: '请输入 Secret Key' }]}>
            <Input.Password placeholder="百度网盘开放平台 Secret Key" />
          </Form.Item>
          <Form.Item name="app_dir" label="网盘目录" tooltip="文件在百度网盘中的存储目录">
            <Input placeholder="/apps/SuperInsight" />
          </Form.Item>
          <Form.Item name="redirect_uri" label="回调地址" tooltip="OAuth 回调地址，需与百度开放平台配置一致">
            <Input placeholder="http://localhost:8011/api/baidu-pan/callback" />
          </Form.Item>
        </Form>
        {testResult && (
          <>
            <Divider style={{ margin: '12px 0' }} />
            <Alert
              message={testResult.ok ? '连通测试成功' : '连通测试失败'}
              description={testResult.message}
              type={testResult.ok ? 'success' : 'error'}
              showIcon
            />
          </>
        )}
        <Divider style={{ margin: '12px 0' }} />
        <Text type="secondary" style={{ fontSize: 12 }}>
          请前往 <a href="https://pan.baidu.com/union/doc/" target="_blank" rel="noreferrer">百度网盘开放平台</a> 创建应用获取 API Key
        </Text>
      </Modal>

      {/* ---- Share Import Modal ---- */}
      <Modal
        title="导入百度网盘分享链接"
        open={shareOpen}
        onCancel={() => { setShareOpen(false); shareForm.resetFields(); }}
        onOk={handleImportShare}
        confirmLoading={shareImporting}
        okText="导入"
        width={480}
      >
        <Form form={shareForm} layout="vertical">
          <Form.Item name="share_link" label="分享链接"
            rules={[{ required: true, message: '请输入百度网盘分享链接' }]}>
            <Input placeholder="https://pan.baidu.com/s/1xxxxxx" />
          </Form.Item>
          <Form.Item name="password" label="提取码">
            <Input placeholder="4位提取码（如有）" maxLength={4} style={{ width: 120 }} />
          </Form.Item>
        </Form>
        <Text type="secondary" style={{ fontSize: 12 }}>
          客户可将百度网盘文件通过分享链接发送给您，输入链接和提取码即可将文件转存到您的网盘目录
        </Text>
      </Modal>
    </InterviewLayout>
  );
};

export default FileManagePage;
