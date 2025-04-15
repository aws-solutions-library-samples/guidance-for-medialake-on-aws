export default {
    languages: {
        english: 'Englisch',
        german: 'Deutsch',
        portuguese: 'Portugiesisch',
        french: 'Französisch',
        chinese: 'Chinesisch',
        hindi: 'Hindi',
        arabic: 'Arabisch',
        hebrew: 'Hebräisch'
    },
    assetsPage: {
        title: 'Assets',
        connectors: 'Connectors',
        selectConnector: 'Wählen Sie einen Connector'
      },
    assetExplorer: {
        noConnectorSelected: 'Wählen Sie einen Connector, um Assets anzuzeigen',
        noAssetsFound: 'Keine Assets für diesen Connector gefunden',
        noIndexedAssets: 'Keine indizierten Assets für diesen Connector mit Bucket "{{bucketName}}" gefunden.',
        loadingAssets: 'Assets werden geladen...',
        menu: {
          rename: 'Umbenennen',
          share: 'Teilen',
          download: 'Herunterladen'
        },
        deleteDialog: {
          title: 'Löschen bestätigen',
          description: 'Sind Sie sicher, dass Sie dieses Asset löschen möchten? Diese Aktion kann nicht rückgängig gemacht werden.',
          cancel: 'Abbrechen',
          confirm: 'Löschen'
        }
      },
    sidebar: {
      menu: {
        home: 'Startseite',
        assets: 'Assets',
        pipelines: 'Pipelines',
        pipelineExecutions: 'Pipeline-Ausführungen',
        settings: 'Einstellungen'
      },
      submenu: {
        system: 'Systemeinstellungen',
        connectors: 'Konnektoren',
        userManagement: 'Benutzerverwaltung',
        roles: 'Rollen',
        integrations: 'Integrationen',
        environments: 'Umgebungen'
      }
    },
    profile: {
      title: 'Profil',
      description: 'Verwalten Sie Ihre Kontoeinstellungen und Präferenzen',
      changePhoto: 'Foto ändern',
      jobTitle: 'Berufsbezeichnung',
      organization: 'Organisation',
      preferences: 'Präferenzen',
      timezone: 'Zeitzone',
      emailNotifications: 'E-Mail-Benachrichtigungen',
      pushNotifications: 'Push-Benachrichtigungen',
      changePassword: 'Passwort ändern',
      twoFactorAuth: 'Zwei-Faktor-Authentifizierung',
      appearance: 'Erscheinungsbild'
    },
    app: {
      loading: 'Lädt...',
      errors: {
        loadingConfig: 'Fehler beim Laden der AWS-Konfiguration:',
        loadingUserAttributes: 'Fehler beim Laden der Benutzerattribute:',
        signingOut: 'Fehler beim Abmelden:'
      },
      navigation: {
        preventedDuplicate: 'Doppelte Navigation verhindert zu',
        navigating: 'Navigation von'
      },
      branding: {
        name: 'MediaLake'
      }
    },
    search: {
      semantic: 'Semantische Suche',
      filters: {
        dateRange: 'Datumsbereich',
        contentType: 'Inhaltstyp',
        storageLocation: 'Speicherort',
        comingSoon: 'Weitere Filter folgen in Kürze...'
      }
    },
    admin: {
      metrics: {
        storageUsage: 'Speichernutzung',
        apiUsage: 'API-Nutzung',
        activeUsers: 'Aktive Benutzer',
        systemLoad: 'Systemauslastung'
      },
      errors: {
        userDeletionNotImplemented: 'Benutzerlöschung ist noch nicht implementiert.',
        userCreationNotImplemented: 'Benutzererstellung ist noch nicht implementiert.',
        userEditingNotImplemented: 'Benutzerbearbeitung ist noch nicht implementiert.',
        analyticsExportNotImplemented: 'Analytics-Export ist noch nicht implementiert.',
        systemResetNotImplemented: 'System-Reset ist noch nicht implementiert.'
      },
      columns: {
        lastActive: 'Zuletzt aktiv'
      },
      buttons: {
        exportAnalytics: 'Analytics exportieren',
        resetSystem: 'System zurücksetzen'
      }
    },
    integrations: {
      title: 'Integrationen',
      selectProvider: 'Integration auswählen',
      selectIntegration: 'Integration auswählen',
      configureIntegration: 'Integration konfigurieren',
      description: 'Verwalten Sie Ihre Integrationen und Verbindungen',
      addIntegration: 'Integration hinzufügen',
      form: {
        search: {
          placeholder: 'Integrationen suchen'
        },
        title: 'Integration hinzufügen',
        fields: {
          nodeId: {
            label: 'Integration',
            tooltip: 'Wählen Sie einen Integrationsanbieter aus',
            errors: {
              required: 'Integrationsauswahl ist erforderlich'
            }
          },
          description: {
            label: 'Beschreibung',
            tooltip: 'Geben Sie eine Beschreibung für diese Integration ein',
            helper: 'Kurze Beschreibung dieser Integration',
            errors: {
              required: 'Beschreibung ist erforderlich'
            }
          },
          environmentId: {
            label: 'Umgebung',
            tooltip: 'Wählen Sie die Umgebung für diese Integration aus',
            errors: {
              required: 'Umgebungsauswahl ist erforderlich'
            }
          },
          enabled: {
            label: 'Aktiviert',
            tooltip: 'Aktivieren oder deaktivieren Sie diese Integration',
            errors: {
              required: 'Aktivierung ist erforderlich'
            }
          },
          auth: {
            type: {
              label: 'Authentifizierungstyp',
              tooltip: 'Wählen Sie die Authentifizierungsmethode aus',
              options: {
                awsIam: 'AWS IAM',
                apiKey: 'API-Schlüssel'
              },
              errors: {
                required: 'Authentifizierungstyp ist erforderlich'
              }
            },
            credentials: {
              apiKey: {
                label: 'API-Schlüssel',
                tooltip: 'Geben Sie Ihren API-Schlüssel ein',
                helper: 'API-Schlüssel für die Authentifizierung mit dem Dienst',
                errors: {
                  required: 'API-Schlüssel ist erforderlich'
                }
              },
              iamRole: {
                label: 'IAM-Rolle',
                tooltip: 'Geben Sie die ARN der IAM-Rolle ein',
                errors: {
                  required: 'IAM-Rolle ist erforderlich'
                }
              }
            }
          }
        },
        errors: {
          required: 'Dieses Feld ist erforderlich',
          nodeId: {
            unrecognized_keys: 'Ungültige Integrationsauswahl'
          }
        }
      }
    },
    pipelines: {
      title: 'Pipelines',
      description: 'Verwalten Sie Ihre Medien- und Metadaten-Pipelines',
      searchPlaceholder: 'Pipelines suchen...',
      actions: {
        create: 'Neue Pipeline hinzufügen',
        import: 'Pipeline importieren'
      }
    },
    executions: {
      title: 'Pipeline-Ausführungen',
      description: 'Überwachen und verwalten Sie Ihre Pipeline-Ausführungen',
      searchPlaceholder: 'Pipeline-Ausführungen suchen...',
      columns: {
        pipelineName: 'Pipeline-Name',
        status: 'Status',
        startTime: 'Startzeit',
        endTime: 'Endzeit',
        duration: 'Dauer',
        actions: 'Aktionen'
      }
    },
    users: {
      title: 'Benutzerverwaltung',
      description: 'Verwalten Sie Systembenutzer und deren Zugriffe',
      actions: {
        addUser: 'Benutzer hinzufügen'
      },
      form: {
        title: {
          add: 'Benutzer hinzufügen'
        },
        fields: {
          given_name: {
            label: 'Vorname',
            tooltip: 'Geben Sie den Vornamen des Benutzers ein',
            helper: ''
          },
          family_name: {
            label: 'Nachname',
            tooltip: 'Geben Sie den Nachnamen des Benutzers ein',
            helper: ''
          },
          email: {
            label: 'E-Mail',
            tooltip: 'Geben Sie die E-Mail-Adresse des Benutzers ein',
            helper: ''
          },
          roles: {
            label: 'Rollen',
            tooltip: 'Wählen Sie die Rollen für den Benutzer aus',
            options: {
              Admin: 'Admin',
              Editor: 'Editor',
              Viewer: 'Viewer'
            }
          },
          email_verified: {
            label: 'E-Mail bestätigt',
            tooltip: 'Geben Sie an, ob die E-Mail des Benutzers bestätigt wurde'
          },
          enabled: {
            label: 'Aktiviert',
            tooltip: 'Benutzer aktivieren oder deaktivieren'
          }
        }
      },
      roles: {
        admin: 'Admin',
        editor: 'Editor',
        viewer: 'Viewer'
      }
    },
    roles: {
      title: 'Rollenverwaltung',
      description: 'Verwalten Sie Systemrollen und deren Berechtigungen',
      actions: {
        addRole: 'Rolle hinzufügen'
      }
    },
    settings: {
      environments: {
        title: 'Umgebungen',
        description: 'Verwalten Sie Systemumgebungen und deren Konfigurationen',
        addButton: 'Umgebung hinzufügen',
        searchPlaceholder: 'Umgebungen suchen',
        createTitle: 'Umgebung erstellen',
        form: {
          name: 'Umgebungsname',
          region: 'Region',
          status: {
            name: 'Status',
            active: 'Aktiv',
            disabled: 'Deaktiviert'
          },
          costCenter: 'Kostenstelle',
          team: 'Team'
        }
      },
      systemSettings: {
        title: 'Systemeinstellungen',
        tabs: {
          search: 'Suche',
          notifications: 'Benachrichtigungen',
          security: 'Sicherheit',
          performance: 'Leistung'
        },
        search: {
          title: 'Suchkonfiguration',
          description: 'Konfigurieren Sie den Suchanbieter für erweiterte Suchfunktionen über Ihre Medieninhalte.',
          provider: 'Suchanbieter:',
          configureProvider: 'Suchanbieter konfigurieren',
          editProvider: 'Anbieter bearbeiten',
          resetProvider: 'Anbieter zurücksetzen',
          providerDetails: 'Anbieterdetails',
          providerName: 'Anbietername',
          apiKey: 'API-Schlüssel',
          endpoint: 'Endpoint-URL (optional)',
          enabled: 'Suche aktiviert',
          noProvider: 'Kein Suchanbieter konfiguriert.',
          configurePrompt: 'Konfigurieren Sie Twelve Labs, um Suchfunktionen zu aktivieren.'
        },
        notifications: {
          title: 'Benachrichtigungseinstellungen',
          comingSoon: 'Benachrichtigungseinstellungen folgen in Kürze.'
        },
        security: {
          title: 'Sicherheitseinstellungen',
          comingSoon: 'Sicherheitseinstellungen folgen in Kürze.'
        },
        performance: {
          title: 'Leistungseinstellungen',
          comingSoon: 'Leistungseinstellungen folgen in Kürze.'
        }
      }
    },
    common: {
      select: 'Auswählen',
      back: 'Zurück',
      search: 'Suchen',
      profile: 'Profil',
      logout: 'Abmelden',
      theme: 'Thema',
      close: 'Schließen',
      refresh: 'Aktualisieren',
      cancel: 'Abbrechen',
      save: 'Speichern',
      loading: 'Lädt...',
      loadMore: 'Mehr laden',
      tableDensity: 'Tabellendichte',
      moreInfo: 'Mehr Informationen',
      error: 'Fehler',
      language: 'Sprache',
      delete: 'Löschen',
      create: 'Erstellen',
      actions: {
        add: 'Hinzufügen'
      },
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
      status: {
        active: 'Aktiv',
        inactive: 'Inaktiv'
      }
    },
    translation: {
      common: {
        actions: {
          add: 'Hinzufügen',
          edit: 'Bearbeiten',
          delete: 'Löschen',
          activate: 'Aktivieren',
          deactivate: 'Deaktivieren',
          create: 'Erstellen'
        },
        tableDensity: 'Tabellendichte',
        theme: 'Thema',
        back: 'Zurück',
        loading: 'Lädt...',
        error: 'Etwas ist schief gelaufen',
        save: 'Speichern',
        cancel: 'Abbrechen',
        delete: 'Löschen',
        edit: 'Bearbeiten',
        search: 'Suchen',
        profile: 'Profil',
        filterColumn: 'Filter',
        searchValue: 'Suche',
        logout: 'Abmelden',
        language: 'Sprache',
        alerts: 'Warnungen',
        warnings: 'Warnungen',
        notifications: 'Benachrichtigungen',
        searchPlaceholder: 'Suchen oder Schlüssel:Wert verwenden...',
        close: 'Schließen',
        success: 'Erfolg',
        refresh: 'Aktualisieren',
        previous: 'Vorherige',
        next: 'Nächste',
        show: 'Anzeigen',
        all: 'Alle',
        status: {
          active: 'Aktiv',
          inactive: 'Inaktiv'
        },
        rename: 'Umbenennen',
        root: 'Root',
        folder: 'Ordner',
        loadMore: 'Mehr laden',
        darkMode: 'Dunkelmodus',
        lightMode: 'Hellmodus',
        filter: 'Filter',
        textFilter: 'Textfilter',
        selectFilter: 'Filter auswählen',
        clearFilter: 'Filter löschen',
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
        noGroups: 'Keine Gruppen',
        select: 'Auswählen',
        moreInfo: 'Mehr Informationen'
      },
      users: {
        title: 'Benutzerverwaltung',
        search: 'Benutzer suchen',
        description: 'Verwalten Sie Systembenutzer und deren Zugriffe',
        form: {
          fields: {
            given_name: {
              label: 'Vorname',
              tooltip: 'Geben Sie den Vornamen des Benutzers ein',
              errors: {
                required: 'Vorname ist erforderlich'
              }
            },
            family_name: {
              label: 'Nachname',
              tooltip: 'Geben Sie den Nachnamen des Benutzers ein',
              errors: {
                required: 'Nachname ist erforderlich'
              }
            },
            email: {
              label: 'E-Mail',
              tooltip: 'Geben Sie die E-Mail-Adresse des Benutzers ein',
              errors: {
                required: 'E-Mail ist erforderlich',
                invalid: 'Ungültige E-Mail-Adresse'
              }
            },
            enabled: {
              label: 'Aktiviert',
              tooltip: 'Benutzer aktivieren oder deaktivieren',
              errors: {
                required: 'Aktivierung ist erforderlich'
              }
            },
            roles: {
              label: 'Rollen',
              tooltip: 'Wählen Sie die Rollen für den Benutzer aus',
              errors: {
                required: 'Rollen sind erforderlich'
              }
            },
            email_verified: {
              label: 'E-Mail bestätigt',
              tooltip: 'Geben Sie an, ob die E-Mail des Benutzers bestätigt wurde',
              errors: {
                required: 'E-Mail-Bestätigung ist erforderlich'
              }
            }
          }
        }
      },
      roles: {
        title: 'Rollenverwaltung',
        description: 'Verwalten Sie Systemrollen und deren Berechtigungen',
        admin: 'Admin',
        editor: 'Editor',
        viewer: 'Viewer',
        actions: {
          addRole: 'Rolle hinzufügen'
        }
      },
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
        connectedStorage: 'Verbundener Speicher',
        sharing: 'Teilen',
        comingSoon: 'Demnächst'
      },
      notifications: {
        'Pipeline Complete': 'Pipeline abgeschlossen',
        'Asset processing pipeline completed successfully': 'Asset-Verarbeitungspipeline erfolgreich abgeschlossen',
        'Storage Warning': 'Speicherwarnung',
        'Storage capacity reaching 80%': 'Speicherkapazität erreicht 80%',
        'Pipeline Failed': 'Pipeline fehlgeschlagen',
        'Video processing pipeline failed': 'Videoverarbeitungspipeline fehlgeschlagen'
      },
      modal: {
        confirmDelete: 'Sind Sie sicher, dass Sie dieses Element löschen möchten?',
        confirmAction: 'Sind Sie sicher, dass Sie diese Aktion durchführen möchten?',
        error: 'Ein Fehler ist aufgetreten',
        success: 'Vorgang erfolgreich abgeschlossen'
      },
      executions: {
        title: 'Pipeline-Ausführungen',
        description: 'Überwachen und verwalten Sie Ihre Pipeline-Ausführungen',
        searchPlaceholder: 'Pipeline-Ausführungen suchen...',
        columns: {
          pipelineName: 'Pipeline-Name',
          status: 'Status',
          startTime: 'Startzeit',
          endTime: 'Endzeit',
          duration: 'Dauer',
          actions: 'Aktionen'
        },
        status: {
          succeeded: 'Erfolgreich',
          failed: 'Fehlgeschlagen',
          running: 'Laufend',
          timedOut: 'Zeitüberschreitung',
          aborted: 'Abgebrochen'
        },
        actions: {
          retryFromCurrent: 'Ab aktueller Position wiederholen',
          retryFromStart: 'Von Anfang an wiederholen',
          viewDetails: 'Details anzeigen'
        },
        pagination: {
          page: 'Seite {{page}} von {{total}}',
          showEntries: 'Zeige {{count}}'
        }
      },
      s3Explorer: {
        filter: {
          label: 'Nach Name filtern'
        },
        error: {
          loading: 'Fehler beim Laden der S3-Objekte: {{message}}'
        },
        file: {
          info: 'Größe: {{size}} • Speicherklasse: {{storageClass}} • Geändert: {{modified}}'
        },
        menu: {
          rename: 'Umbenennen',
          delete: 'Löschen'
        }
      },
      assets: {
        title: 'Assets',
        connectedStorage: 'Verbundener Speicher'
      },
      metadata: {
        title: 'Kommt bald',
        description: "Wir arbeiten daran, Ihnen Funktionen zur Metadatenverwaltung bereitzustellen. Bleiben Sie dran!"
      },
      pipelines: {
        title: 'Pipelines',
        description: 'Verwalten Sie Ihre Medien- und Metadaten-Pipelines',
        searchPlaceholder: 'Pipelines suchen...',
        actions: {
          create: 'Neue Pipeline hinzufügen',
          deploy: 'Image-Pipeline bereitstellen',
          addNew: 'Neue Pipeline hinzufügen',
          viewAll: 'Alle Pipelines anzeigen'
        },
        search: 'Pipelines suchen',
        deploy: 'Image-Pipeline bereitstellen',
        addNew: 'Neue Pipeline hinzufügen',
        columns: {
          name: 'Name',
          creationDate: 'Erstellungsdatum',
          system: 'System',
          type: 'Typ',
          actions: 'Aktionen'
        },
        editor: {
          title: 'Pipeline-Editor',
          save: 'Pipeline speichern',
          validate: 'Pipeline validieren',
          sidebar: {
            title: 'Knoten',
            dragNodes: 'Ziehen Sie Knoten auf die Arbeitsfläche',
            loading: 'Knoten werden geladen...',
            error: 'Fehler beim Laden der Knoten'
          },
          node: {
            configure: 'Konfiguriere {{type}}',
            delete: 'Knoten löschen',
            edit: 'Knoten bearbeiten'
          },
          edge: {
            title: 'Kantenbeschriftung bearbeiten',
            label: 'Kantenbeschriftung',
            delete: 'Verbindung löschen'
          },
          modals: {
            error: {
              title: 'Fehler',
              incompatibleNodes: 'Der Ausgang des vorherigen Knotens ist nicht kompatibel mit dem Eingang des Zielknotens.',
              validation: 'Pipeline-Validierung fehlgeschlagen'
            },
            delete: {
              title: 'Pipeline löschen',
              message: 'Sind Sie sicher, dass Sie diese Pipeline löschen möchten? Diese Aktion kann nicht rückgängig gemacht werden.',
              confirm: 'Geben Sie den Namen der Pipeline zur Bestätigung ein:'
            }
          },
          controls: {
            undo: 'Rückgängig',
            redo: 'Wiederholen',
            zoomIn: 'Hineinzoomen',
            zoomOut: 'Herauszoomen',
            fitView: 'Ansicht anpassen',
            lockView: 'Ansicht sperren'
          },
          notifications: {
            saved: 'Pipeline erfolgreich gespeichert',
            validated: 'Pipeline-Validierung erfolgreich',
            error: {
              save: 'Fehler beim Speichern der Pipeline',
              validation: 'Pipeline-Validierung fehlgeschlagen',
              incompatibleNodes: 'Inkompatible Knotenverbindung'
            }
          }
        },
        integrations: {
          title: 'Integrationen',
          description: 'Verwalten Sie Ihre Integrationen und Verbindungen',
          addIntegration: 'Integration hinzufügen',
          selectIntegration: 'Integration auswählen',
          selectProvider: 'Provider auswählen',
          configureIntegration: 'Integration konfigurieren',
          form: {
            title: 'Integration hinzufügen',
            fields: {
              nodeId: {
                label: 'Integration',
                tooltip: 'Wählen Sie einen Integrationsanbieter aus',
                errors: {
                  required: 'Integrationsauswahl ist erforderlich'
                }
              },
              description: {
                label: 'Beschreibung',
                tooltip: 'Geben Sie eine Beschreibung für diese Integration ein',
                errors: {
                  required: 'Beschreibung ist erforderlich'
                }
              },
              environmentId: {
                label: 'Umgebung',
                tooltip: 'Wählen Sie die Umgebung für diese Integration aus',
                errors: {
                  required: 'Umgebungsauswahl ist erforderlich'
                }
              },
              enabled: {
                label: 'Aktiviert',
                tooltip: 'Aktivieren oder deaktivieren Sie diese Integration',
                errors: {
                  required: 'Aktivierung ist erforderlich'
                }
              },
              auth: {
                type: {
                  label: 'Authentifizierungstyp',
                  tooltip: 'Wählen Sie die Authentifizierungsmethode aus',
                  options: {
                    awsIam: 'AWS IAM',
                    apiKey: 'API-Schlüssel'
                  },
                  errors: {
                    required: 'Authentifizierungstyp ist erforderlich'
                  }
                },
                credentials: {
                  apiKey: {
                    label: 'API-Schlüssel',
                    tooltip: 'Geben Sie Ihren API-Schlüssel ein',
                    errors: {
                      required: 'API-Schlüssel ist erforderlich'
                    }
                  },
                  iamRole: {
                    label: 'IAM-Rolle',
                    tooltip: 'Geben Sie die ARN der IAM-Rolle ein',
                    errors: {
                      required: 'IAM-Rolle ist erforderlich'
                    }
                  }
                }
              }
            },
            search: {
              placeholder: 'Integrationen suchen'
            },
            errors: {
              required: 'Dieses Feld ist erforderlich',
              nodeId: {
                unrecognized_keys: 'Ungültige Integrationsauswahl'
              }
            }
          },
          columns: {
            nodeName: 'Node-Name',
            environment: 'Umgebung',
            createdDate: 'Erstellungsdatum',
            modifiedDate: 'Änderungsdatum',
            actions: 'Aktionen'
          },
          settings: {
            environments: {
              title: 'Umgebungen'
            }
          }
        }
      }
    }
  }
  