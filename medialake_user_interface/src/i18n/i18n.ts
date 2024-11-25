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
                        searchPlaceholder: 'Search or use key:value...'
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
