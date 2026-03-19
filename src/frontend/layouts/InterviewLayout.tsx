/**
 * InterviewLayout – 访谈模块响应式布局组件
 *
 * 桌面端 (md+): 侧边栏 + 主内容区
 * 移动端 (<md): 折叠侧边栏，全宽主内容区
 */

import React from 'react';
import { Layout, Grid, Menu } from 'antd';
import {
  MessageOutlined,
  FileTextOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content } = Layout;
const { useBreakpoint } = Grid;

interface InterviewLayoutProps {
  children: React.ReactNode;
}

const siderMenuItems = [
  {
    key: '/interview/start',
    icon: <MessageOutlined />,
    label: '发起访谈',
  },
  {
    key: '/interview/history',
    icon: <HistoryOutlined />,
    label: '访谈记录',
  },
  {
    key: '/interview/templates',
    icon: <FileTextOutlined />,
    label: '行业模板',
  },
];

const InterviewLayout: React.FC<InterviewLayoutProps> = ({ children }) => {
  const screens = useBreakpoint();
  const navigate = useNavigate();
  const location = useLocation();

  const showSider = screens.md;

  return (
    <Layout style={{ minHeight: '100vh' }}>
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
  );
};

export default InterviewLayout;
