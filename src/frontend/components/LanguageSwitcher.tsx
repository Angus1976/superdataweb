import React from 'react';
import { Dropdown } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { MenuProps } from 'antd';

const LanguageSwitcher: React.FC = () => {
  const { i18n } = useTranslation();

  const items: MenuProps['items'] = [
    { key: 'zh-CN', label: '中文' },
    { key: 'en-US', label: 'English' },
  ];

  const onClick: MenuProps['onClick'] = ({ key }) => {
    i18n.changeLanguage(key);
    localStorage.setItem('language', key);
  };

  return (
    <Dropdown menu={{ items, onClick, selectedKeys: [i18n.language] }} placement="bottomRight">
      <span style={{ cursor: 'pointer', fontSize: 16, color: 'rgba(255,255,255,0.85)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <GlobalOutlined />
        <span style={{ fontSize: 13 }}>{i18n.language === 'zh-CN' ? '中文' : 'EN'}</span>
      </span>
    </Dropdown>
  );
};

export default LanguageSwitcher;
