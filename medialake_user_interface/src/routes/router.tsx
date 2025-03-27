import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import AuthPage from '@/components/AuthPage';
import AppLayout from '@/components/AppLayout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import Home from '@/pages/Home';
import SearchPage from '@/pages/SearchPage';
import AssetsPage from '@/pages/AssetsPage';
import { ExecutionsPage } from '@/features/executions';
import { PipelinesPage, PipelineEditorPage } from '@/features/pipelines/pages';
import ImageDetailPage from '@/pages/ImageDetailPage';
import VideoDetailPage from '@/pages/VideoDetailPage';
import AudioDetailPage from '@/pages/AudioDetailPage';
import ConnectorsPage from '@/pages/settings/ConnectorsPage';
import ProfilePage from '@/pages/settings/ProfilePage';
import UserManagement from '@/pages/settings/UserManagement';
import RoleManagement from '@/pages/settings/RoleManagement';
import IntegrationsPage from '@/pages/settings/IntegrationsPage';
import EnvironmentsPage from '@/pages/settings/EnvironmentsPage';
import SystemSettingsPage from '@/pages/settings/SystemSettingsPage';

export const router = createBrowserRouter([
    {
        path: '/sign-in',
        element: <AuthPage />
    },
    {
        path: '/',
        element: (
            <ProtectedRoute>
                <AppLayout />
            </ProtectedRoute>
        ),
        children: [
            {
                index: true,
                element: <Home />
            },
            {
                path: 'search',
                element: <SearchPage />
            },
            {
                path: 'assets',
                element: <AssetsPage />
            },
            {
                path: 'executions',
                element: <ExecutionsPage />
            },
            {
                path: 'pipelines',
                element: <PipelinesPage />
            },
            {
                path: 'pipelines/new',
                element: <PipelineEditorPage />
            },
            {
                path: 'images/:id',
                element: <ImageDetailPage />
            },
            {
                path: 'videos/:id',
                element: <VideoDetailPage />
            },
            {
                path: 'audio/:id',
                element: <AudioDetailPage />
            },
            {
                path: 'settings/profile',
                element: <ProfilePage />
            },
            {
                path: 'settings/connectors',
                element: <ConnectorsPage />
            },
            {
                path: 'settings/users',
                element: <UserManagement />
            },
            {
                path: 'settings/roles',
                element: <RoleManagement />
            },
            {
                path: 'settings/integrations',
                element: <IntegrationsPage />
            },
            {
                path: 'settings/environments',
                element: <EnvironmentsPage />
            },
            {
                path: 'settings/pipelines',
                element: <PipelinesPage />
            },
            {
                path: 'settings/pipelines/new',
                element: <PipelineEditorPage />
            },
            {
                path: 'settings/pipelines/edit/:id',
                element: <PipelineEditorPage />
            },
            {
                path: 'settings/system',
                element: <SystemSettingsPage />
            },
            {
                path: 'settings',
                element: <Navigate to="settings/profile" replace />
            },
            {
                path: '*',
                element: <Navigate to="/" replace />
            }
        ]
    }
]);