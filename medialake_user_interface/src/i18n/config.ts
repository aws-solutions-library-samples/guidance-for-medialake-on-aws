import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

i18n
    .use(LanguageDetector)
    .use(initReactI18next)
    .init({
        fallbackLng: 'en',
        debug: process.env.NODE_ENV === 'development',
        interpolation: {
            escapeValue: false,
        },
        resources: {
            en: {
                translation: {
                    // Common
                    'common.close': 'Close',
                    'common.cancel': 'Cancel',
                    'common.save': 'Save',
                    'common.delete': 'Delete',
                    'common.edit': 'Edit',
                    'common.loading': 'Loading...',
                    'common.error': 'Error',
                    'common.success': 'Success',
                    'common.refresh': 'Refresh',
                    'common.previous': 'Previous',
                    'common.next': 'Next',
                    'common.show': 'Show',
                    'common.all': 'All',
                    'common.status': 'Status',
                    'common.actions': 'Actions',
                    'common.rename': 'Rename',
                    'common.root': 'Root',
                    'common.folder': 'Folder',
                    'common.loadMore': 'Load More',
                    'common.comingSoon': 'Coming Soon',

                    // Modal messages
                    'modal.confirmDelete': 'Are you sure you want to delete this item?',
                    'modal.confirmAction': 'Are you sure you want to perform this action?',
                    'modal.error': 'An error occurred',
                    'modal.success': 'Operation completed successfully',

                    // Executions Page
                    'executions.title': 'Pipeline Executions',
                    'executions.description': 'Monitor and manage your pipeline executions',
                    'executions.columns.pipelineName': 'Pipeline Name',
                    'executions.columns.status': 'Status',
                    'executions.columns.startTime': 'Start Time',
                    'executions.columns.duration': 'Duration',
                    'executions.columns.actions': 'Actions',

                    // Status options
                    'executions.status.succeeded': 'Succeeded',
                    'executions.status.failed': 'Failed',
                    'executions.status.running': 'Running',
                    'executions.status.timedOut': 'Timed Out',
                    'executions.status.aborted': 'Aborted',

                    // Actions
                    'executions.actions.retryFromCurrent': 'Retry from current position',
                    'executions.actions.retryFromStart': 'Retry from start',
                    'executions.actions.viewDetails': 'View Details',

                    // Pagination
                    'executions.pagination.page': 'Page {{page}} of {{total}}',
                    'executions.pagination.showEntries': 'Show {{count}}',

                    // Sidebar Menu
                    'sidebar.menu.home': 'Home',
                    'sidebar.menu.assets': 'Assets',
                    'sidebar.menu.metadata': 'Metadata',
                    'sidebar.menu.pipelines': 'Pipelines',
                    'sidebar.menu.pipelineExecutions': 'Pipeline Executions',
                    'sidebar.menu.reviewQueue': 'Review Queue',
                    'sidebar.menu.tags': 'Tags',
                    'sidebar.menu.settings': 'Settings',

                    // Settings Submenu
                    'sidebar.submenu.integrations': 'Integrations',
                    'sidebar.submenu.connectors': 'Connectors',
                    'sidebar.submenu.userManagement': 'User Management',
                    'sidebar.submenu.roles': 'Roles',
                    'sidebar.submenu.system': 'System',

                    // S3 Explorer
                    's3Explorer.filter.label': 'Filter by name',
                    's3Explorer.error.loading': 'Error loading S3 objects: {{message}}',
                    's3Explorer.file.info': 'Size: {{size}} • Storage Class: {{storageClass}} • Modified: {{modified}}',
                    's3Explorer.menu.rename': 'Rename',
                    's3Explorer.menu.delete': 'Delete',

                    // Assets Page
                    'assets.title': 'Assets',
                    'assets.connectedStorage': 'Connected Storage',

                    // Metadata Page
                    'metadata.title': 'Coming Soon',
                    'metadata.description': "We're working to bring you metadata management capabilities. Stay tuned!"
                },
            },
        },
    });

export default i18n;
