export default {
  languages: {
    english: "Anglais",
    german: "Allemand",
    portuguese: "Portugais",
    french: "Français",
    chinese: "Chinois",
    hindi: "Hindi",
    arabic: "Arabe",
    hebrew: "Hébreu",
    japanese: "Japonais",
    korean: "Coréen",
    spanish: "Espagnol",
  },
  assetsPage: {
    title: "Actifs",
    connectors: "Connecteurs",
    selectConnector: "Sélectionnez un connecteur",
  },
  assetExplorer: {
    noConnectorSelected: "Sélectionnez un connecteur pour afficher les actifs",
    noAssetsFound: "Aucun actif trouvé pour ce connecteur",
    noIndexedAssets:
      'Aucun actif indexé n\'a été trouvé pour ce connecteur avec le compartiment "{{bucketName}}".',
    loadingAssets: "Chargement des actifs...",
    menu: {
      rename: "Renommer",
      share: "Partager",
      download: "Télécharger",
    },
    deleteDialog: {
      title: "Confirmer la suppression",
      description:
        "Êtes-vous sûr de vouloir supprimer cet actif ? Cette action est irréversible.",
      cancel: "Annuler",
      confirm: "Supprimer",
    },
  },
  sidebar: {
    menu: {
      home: "Accueil",
      assets: "Actifs",
      pipelines: "Pipelines",
      pipelineExecutions: "Exécutions de pipeline",
      settings: "Paramètres",
    },
    submenu: {
      system: "Paramètres système",
      connectors: "Connecteurs",
      userManagement: "Gestion des utilisateurs",
      roles: "Rôles",
      integrations: "Intégrations",
      environments: "Environnements",
    },
  },
  profile: {
    title: "Profil",
    description: "Gérez les paramètres et préférences de votre compte",
    changePhoto: "Changer la photo",
    jobTitle: "Poste",
    organization: "Organisation",
    preferences: "Préférences",
    timezone: "Fuseau horaire",
    emailNotifications: "Notifications par email",
    pushNotifications: "Notifications push",
    changePassword: "Changer le mot de passe",
    twoFactorAuth: "Authentification à deux facteurs",
    appearance: "Apparence",
  },
  app: {
    loading: "Chargement...",
    errors: {
      loadingConfig: "Erreur lors du chargement de la configuration AWS :",
      loadingUserAttributes:
        "Erreur lors du chargement des attributs utilisateur :",
      signingOut: "Erreur lors de la déconnexion :",
    },
    navigation: {
      preventedDuplicate: "Navigation en double empêchée vers",
      navigating: "Navigation depuis",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "Recherche sémantique",
    filters: {
      dateRange: "Plage de dates",
      contentType: "Type de contenu",
      storageLocation: "Emplacement de stockage",
      comingSoon: "Plus de filtres bientôt disponibles...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "Utilisation du stockage",
      apiUsage: "Utilisation de l'API",
      activeUsers: "Utilisateurs actifs",
      systemLoad: "Charge du système",
    },
    errors: {
      userDeletionNotImplemented:
        "La suppression d'utilisateur n'est pas encore implémentée.",
      userCreationNotImplemented:
        "La création d'utilisateur n'est pas encore implémentée.",
      userEditingNotImplemented:
        "La modification d'utilisateur n'est pas encore implémentée.",
      analyticsExportNotImplemented:
        "L'export des analyses n'est pas encore implémenté.",
      systemResetNotImplemented:
        "La réinitialisation du système n'est pas encore implémentée.",
    },
    columns: {
      lastActive: "Dernière activité",
    },
    buttons: {
      exportAnalytics: "Exporter les analyses",
      resetSystem: "Réinitialiser le système",
    },
  },
  integrations: {
    title: "Intégrations",
    selectProvider: "Sélectionnez une intégration",
    selectIntegration: "Sélectionnez une intégration",
    configureIntegration: "Configurer l'intégration",
    description: "Gérez vos intégrations et connexions",
    addIntegration: "Ajouter une intégration",
    form: {
      search: {
        placeholder: "Rechercher des intégrations",
      },
      title: "Ajouter une intégration",
      fields: {
        nodeId: {
          label: "Intégration",
          tooltip: "Sélectionnez un fournisseur d'intégration",
          errors: {
            required: "La sélection d'une intégration est requise",
          },
        },
        description: {
          label: "Description",
          tooltip: "Fournissez une description pour cette intégration",
          helper: "Brève description de cette intégration",
          errors: {
            required: "La description est requise",
          },
        },
        environmentId: {
          label: "Environnement",
          tooltip: "Sélectionnez l'environnement pour cette intégration",
          errors: {
            required: "La sélection d'un environnement est requise",
          },
        },
        enabled: {
          label: "Activé",
          tooltip: "Activez ou désactivez cette intégration",
          errors: {
            required: "L'activation est requise",
          },
        },
        auth: {
          type: {
            label: "Type d'authentification",
            tooltip: "Sélectionnez la méthode d'authentification",
            options: {
              awsIam: "AWS IAM",
              apiKey: "Clé API",
            },
            errors: {
              required: "Le type d'authentification est requis",
            },
          },
          credentials: {
            apiKey: {
              label: "Clé API",
              tooltip: "Entrez votre clé API",
              helper: "Clé API pour l'authentification avec le service",
              errors: {
                required: "La clé API est requise",
              },
            },
            iamRole: {
              label: "Rôle IAM",
              tooltip: "Entrez l'ARN du rôle IAM",
              errors: {
                required: "Le rôle IAM est requis",
              },
            },
          },
        },
      },
      errors: {
        required: "Ce champ est requis",
        nodeId: {
          unrecognized_keys: "Sélection d'intégration invalide",
        },
      },
    },
  },
  pipelines: {
    title: "Pipelines",
    description: "Gérez vos pipelines de médias et métadonnées",
    searchPlaceholder: "Recherchez des pipelines...",
    actions: {
      create: "Ajouter un nouveau pipeline",
      import: "Importer un pipeline",
    },
  },
  executions: {
    title: "Exécutions de pipeline",
    description: "Surveillez et gérez vos exécutions de pipeline",
    searchPlaceholder: "Recherchez des exécutions de pipeline...",
    columns: {
      pipelineName: "Nom du pipeline",
      status: "Statut",
      startTime: "Heure de début",
      endTime: "Heure de fin",
      duration: "Durée",
      actions: "Actions",
    },
    actions: {
      retryFromCurrent: "Réessayer à partir de la position actuelle",
      retryFromStart: "Réessayer depuis le début",
      viewDetails: "Voir les détails",
    },
  },
  users: {
    title: "Gestion des utilisateurs",
    description: "Gérez les utilisateurs du système et leurs accès",
    actions: {
      addUser: "Ajouter un utilisateur",
    },
    form: {
      title: {
        add: "Ajouter un utilisateur",
      },
      fields: {
        given_name: {
          label: "Prénom",
          tooltip: "Entrez le prénom de l'utilisateur",
          helper: "",
        },
        family_name: {
          label: "Nom de famille",
          tooltip: "Entrez le nom de famille de l'utilisateur",
          helper: "",
        },
        email: {
          label: "Email",
          tooltip: "Entrez l'adresse email de l'utilisateur",
          helper: "",
        },
        roles: {
          label: "Rôles",
          tooltip: "Sélectionnez les rôles pour l'utilisateur",
          options: {
            Admin: "Administrateur",
            Editor: "Éditeur",
            Viewer: "Spectateur",
          },
        },
        email_verified: {
          label: "Email vérifié",
          tooltip: "Indiquez si l'email de l'utilisateur a été vérifié",
        },
        enabled: {
          label: "Activé",
          tooltip: "Activez ou désactivez l'utilisateur",
        },
      },
    },
    roles: {
      admin: "Administrateur",
      editor: "Éditeur",
      viewer: "Spectateur",
    },
  },
  roles: {
    title: "Gestion des rôles",
    description: "Gérez les rôles du système et leurs permissions",
    actions: {
      addRole: "Ajouter un rôle",
    },
  },
  settings: {
    environments: {
      title: "Environnements",
      description:
        "Gérez les environnements du système et leurs configurations",
      addButton: "Ajouter un environnement",
      searchPlaceholder: "Recherchez des environnements",
      createTitle: "Créer un environnement",
      form: {
        name: "Nom de l'environnement",
        region: "Région",
        status: {
          name: "Statut",
          active: "Actif",
          disabled: "Désactivé",
        },
        costCenter: "Centre de coût",
        team: "Équipe",
      },
    },
    systemSettings: {
      title: "Paramètres système",
      tabs: {
        search: "Recherche",
        notifications: "Notifications",
        security: "Sécurité",
        performance: "Performance",
      },
      search: {
        title: "Configuration de la recherche",
        description:
          "Configurez le fournisseur de recherche pour améliorer les capacités de recherche de vos actifs multimédias.",
        provider: "Fournisseur de recherche :",
        configureProvider: "Configurer le fournisseur de recherche",
        editProvider: "Modifier le fournisseur",
        resetProvider: "Réinitialiser le fournisseur",
        providerDetails: "Détails du fournisseur",
        providerName: "Nom du fournisseur",
        apiKey: "Clé API",
        endpoint: "URL de l'endpoint (optionnel)",
        enabled: "Recherche activée",
        noProvider: "Aucun fournisseur de recherche configuré.",
        configurePrompt:
          "Configurez Twelve Labs pour activer les capacités de recherche.",
      },
      notifications: {
        title: "Paramètres de notifications",
        comingSoon: "Paramètres de notification bientôt disponibles.",
      },
      security: {
        title: "Paramètres de sécurité",
        comingSoon: "Paramètres de sécurité bientôt disponibles.",
      },
      performance: {
        title: "Paramètres de performance",
        comingSoon: "Paramètres de performance bientôt disponibles.",
      },
    },
  },
  common: {
    select: "Sélectionner",
    back: "Retour",
    search: "Rechercher",
    profile: "Profil",
    logout: "Déconnexion",
    theme: "Thème",
    close: "Fermer",
    refresh: "Rafraîchir",
    cancel: "Annuler",
    save: "Enregistrer",
    loading: "Chargement...",
    loadMore: "Charger plus",
    tableDensity: "Densité du tableau",
    moreInfo: "Plus d'informations",
    error: "Erreur",
    language: "Langue",
    delete: "Supprimer",
    create: "Créer",
    actions: {
      add: "Ajouter",
    },
    columns: {
      username: "Nom d'utilisateur",
      firstName: "Prénom",
      lastName: "Nom de famille",
      email: "Email",
      status: "Statut",
      groups: "Groupes",
      created: "Créé",
      modified: "Modifié",
      actions: "Actions",
    },
    status: {
      active: "Actif",
      inactive: "Inactif",
    },
  },
  translation: {
    common: {
      actions: {
        add: "Ajouter",
        edit: "Modifier",
        delete: "Supprimer",
        activate: "Activer",
        deactivate: "Désactiver",
        create: "Créer",
      },
      tableDensity: "Densité du tableau",
      theme: "Thème",
      back: "Retour",
      loading: "Chargement...",
      error: "Quelque chose s'est mal passé",
      save: "Enregistrer",
      cancel: "Annuler",
      delete: "Supprimer",
      edit: "Modifier",
      search: "Rechercher",
      profile: "Profil",
      filterColumn: "Filtrer",
      searchValue: "Rechercher",
      logout: "Déconnexion",
      language: "Langue",
      alerts: "Alertes",
      warnings: "Avertissements",
      notifications: "Notifications",
      searchPlaceholder: "Recherchez ou utilisez clé:valeur...",
      close: "Fermer",
      success: "Succès",
      refresh: "Rafraîchir",
      previous: "Précédent",
      next: "Suivant",
      show: "Afficher",
      all: "Tous",
      status: {
        active: "Actif",
        inactive: "Inactif",
      },
      rename: "Renommer",
      root: "Racine",
      folder: "Dossier",
      loadMore: "Charger plus",
      darkMode: "Mode sombre",
      lightMode: "Mode clair",
      filter: "Filtrer",
      textFilter: "Filtre textuel",
      selectFilter: "Sélectionner un filtre",
      clearFilter: "Effacer le filtre",
      columns: {
        username: "Nom d'utilisateur",
        firstName: "Prénom",
        lastName: "Nom de famille",
        email: "Email",
        status: "Statut",
        groups: "Groupes",
        created: "Créé",
        modified: "Modifié",
        actions: "Actions",
      },
      noGroups: "Aucun groupe",
      select: "Sélectionner",
      moreInfo: "Plus d'informations",
    },
    users: {
      title: "Gestion des utilisateurs",
      search: "Rechercher des utilisateurs",
      description: "Gérez les utilisateurs du système et leurs accès",
      form: {
        fields: {
          given_name: {
            label: "Prénom",
            tooltip: "Entrez le prénom de l'utilisateur",
            errors: {
              required: "Le prénom est requis",
            },
          },
          family_name: {
            label: "Nom de famille",
            tooltip: "Entrez le nom de famille de l'utilisateur",
            errors: {
              required: "Le nom de famille est requis",
            },
          },
          email: {
            label: "Email",
            tooltip: "Entrez l'adresse email de l'utilisateur",
            errors: {
              required: "L'email est requis",
              invalid: "Adresse email invalide",
            },
          },
          enabled: {
            label: "Activé",
            tooltip: "Activez ou désactivez l'utilisateur",
            errors: {
              required: "L'activation est requise",
            },
          },
          roles: {
            label: "Rôles",
            tooltip: "Sélectionnez les rôles pour l'utilisateur",
            errors: {
              required: "Les rôles sont requis",
            },
          },
          email_verified: {
            label: "Email vérifié",
            tooltip: "Indiquez si l'email de l'utilisateur a été vérifié",
            errors: {
              required: "La vérification de l'email est requise",
            },
          },
        },
      },
    },
    roles: {
      title: "Gestion des rôles",
      description: "Gérez les rôles du système et leurs permissions",
      admin: "Administrateur",
      editor: "Éditeur",
      viewer: "Spectateur",
      actions: {
        addRole: "Ajouter un rôle",
      },
    },
    columns: {
      username: "Nom d'utilisateur",
      firstName: "Prénom",
      lastName: "Nom de famille",
      email: "Email",
      status: "Statut",
      groups: "Groupes",
      created: "Créé",
      modified: "Modifié",
      actions: "Actions",
    },
    actions: {
      addUser: "Ajouter un utilisateur",
      edit: "Modifier l'utilisateur",
      delete: "Supprimer l'utilisateur",
      activate: "Activer l'utilisateur",
      deactivate: "Désactiver l'utilisateur",
    },
    status: {
      active: "Actif",
      inactive: "Inactif",
    },
    errors: {
      loadFailed: "Échec du chargement des utilisateurs",
      saveFailed: "Échec de l'enregistrement de l'utilisateur",
      deleteFailed: "Échec de la suppression de l'utilisateur",
    },
    navigation: {
      home: "Accueil",
      collections: "Collections",
      settings: "Paramètres",
    },
    home: {
      welcome: "Bienvenue sur Media Lake",
      description: "Gérez et organisez efficacement vos fichiers multimédias",
      statistics: "Statistiques",
      collections: "Collections",
      sharedCollections: "Collections partagées",
      favorites: "Favoris",
      smartFolders: "Dossiers intelligents",
      connectedStorage: "Stockage connecté",
      sharing: "Partage",
      comingSoon: "Bientôt disponible",
    },
    notifications: {
      "Pipeline Complete": "Pipeline terminé",
      "Asset processing pipeline completed successfully":
        "Le pipeline de traitement des actifs s'est terminé avec succès",
      "Storage Warning": "Avertissement de stockage",
      "Storage capacity reaching 80%": "Capacité de stockage atteignant 80%",
      "Pipeline Failed": "Pipeline échoué",
      "Video processing pipeline failed":
        "Le pipeline de traitement vidéo a échoué",
    },
    modal: {
      confirmDelete: "Êtes-vous sûr de vouloir supprimer cet élément ?",
      confirmAction: "Êtes-vous sûr de vouloir effectuer cette action ?",
      error: "Une erreur est survenue",
      success: "Opération terminée avec succès",
    },
    executions: {
      title: "Exécutions de pipeline",
      description: "Surveillez et gérez vos exécutions de pipeline",
      searchPlaceholder: "Recherchez des exécutions de pipeline...",
      columns: {
        pipelineName: "Nom du pipeline",
        status: "Statut",
        startTime: "Heure de début",
        endTime: "Heure de fin",
        duration: "Durée",
        actions: "Actions",
      },
      status: {
        succeeded: "Réussi",
        failed: "Échoué",
        running: "En cours",
        timedOut: "Temps écoulé",
        aborted: "Annulé",
      },
      actions: {
        retryFromCurrent: "Réessayer à partir de la position actuelle",
        retryFromStart: "Réessayer depuis le début",
        viewDetails: "Voir les détails",
      },
      pagination: {
        page: "Page {{page}} sur {{total}}",
        showEntries: "Afficher {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "Filtrer par nom",
      },
      error: {
        loading: "Erreur lors du chargement des objets S3 : {{message}}",
      },
      file: {
        info: "Taille : {{size}} • Classe de stockage : {{storageClass}} • Modifié : {{modified}}",
      },
      menu: {
        rename: "Renommer",
        delete: "Supprimer",
      },
    },
    assets: {
      title: "Actifs",
      connectedStorage: "Stockage connecté",
    },
    metadata: {
      title: "Bientôt disponible",
      description:
        "Nous travaillons à vous offrir des fonctionnalités de gestion des métadonnées. Restez à l'écoute !",
    },
    pipelines: {
      title: "Pipelines",
      description: "Gérez vos pipelines de médias et métadonnées",
      searchPlaceholder: "Recherchez des pipelines...",
      actions: {
        create: "Ajouter un nouveau pipeline",
        deploy: "Déployer le pipeline d'images",
        addNew: "Ajouter un nouveau pipeline",
        viewAll: "Voir tous les pipelines",
        import: "Importer un pipeline",
      },
      search: "Rechercher des pipelines",
      deploy: "Déployer le pipeline d'images",
      addNew: "Ajouter un nouveau pipeline",
      columns: {
        name: "Nom",
        creationDate: "Date de création",
        system: "Système",
        type: "Type",
        actions: "Actions",
      },
      editor: {
        title: "Éditeur de pipeline",
        save: "Enregistrer le pipeline",
        validate: "Valider le pipeline",
        sidebar: {
          title: "Nœuds",
          dragNodes: "Faites glisser les nœuds sur le canevas",
          loading: "Chargement des nœuds...",
          error: "Erreur lors du chargement des nœuds",
        },
        node: {
          configure: "Configurer {{type}}",
          delete: "Supprimer le nœud",
          edit: "Modifier le nœud",
        },
        edge: {
          title: "Modifier l'étiquette de la connexion",
          label: "Étiquette de connexion",
          delete: "Supprimer la connexion",
        },
        modals: {
          error: {
            title: "Erreur",
            incompatibleNodes:
              "La sortie du nœud précédent n'est pas compatible avec l'entrée du nœud de destination.",
            validation: "La validation du pipeline a échoué",
          },
          delete: {
            title: "Supprimer le pipeline",
            message:
              "Êtes-vous sûr de vouloir supprimer ce pipeline ? Cette action est irréversible.",
            confirm: "Tapez le nom du pipeline pour confirmer la suppression :",
          },
        },
        controls: {
          undo: "Annuler",
          redo: "Rétablir",
          zoomIn: "Agrandir",
          zoomOut: "Rétrécir",
          fitView: "Adapter la vue",
          lockView: "Verrouiller la vue",
        },
        notifications: {
          saved: "Pipeline enregistré avec succès",
          validated: "Validation du pipeline réussie",
          error: {
            save: "Échec de l'enregistrement du pipeline",
            validation: "La validation du pipeline a échoué",
            incompatibleNodes: "Connexion de nœud incompatible",
          },
        },
      },
    },
    integrations: {
      title: "Intégrations",
      description: "Gérez vos intégrations et connexions",
      addIntegration: "Ajouter une intégration",
      selectIntegration: "Sélectionnez une intégration",
      selectProvider: "Sélectionnez un fournisseur",
      configureIntegration: "Configurer l'intégration",
      deleteConfirmation: {
        title: "Supprimer l'intégration",
        message: "Êtes-vous sûr de vouloir supprimer cette intégration ?",
        warning:
          "Attention : La suppression de cette intégration peut entraîner l'échec des pipelines qui l'utilisent.",
      },
      form: {
        title: "Ajouter une intégration",
        fields: {
          nodeId: {
            label: "Intégration",
            tooltip: "Sélectionnez un fournisseur d'intégration",
            errors: {
              required: "La sélection d'une intégration est requise",
            },
          },
          description: {
            label: "Description",
            tooltip: "Fournissez une description pour cette intégration",
            helper: "Brève description de cette intégration",
            errors: {
              required: "La description est requise",
            },
          },
          environmentId: {
            label: "Environnement",
            tooltip: "Sélectionnez l'environnement pour cette intégration",
            errors: {
              required: "La sélection d'un environnement est requise",
            },
          },
          enabled: {
            label: "Activé",
            tooltip: "Activez ou désactivez cette intégration",
            errors: {
              required: "L'activation est requise",
            },
          },
          auth: {
            type: {
              label: "Type d'authentification",
              tooltip: "Sélectionnez la méthode d'authentification",
              options: {
                awsIam: "AWS IAM",
                apiKey: "Clé API",
              },
              errors: {
                required: "Le type d'authentification est requis",
              },
            },
            credentials: {
              apiKey: {
                label: "Clé API",
                tooltip: "Entrez votre clé API",
                helper: "Clé API pour l'authentification avec le service",
                errors: {
                  required: "La clé API est requise",
                },
              },
              iamRole: {
                label: "Rôle IAM",
                tooltip: "Entrez l'ARN du rôle IAM",
                errors: {
                  required: "Le rôle IAM est requis",
                },
              },
            },
          },
        },
        search: {
          placeholder: "Recherchez des intégrations",
        },
        errors: {
          required: "Ce champ est requis",
          nodeId: {
            unrecognized_keys: "Sélection d'intégration invalide",
          },
        },
      },
      columns: {
        nodeName: "Nom du nœud",
        environment: "Environnement",
        createdDate: "Date de création",
        modifiedDate: "Date de modification",
        actions: "Actions",
      },
      settings: {
        environments: {
          title: "Environnements",
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "Ajouter un groupe",
      editGroup: "Modifier le groupe",
      deleteGroup: "Supprimer le groupe",
      createGroup: "Créer un groupe",
      manageGroups: "Gérer les groupes",
    },
  },
  permissionSets: {
    noAssignments: "Aucun ensemble de permissions",
    actions: {
      addPermissionSet: "Ajouter un ensemble de permissions",
      editPermissionSet: "Modifier l'ensemble de permissions",
      deletePermissionSet: "Supprimer l'ensemble de permissions",
    },
  },
};
