import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

i18n
    // detect user language
    .use(LanguageDetector)
    // pass the i18n instance to react-i18next
    .use(initReactI18next)
    // init i18next
    .init({
        debug: true,
        fallbackLng: 'en',
        interpolation: {
            escapeValue: false, // not needed for react as it escapes by default
        },
        resources: {
            en: {
                translation: {
                    common: {
                        loading: 'Loading...',
                        error: 'Something went wrong',
                        save: 'Save',
                        cancel: 'Cancel',
                        delete: 'Delete',
                        edit: 'Edit',
                        search: 'Search',
                        profile: 'Profile',
                        logout: 'Logout',
                        language: 'Language',
                        alerts: 'Alerts',
                        warnings: 'Warnings',
                        notifications: 'Notifications',
                        searchPlaceholder: 'Search or use key:value...',
                        close: 'Close',
                        success: 'Success',
                        refresh: 'Refresh',
                        previous: 'Previous',
                        next: 'Next',
                        show: 'Show',
                        all: 'All',
                        status: 'Status',
                        actions: 'Actions',
                        rename: 'Rename',
                        root: 'Root',
                        folder: 'Folder',
                        loadMore: 'Load More'
                    },
                    navigation: {
                        home: 'Home',
                        collections: 'Collections',
                        settings: 'Settings'
                    },
                    home: {
                        welcome: 'Welcome to MediaLake',
                        description: 'Manage and organize your media files efficiently',
                        statistics: 'Statistics',
                        collections: 'Collections',
                        sharedCollections: 'Shared Collections',
                        favorites: 'Favorites',
                        smartFolders: 'Smart Folders',
                        connectedStorage: 'Connected Storage'
                    },
                    notifications: {
                        'Pipeline Complete': 'Pipeline Complete',
                        'Asset processing pipeline completed successfully': 'Asset processing pipeline completed successfully',
                        'Storage Warning': 'Storage Warning',
                        'Storage capacity reaching 80%': 'Storage capacity reaching 80%',
                        'Pipeline Failed': 'Pipeline Failed',
                        'Video processing pipeline failed': 'Video processing pipeline failed'
                    },
                    modal: {
                        confirmDelete: 'Are you sure you want to delete this item?',
                        confirmAction: 'Are you sure you want to perform this action?',
                        error: 'An error occurred',
                        success: 'Operation completed successfully'
                    },
                    executions: {
                        title: 'Pipeline Executions',
                        description: 'Monitor and manage your pipeline executions',
                        columns: {
                            pipelineName: 'Pipeline Name',
                            status: 'Status',
                            startTime: 'Start Time',
                            duration: 'Duration',
                            actions: 'Actions'
                        },
                        status: {
                            succeeded: 'Succeeded',
                            failed: 'Failed',
                            running: 'Running',
                            timedOut: 'Timed Out',
                            aborted: 'Aborted'
                        },
                        actions: {
                            retryFromCurrent: 'Retry from current position',
                            retryFromStart: 'Retry from start',
                            viewDetails: 'View Details'
                        },
                        pagination: {
                            page: 'Page {{page}} of {{total}}',
                            showEntries: 'Show {{count}}'
                        }
                    },
                    sidebar: {
                        menu: {
                            home: 'Home',
                            assets: 'Assets',
                            metadata: 'Metadata',
                            pipelines: 'Pipelines',
                            pipelineExecutions: 'Pipeline Executions',
                            reviewQueue: 'Review Queue',
                            tags: 'Tags',
                            settings: 'Settings'
                        },
                        submenu: {
                            integrations: 'Integrations',
                            connectors: 'Connectors',
                            userManagement: 'User Management',
                            roles: 'Roles',
                            system: 'System'
                        }
                    },
                    s3Explorer: {
                        filter: {
                            label: 'Filter by name'
                        },
                        error: {
                            loading: 'Error loading S3 objects: {{message}}'
                        },
                        file: {
                            info: 'Size: {{size}} • Storage Class: {{storageClass}} • Modified: {{modified}}'
                        },
                        menu: {
                            rename: 'Rename',
                            delete: 'Delete'
                        }
                    },
                    assets: {
                        title: 'Assets',
                        connectedStorage: 'Connected Storage'
                    },
                    metadata: {
                        title: 'Coming Soon',
                        description: "We're working to bring you metadata management capabilities. Stay tuned!"
                    }
                }
            },
            de: {
                translation: {
                    common: {
                        loading: 'Wird geladen...',
                        error: 'Etwas ist schief gelaufen',
                        save: 'Speichern',
                        cancel: 'Abbrechen',
                        delete: 'Löschen',
                        edit: 'Bearbeiten',
                        search: 'Suchen',
                        profile: 'Profil',
                        logout: 'Abmelden',
                        language: 'Sprache',
                        alerts: 'Warnungen',
                        warnings: 'Warnhinweise',
                        notifications: 'Benachrichtigungen',
                        searchPlaceholder: 'Suchen oder Schlüssel:Wert verwenden...'
                    },
                    navigation: {
                        home: 'Startseite',
                        collections: 'Sammlungen',
                        settings: 'Einstellungen'
                    },
                    home: {
                        welcome: 'Willkommen bei MediaLake',
                        description: 'Verwalten und organisieren Sie Ihre Mediendateien effizient',
                        statistics: 'Statistiken',
                        collections: 'Sammlungen',
                        sharedCollections: 'Geteilte Sammlungen',
                        favorites: 'Favoriten',
                        smartFolders: 'Intelligente Ordner',
                        connectedStorage: 'Verbundener Speicher'
                    },
                    notifications: {
                        'Pipeline Complete': 'Pipeline abgeschlossen',
                        'Asset processing pipeline completed successfully': 'Asset-Verarbeitungspipeline erfolgreich abgeschlossen',
                        'Storage Warning': 'Speicherwarnung',
                        'Storage capacity reaching 80%': 'Speicherkapazität erreicht 80%',
                        'Pipeline Failed': 'Pipeline fehlgeschlagen',
                        'Video processing pipeline failed': 'Videoverarbeitungspipeline fehlgeschlagen'
                    }
                }
            }
        }
    });

export default i18n;
