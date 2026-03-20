/**
 * InterviewLayout – 访谈模块响应式布局组件
 *
 * 桌面端 (md+): 侧边栏 + 主内容区
 * 移动端 (<md): 折叠侧边栏，全宽主内容区
 */

import React from 'react';
import { Layout, Grid, Menu, Button, Space, Typography } from 'antd';
import {
  MessageOutlined,
  FileTextOutlined,
  HistoryOutlined,
  UserOutlined,
  LogoutOutlined,
  FolderOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import LanguageSwitcher from '../components/LanguageSwitcher';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;
const { useBreakpoint } = Grid;

interface InterviewLayoutProps {
  children: React.ReactNode;
}

const InterviewLayout: React.FC<InterviewLayoutProps> = ({ children }) => {
  const screens = useBreakpoint();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { user, logout } = useAuth();

  const showSider = screens.md;

  const siderMenuItems = [
    {
      key: '/interview/start',
      icon: <MessageOutlined />,
      label: t('menu.interview', '发起访谈'),
    },
    {
      key: '/interview/history',
      icon: <HistoryOutlined />,
      label: t('menu.history', '访谈记录'),
    },
    {
      key: '/interview/templates',
      icon: <FileTextOutlined />,
      label: t('menu.templates', '行业模板'),
    },
    ...(user?.role === 'admin'
      ? [
          {
            key: '/admin/users',
            icon: <UserOutlined />,
            label: t('menu.userManagement', '用户管理'),
          },
          {
            key: '/admin/files',
            icon: <FolderOutlined />,
            label: t('menu.fileManagement', '文件管理'),
          },
          {
            key: '/admin/llm-config',
            icon: <ApiOutlined />,
            label: t('menu.llmConfig', 'LLM 配置'),
          },
        ]
      : []),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          background: '#001529',
        }}
      >
        <Text strong style={{ color: '#fff', fontSize: 18 }}>
          SuperInsight
        </Text>
        <Space size="middle">
          {user?.email && (
            <Text style={{ color: 'rgba(255,255,255,0.85)' }}>
              <UserOutlined style={{ marginRight: 4 }} />
              {user.email}
            </Text>
          )}
          <LanguageSwitcher />
          <Button
            type="text"
            icon={<LogoutOutlined />}
            onClick={handleLogout}
            style={{ color: 'rgba(255,255,255,0.85)' }}
          >
            {t('common.logout', '退出')}
          </Button>
        </Space>
      </Header>
      <Layout>
        {showSider && (
          <Sider width={200} theme="light" breakpoint="md" collapsedWidth={0}>
            <Menu
              mode="inline"
              selectedKeys={[location.pathname]}
              items={siderMenuItems}
              onClick={({ key }) => navigate(key)}
              style={{ height: '100%', borderRight: 0 }}
            />
          </Sider>
        )}
        <Content style={{ padding: showSider ? '24px' : '16px' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default InterviewLayout;
