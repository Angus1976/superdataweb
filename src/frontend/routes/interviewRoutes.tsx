/**
 * Interview module route definitions.
 *
 * Add these routes to the main React Router configuration:
 *   import { interviewRoutes } from './routes/interviewRoutes';
 *   // inside <Routes>: {interviewRoutes}
 */

import React from 'react';
import { Route } from 'react-router-dom';

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

export const interviewRoutes = (
  <>
    <Route path="/interview/start" element={<InterviewStartPage />} />
    <Route
      path="/interview/session/:projectId"
      element={<InterviewSessionPage />}
    />
    <Route
      path="/interview/import/:projectId"
      element={<OfflineImportPage projectId="" />}
    />
    <Route
      path="/interview/labels/:projectId"
      element={<LabelPreviewPage projectId="" />}
    />
  </>
);

/**
 * Navigation menu item for the interview module.
 * Import and spread into your existing Ant Design Menu items array.
 */
export const interviewMenuItem = {
  key: 'interview',
  icon: 'MessageOutlined', // use <MessageOutlined /> in JSX context
  label: '客户智能访谈',
  path: '/interview/start',
};
