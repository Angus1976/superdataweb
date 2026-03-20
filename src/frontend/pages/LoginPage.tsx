import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { MailOutlined, LockOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import LanguageSwitcher from '../components/LanguageSwitcher';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.email, values.password);
      message.success(t('login.loginSuccess'));
      navigate('/interview/start', { replace: true });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || t('login.loginFailed');
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      {/* Language switcher */}
      <div style={styles.langSwitcher}>
        <LanguageSwitcher />
      </div>

      <Card style={styles.card} bordered={false}>
        {/* Brand */}
        <div style={styles.brand}>
          <ThunderboltOutlined style={styles.brandIcon} />
          <Title level={3} style={styles.brandTitle}>SuperInsight</Title>
        </div>

        <Title level={4} style={styles.title}>{t('login.title')}</Title>
        <Text type="secondary" style={styles.subtitle}>{t('login.subtitle')}</Text>

        <Form layout="vertical" onFinish={onFinish} size="large" style={{ marginTop: 28 }}>
          <Form.Item
            name="email"
            rules={[
              { required: true, message: t('login.emailPlaceholder') },
              { type: 'email', message: t('login.emailPlaceholder') },
            ]}
          >
            <Input prefix={<MailOutlined style={{ color: '#667eea' }} />} placeholder={t('login.emailPlaceholder')} />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: t('login.passwordPlaceholder') }]}
          >
            <Input.Password prefix={<LockOutlined style={{ color: '#667eea' }} />} placeholder={t('login.passwordPlaceholder')} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" block loading={loading} style={styles.submitBtn}>
              {t('login.loginButton')}
            </Button>
          </Form.Item>
        </Form>

        <div style={styles.footer}>
          <Space>
            <Text type="secondary">{t('login.noAccount')}</Text>
            <Link to="/register">{t('login.goRegister')}</Link>
          </Space>
        </div>
      </Card>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    minHeight: '100vh',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    padding: 16,
    position: 'relative',
  },
  langSwitcher: {
    position: 'absolute',
    top: 20,
    right: 28,
    zIndex: 10,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    borderRadius: 16,
    boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
    padding: '12px 8px',
  },
  brand: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 8,
  },
  brandIcon: {
    fontSize: 28,
    color: '#667eea',
  },
  brandTitle: {
    margin: 0,
    background: 'linear-gradient(135deg, #667eea, #764ba2)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    fontWeight: 700,
  },
  title: {
    textAlign: 'center',
    marginBottom: 4,
    fontWeight: 600,
  },
  subtitle: {
    display: 'block',
    textAlign: 'center',
    marginBottom: 0,
  },
  submitBtn: {
    height: 44,
    borderRadius: 8,
    fontWeight: 600,
    background: 'linear-gradient(135deg, #667eea, #764ba2)',
    border: 'none',
  },
  footer: {
    textAlign: 'center',
    marginTop: 8,
  },
};

export default LoginPage;
