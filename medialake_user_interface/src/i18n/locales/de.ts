export default {
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
            searchPlaceholder: 'Suchen oder Schlüssel:Wert verwenden...',
            darkMode: 'Dunkelmodus',
            lightMode: 'Hellmodus',
            noGroups: 'Keine Gruppen',
            create: 'Erstellen'
        },
        users: {
            title: 'Benutzerverwaltung',
            description: 'Verwalten Sie Systembenutzer und deren Zugriff',
            columns: {
                username: 'Benutzername',
                firstName: 'Vorname',
                lastName: 'Nachname',
                email: 'E-Mail',
                status: 'Status',
                groups: 'Gruppen',
                created: 'Erstellt',
                modified: 'Geändert',
                actions: 'Aktionen'
            },
            actions: {
                addUser: 'Benutzer hinzufügen',
                edit: 'Benutzer bearbeiten',
                delete: 'Benutzer löschen',
                activate: 'Benutzer aktivieren',
                deactivate: 'Benutzer deaktivieren'
            },
            status: {
                active: 'Aktiv',
                inactive: 'Inaktiv'
            },
            errors: {
                loadFailed: 'Fehler beim Laden der Benutzer',
                saveFailed: 'Fehler beim Speichern des Benutzers',
                deleteFailed: 'Fehler beim Löschen des Benutzers'
            }
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
        },
        integrations: {
            title: 'Integrationen',
            description: 'Verwalten Sie Ihre Integrationen und Verbindungen',
            addIntegration: 'Integration hinzufügen',
            selectIntegration: 'Integration auswählen',
            configureIntegration: 'Integration konfigurieren',
            columns: {
                nodeName: 'Node-Name',
                environment: 'Umgebung',
                createdDate: 'Erstellungsdatum',
                modifiedDate: 'Änderungsdatum',
                actions: 'Aktionen'
            },
            form: {
                environment: 'Umgebung',
                description: 'Beschreibung',
                selectNode: 'Wählen Sie eine Integration zur Konfiguration aus'
            },
            actions: {
                edit: 'Integration bearbeiten',
                delete: 'Integration löschen'
            },
            search: 'Integrationen suchen...',
            status: {
                creating: 'Integration wird erstellt...',
                created: 'Integration erstellt',
                createFailed: 'Integration konnte nicht erstellt werden',
                deleting: 'Integration wird gelöscht...',
                deleted: 'Integration gelöscht',
                deleteFailed: 'Integration konnte nicht gelöscht werden'
            }
        },
        settings: {
            environments: {
                title: 'Umgebungen',
                description: 'Verwalten Sie Systemumgebungen und deren Konfigurationen',
                search: 'Umgebungen suchen',
                addButton: 'Umgebung hinzufügen',
                createTitle: 'Umgebung erstellen',
                editTitle: 'Umgebung bearbeiten',
                deleteSuccess: 'Umgebung erfolgreich gelöscht',
                deleteError: 'Fehler beim Löschen der Umgebung',
                createSuccess: 'Umgebung erfolgreich erstellt',
                updateSuccess: 'Umgebung erfolgreich aktualisiert',
                submitError: 'Fehler beim Speichern der Umgebung',
                columns: {
                    name: 'Name',
                    region: 'Region',
                    status: 'Status',
                    team: 'Team',
                    costCenter: 'Kostenstelle',
                    createdAt: 'Erstellt am',
                    updatedAt: 'Aktualisiert am',
                    actions: 'Aktionen'
                },
                status: {
                    active: 'Aktiv',
                    disabled: 'Deaktiviert'
                },
                actions: {
                    edit: 'Umgebung bearbeiten',
                    delete: 'Umgebung löschen'
                },
                form: {
                    name: 'Umgebungsname',
                    region: 'Region',
                    costCenter: 'Kostenstelle',
                    team: 'Team'
                }
            }
        }
    }
}
