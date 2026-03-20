/**
 * Interview module route definitions.
 *
 * Add these routes to the main React Router configuration:
 *   import { interviewRoutes } from './routes/interviewRoutes';
 *   // inside <Routes>: {interviewRoutes}
 */

import React from 'react';
import { Route } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';

const InterviewStartPage = React.lazy(
  () => import('../pages/InterviewStartPage'),
);
const InterviewSessionPage = React.lazy(
  () => import('../pages/InterviewSessionPage'),
);
const OfflineImportPage = React.lazy(
  () => import('../pages/OfflineImportPage'),
);
const LabelPreviewPage = React.lazy(
  () => import('../pages/LabelPreviewPage'),
);
const LoginPage = React.lazy(() => import('../pages/LoginPage'));
const RegisterPage = React.lazy(() => import('../pages/RegisterPage'));
const AdminUserPage = React.lazy(() => import('../pages/AdminUserPage'));

export const interviewRoutes = (
  <>
    {/* Public routes */}
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />

    {/* Protected routes */}
    <Route
      path="/interview/start"
      element={
        <ProtectedRoute>
          <InterviewStartPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/interview/session/:projectId"
      element={
        <ProtectedRoute>
          <InterviewSessionPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/interview/import/:projectId"
      element={
        <ProtectedRoute>
          <OfflineImportPage projectId="" />
        </ProtectedRoute>
      }
    />
    <Route
      path="/interview/labels/:projectId"
      element={
        <ProtectedRoute>
          <LabelPreviewPage projectId="" />
        </ProtectedRoute>
      }
    />

    {/* Admin-only route */}
    <Route
      path="/admin/users"
      element={
        <ProtectedRoute requireAdmin>
          <AdminUserPage />
        </ProtectedRoute>
      }
    />
  </>
);

export const interviewMenuItem = {
  key: 'interview',
  icon: 'MessageOutlined',
  label: '客户智能访谈',
  path: '/interview/start',
};
