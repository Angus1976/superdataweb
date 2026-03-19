import React, { useState } from 'react';
import {
  Upload, Button, Card, Alert, Table, Progress, Space, Typography, message,
} from 'antd';
import { UploadOutlined, FileExcelOutlined, FileTextOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';

const { Title, Text } = Typography;

interface ImportError {
  row: number;
  field: string;
  reason: string;
}

interface ImportResult {
  file_name: string;
  parsed_entities: number;
  parsed_rules: number;
  parsed_relations: number;
  merged_data: {
    total_entities: number;
    total_rules: number;
    total_relations: number;
  };
}

const OfflineImportPage: React.FC<{ projectId: string }> = ({ projectId }) => {
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [errors, setErrors] = useState<ImportError[]>([]);
  const [taskStatus, setTaskStatus] = useState<string>('');

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append('file', file as Blob);

    setImporting(true);
    setErrors([]);
    setResult(null);

    try {
      const resp = await fetch(`/api/interview/${projectId}/import-offline`, {
        method: 'POST',
        body: formData,
        headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      });

      if (!resp.ok) {
        const err = await resp.json();
        if (err.details?.errors) {
          setErrors(err.details.errors);
        }
        throw new Error(err.message || err.detail || 'Import failed');
      }

      const data: ImportResult = await resp.json();
      setResult(data);
      setTaskStatus('completed');
      message.success('导入成功');
      onSuccess?.(data);
    } catch (e: any) {
      message.error(e.message);
      onError?.(e);
    } finally {
      setImporting(false);
    }
  };

  const errorColumns = [
    { title: '行号', dataIndex: 'row', key: 'row', width: 80 },
    { title: '字段', dataIndex: 'field', key: 'field', width: 120 },
    { title: '原因', dataIndex: 'reason', key: 'reason' },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>离线数据导入</Title>
      <Text type="secondary">支持 .xlsx 和 .json 格式文件</Text>

      <Card style={{ marginTop: 16 }}>
        <Upload
          accept=".xlsx,.json"
          customRequest={handleUpload}
          showUploadList={true}
          maxCount={1}
        >
          <Button icon={<UploadOutlined />} loading={importing} size="large">
            选择文件上传
          </Button>
        </Upload>

        <Space style={{ marginTop: 8 }}>
          <Text type="secondary"><FileExcelOutlined /> Excel (.xlsx)</Text>
          <Text type="secondary"><FileTextOutlined /> JSON (.json)</Text>
        </Space>
      </Card>

      {importing && (
        <Card style={{ marginTop: 16 }}>
          <Progress percent={50} status="active" />
          <Text>正在导入并合并数据...</Text>
        </Card>
      )}

      {errors.length > 0 && (
        <Alert
          type="error"
          message="导入失败"
          description={
            <Table
              dataSource={errors}
              columns={errorColumns}
              size="small"
              pagination={false}
              rowKey={(r) => `${r.row}-${r.field}`}
            />
          }
          style={{ marginTop: 16 }}
        />
      )}

      {result && (
        <Card title="导入结果" style={{ marginTop: 16 }}>
          <Space direction="vertical">
            <Text>文件: {result.file_name}</Text>
            <Text>解析实体: {result.parsed_entities}</Text>
            <Text>解析规则: {result.parsed_rules}</Text>
            <Text>解析关系: {result.parsed_relations}</Text>
            <Text strong>合并后 — 实体: {result.merged_data.total_entities}, 规则: {result.merged_data.total_rules}, 关系: {result.merged_data.total_relations}</Text>
          </Space>
        </Card>
      )}
    </div>
  );
};

export default OfflineImportPage;
