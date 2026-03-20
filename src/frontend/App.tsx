import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import { AuthProvider } from './contexts/AuthContext';
import { interviewRoutes } from './routes/interviewRoutes';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense
          fallback={
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
              <Spin size="large" />
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<Navigate to="/login" replace />} />
            {interviewRoutes}
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;