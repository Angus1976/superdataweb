import React, { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Input, Space, Tag, Badge, Modal, Form, Select, Switch,
  Upload, Statistic, message, Typography, Row, Col,
} from 'antd';
import {
  PlusOutlined, UploadOutlined, SearchOutlined, UserOutlined,
  EditOutlined, DeleteOutlined, ExclamationCircleOutlined,
  MailOutlined, LockOutlined, BankOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { userApi, enterpriseApi } from '../services/api';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload';

const { Title } = Typography;
const { confirm } = Modal;

interface UserRecord {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface ImportResult {
  success_count: number;
  failure_count: number;
  errors: Array<{ row: number; reason: string }>;
}

const AdminUserPage: React.FC = () => {
  const { t } = useTranslation();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  // Create modal
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm();

  // Edit modal
  const [editOpen, setEditOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editForm] = Form.useForm();
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);

  // Import result modal
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  // Enterprise modal
  const [enterpriseOpen, setEnterpriseOpen] = useState(false);
  const [enterpriseLoading, setEnterpriseLoading] = useState(false);
  const [enterpriseForm] = Form.useForm();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await userApi.listUsers({ page, size: pageSize, search: search || undefined });
      setUsers(data.items);
      setTotal(data.total);
    } catch {
      message.error(t('common.error'));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, t]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Create user
  const handleCreate = async (values: { email: string; password: string; role: string }) => {
    setCreateLoading(true);
    try {
      await userApi.createUser(values);
      message.success(t('common.success'));
      setCreateOpen(false);
      createForm.resetFields();
      fetchUsers();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('common.error'));
    } finally {
      setCreateLoading(false);
    }
  };

  // Edit user
  const openEdit = (record: UserRecord) => {
    setEditingUser(record);
    editForm.setFieldsValue({ role: record.role, is_active: record.is_active });
    setEditOpen(true);
  };

  const handleEdit = async (values: { role: string; is_active: boolean }) => {
    if (!editingUser) return;
    setEditLoading(true);
    try {
      await userApi.updateUser(editingUser.id, values);
      message.success(t('common.success'));
      setEditOpen(false);
      fetchUsers();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('common.error'));
    } finally {
      setEditLoading(false);
    }
  };

  // Delete user
  const handleDelete = (record: UserRecord) => {
    confirm({
      title: t('admin.deleteUser'),
      icon: <ExclamationCircleOutlined />,
      content: t('admin.confirmDelete'),
      okText: t('common.confirm'),
      cancelText: t('common.cancel'),
      okButtonProps: { danger: true },
      async onOk() {
        try {
          await userApi.deleteUser(record.id);
          message.success(t('admin.deleteSuccess'));
          fetchUsers();
        } catch {
          message.error(t('common.error'));
        }
      },
    });
  };

  // Download import template
  const handleDownloadTemplate = () => {
    const BOM = '\uFEFF';
    const header = 'email,password,role';
    const example = 'user@company.com,password123,member';
    const csv = BOM + header + '\n' + example + '\n';
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'user_import_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  // Batch import
  const handleImport = async (file: File) => {
    try {
      const { data } = await userApi.batchImport(file);
      setImportResult(data);
      message.success(t('admin.importSuccess'));
      fetchUsers();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('common.error'));
    }
    return false; // prevent default upload
  };

  // Create enterprise
  const handleCreateEnterprise = async (values: { name: string; code: string; domain?: string }) => {
    setEnterpriseLoading(true);
    try {
      await enterpriseApi.create(values);
      message.success(t('admin.enterpriseCreateSuccess'));
      setEnterpriseOpen(false);
      enterpriseForm.resetFields();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || t('common.error'));
    } finally {
      setEnterpriseLoading(false);
    }
  };

  const columns: ColumnsType<UserRecord> = [
    {
      title: t('admin.email'),
      dataIndex: 'email',
      key: 'email',
      ellipsis: true,
    },
    {
      title: t('admin.role'),
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: (role: string) => (
        <Tag color={role === 'admin' ? 'purple' : 'blue'}>
          {role === 'admin' ? t('admin.roleAdmin') : t('admin.roleMember')}
        </Tag>
      ),
    },
    {
      title: t('admin.status'),
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Badge
          status={active ? 'success' : 'error'}
          text={active ? t('admin.statusActive') : t('admin.statusDisabled')}
        />
      ),
    },
    {
      title: t('common.submit') === 'Submit' ? 'Created At' : '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: t('common.edit'),
      key: 'actions',
      width: 140,
      render: (_: unknown, record: UserRecord) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(record)} size="small">
            {t('common.edit')}
          </Button>
          <Button type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)} size="small">
            {t('common.delete')}
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 24 }}>{t('admin.title')}</Title>

      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card bordered={false} style={cardStyle}>
            <Statistic title={t('admin.totalUsers')} value={total} prefix={<UserOutlined style={{ color: '#667eea' }} />} />
          </Card>
        </Col>
      </Row>

      {/* Action bar */}
      <Card bordered={false} style={{ ...cardStyle, marginBottom: 24 }}>
        <Space wrap style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)} style={primaryBtn}>
              {t('admin.addUser')}
            </Button>
            <Upload
              accept=".xlsx,.csv"
              showUploadList={false}
              beforeUpload={(file: File) => { handleImport(file); return false; }}
            >
              <Button icon={<UploadOutlined />}>{t('admin.batchImport')}</Button>
            </Upload>
            <Button icon={<DownloadOutlined />} onClick={handleDownloadTemplate}>
              {t('admin.downloadTemplate')}
            </Button>
            <Button icon={<BankOutlined />} onClick={() => setEnterpriseOpen(true)}>
              {t('admin.addEnterprise')}
            </Button>
          </Space>
          <Input
            placeholder={t('admin.searchPlaceholder')}
            prefix={<SearchOutlined />}
            allowClear
            style={{ width: 240 }}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => { setSearch(e.target.value); setPage(1); }}
          />
        </Space>
      </Card>

      {/* Table */}
      <Card bordered={false} style={cardStyle}>
        <Table<UserRecord>
          rowKey="id"
          columns={columns}
          dataSource={users}
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: (p: number) => setPage(p),
            showTotal: (total: number) => `${total}`,
            showSizeChanger: false,
          }}
          locale={{ emptyText: t('admin.noData') }}
          scroll={{ x: 700 }}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        title={t('admin.addUser')}
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="email" label={t('admin.email')} rules={[{ required: true, type: 'email' }]}>
            <Input prefix={<MailOutlined />} />
          </Form.Item>
          <Form.Item name="password" label={t('admin.password')} rules={[{ required: true, min: 8 }]}>
            <Input.Password prefix={<LockOutlined />} />
          </Form.Item>
          <Form.Item name="role" label={t('admin.role')} initialValue="member">
            <Select options={[
              { value: 'admin', label: t('admin.roleAdmin') },
              { value: 'member', label: t('admin.roleMember') },
            ]} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={createLoading} style={primaryBtn}>
              {t('common.confirm')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title={t('admin.editUser')}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit}>
          <Form.Item name="role" label={t('admin.role')}>
            <Select options={[
              { value: 'admin', label: t('admin.roleAdmin') },
              { value: 'member', label: t('admin.roleMember') },
            ]} />
          </Form.Item>
          <Form.Item name="is_active" label={t('admin.status')} valuePropName="checked">
            <Switch checkedChildren={t('admin.statusActive')} unCheckedChildren={t('admin.statusDisabled')} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={editLoading} style={primaryBtn}>
              {t('common.save')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Result Modal */}
      <Modal
        title={t('admin.importResult')}
        open={!!importResult}
        onCancel={() => setImportResult(null)}
        footer={<Button onClick={() => setImportResult(null)}>{t('common.confirm')}</Button>}
      >
        {importResult && (
          <div>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={12}>
                <Statistic title={t('admin.successCount')} value={importResult.success_count} valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={12}>
                <Statistic title={t('admin.failureCount')} value={importResult.failure_count} valueStyle={{ color: '#ff4d4f' }} />
              </Col>
            </Row>
            {importResult.errors.length > 0 && (
              <div>
                <Title level={5}>{t('admin.errorDetails')}</Title>
                <Table
                  size="small"
                  dataSource={importResult.errors.map((e: { row: number; reason: string }, i: number) => ({ ...e, key: i }))}
                  columns={[
                    { title: 'Row', dataIndex: 'row', width: 60 },
                    { title: 'Reason', dataIndex: 'reason' },
                  ]}
                  pagination={false}
                  scroll={{ y: 200 }}
                />
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Enterprise Modal */}
      <Modal
        title={t('admin.addEnterprise')}
        open={enterpriseOpen}
        onCancel={() => { setEnterpriseOpen(false); enterpriseForm.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Form form={enterpriseForm} layout="vertical" onFinish={handleCreateEnterprise}>
          <Form.Item name="name" label={t('admin.enterpriseName')} rules={[{ required: true, message: t('admin.enterpriseNamePlaceholder') }]}>
            <Input prefix={<BankOutlined />} placeholder={t('admin.enterpriseNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="code" label={t('admin.enterpriseCode')} rules={[{ required: true, message: t('admin.enterpriseCodePlaceholder') }]}>
            <Input placeholder={t('admin.enterpriseCodePlaceholder')} />
          </Form.Item>
          <Form.Item name="domain" label={t('admin.enterpriseDomain')}>
            <Input placeholder={t('admin.enterpriseDomainPlaceholder')} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={enterpriseLoading} style={primaryBtn}>
              {t('common.confirm')}
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

const cardStyle: React.CSSProperties = {
  borderRadius: 12,
  boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
};

const primaryBtn: React.CSSProperties = {
  borderRadius: 8,
  fontWeight: 600,
  background: 'linear-gradient(135deg, #667eea, #764ba2)',
  border: 'none',
};

export default AdminUserPage;
