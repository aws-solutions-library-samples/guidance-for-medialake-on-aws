import React from 'react';
import { Navigate, RouteObject } from 'react-router-dom';
import AssetsPage from './pages/AssetsPage';
import SearchPage from './pages/SearchPage';
import PipelinesPage from './pages/PipelinesPage';
import ExecutionsPage from './pages/ExecutionsPage';
import ReviewQueuePage from './pages/ReviewQueuePage';
import TagsPage from './pages/TagsPage';
import SettingsRouter from './pages/settings/SettingsRouter';
import IntegrationsPage from './pages/settings/IntegrationsPage';
import ConnectorsPage from './pages/settings/ConnectorsPage';
import SystemPage from './pages/settings/SystemPage';
import ProfilePage from './pages/settings/ProfilePage';

export const routes: RouteObject[] = [
    {
        path: '/',
        element: <AssetsPage />,
    },
    {
        path: '/search',
        element: <SearchPage />,
    },
    {
        path: '/pipelines',
        element: <PipelinesPage />,
    },
    {
        path: '/executions',
        element: <ExecutionsPage />,
    },
    {
        path: '/review-queue',
        element: <ReviewQueuePage />,
    },
    {
        path: '/tags',
        element: <TagsPage />,
    },
    {
        path: '/settings',
        children: [
            {
                path: 'integrations',
                element: <IntegrationsPage />,
            },
            {
                path: 'connectors',
                element: <ConnectorsPage />,
            },
            {
                path: 'system',
                element: <SystemPage />,
            },
            {
                path: 'profile',
                element: <ProfilePage />,
            },
            {
                path: '',
                element: <Navigate to="profile" replace />,
            },
        ],
    },
    {
        path: '*',
        element: <Navigate to="/" replace />,
    },
];

export default routes;
