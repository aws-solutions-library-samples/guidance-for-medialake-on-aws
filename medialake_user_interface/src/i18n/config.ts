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

                    // Modal messages
                    'modal.confirmDelete': 'Are you sure you want to delete this item?',
                    'modal.confirmAction': 'Are you sure you want to perform this action?',
                    'modal.error': 'An error occurred',
                    'modal.success': 'Operation completed successfully',
                },
            },
        },
    });

export default i18n;
