export default {
  languages: {
    english: "English",
    german: "German",
    portuguese: "Portuguese",
    french: "French",
    chinese: "Chinese",
    hindi: "Hindi",
    arabic: "Arabic",
    hebrew: "Hebrew",
    japanese: "Japanese",
    korean: "Korean",
    spanish: "Spanish",
  },
  assetsPage: {
    title: "Assets",
    connectors: "Connectors",
    selectConnector: "Select a connector",
  },
  upload: {
    title: "Upload Media Files",
    description:
      "Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported.",
  },
  connectors: {
    apiMessages: {
      creating: {
        loading: "Creating connector...",
        success: "Connector Created",
        successMessage: "New connector has been successfully created.",
        error: "Connector Creation Failed",
      },
      updating: {
        loading: "Updating connector...",
        success: "Connector Updated",
        successMessage: "Connector has been successfully updated.",
        error: "Connector Update Failed",
      },
      deleting: {
        loading: "Deleting connector...",
        success: "Connector Deleted",
        successMessage: "Connector has been successfully deleted.",
        error: "Connector Deletion Failed",
      },
      enabling: {
        loading: "Enabling connector...",
        success: "Connector Enabled",
        successMessage: "Connector has been successfully enabled.",
        error: "Connector Enable Failed",
      },
      disabling: {
        loading: "Disabling connector...",
        success: "Connector Disabled",
        successMessage: "Connector has been successfully disabled.",
        error: "Connector Disable Failed",
      },
    },
  },
  assets: {
    favorite: "Favorite",
    unfavorite: "Unfavorite",
    rename: "Rename",
    delete: "Delete",
    download: "Download",
    share: "Share",
    viewDetails: "View Details",
    retry: "Retry",
    retryFromCurrent: "Retry from current position",
  },
  assetExplorer: {
    noConnectorSelected: "Select a connector to view assets",
    noAssetsFound: "No assets found for this connector",
    noIndexedAssets:
      'No indexed assets were found for this connector with bucket "{{bucketName}}".',
    loadingAssets: "Loading assets...",
    menu: {
      rename: "Rename",
      share: "Share",
      download: "Download",
    },
    deleteDialog: {
      title: "Confirm Delete",
      description:
        "Are you sure you want to delete this asset? This action cannot be undone.",
      cancel: "Cancel",
      confirm: "Delete",
      deleting: "Deleting...",
    },
  },
  home: {
    title: "Home",
    description: "Guidance for your media, metadata, and workflows.",
    statistics: "Statistics",
    collections: "Collections",
    sharedCollections: "Shared Collections",
    favorites: "Favorites",
    smartFolders: "Smart Folders",
    connectedStorage: "Connected Storage",
    sharing: "Sharing",
    comingSoon: "Coming Soon",
    yourFavoriteAssets: "Your Favorite Assets",
    noFavoriteAssets: "No favorite assets yet",
  },
  sidebar: {
    menu: {
      home: "Home",
      assets: "Assets",
      pipelines: "Pipelines",
      pipelineExecutions: "Pipeline Executions",
      settings: "Settings",
    },
    submenu: {
      system: "System Settings",
      connectors: "Connectors",
      userManagement: "User Management",
      roles: "Roles",
      integrations: "Integrations",
      environments: "Environments",
      usersAndGroups: "Users and Groups",
      permissionSets: "Permissions",
    },
  },
  profile: {
    title: "Profile",
    description: "Manage your account settings and preferences",
    changePhoto: "Change Photo",
    jobTitle: "Job Title",
    organization: "Organization",
    preferences: "Preferences",
    timezone: "Timezone",
    emailNotifications: "Email Notifications",
    pushNotifications: "Push Notifications",
    changePassword: "Change Password",
    twoFactorAuth: "Two-Factor Authentication",
    appearance: "Appearance",
    noFirstName: "User doesn't have a first name configured",
    noLastName: "User doesn't have a last name configured",
  },
  app: {
    loading: "Loading...",
    errors: {
      loadingConfig: "Error loading AWS configuration:",
      loadingUserAttributes: "Error loading user attributes:",
      signingOut: "Error signing out:",
    },
    navigation: {
      preventedDuplicate: "Prevented duplicate navigation to",
      navigating: "Navigating from",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: {
      label: "Semantic",
      enable: "Enable semantic search",
      disable: "Disable semantic search",
    },
    filters: {
      dateRange: "Date Range",
      contentType: "Content Type",
      storageLocation: "Storage Location",
      title: "Filter Results",
      apply: "Apply Filters",
      reset: "Reset",
      toDate: "To Date & Time",
      fromDate: "From Date & Time",
      maxSize: "Max",
      minSize: "Min",
      comingSoon: "More filters coming soon...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "Storage Usage",
      apiUsage: "API Usage",
      activeUsers: "Active Users",
      systemLoad: "System Load",
    },
    errors: {
      userDeletionNotImplemented: "User deletion is not implemented yet.",
      userCreationNotImplemented: "User creation is not implemented yet.",
      userEditingNotImplemented: "User editing is not implemented yet.",
      analyticsExportNotImplemented: "Analytics export is not implemented yet.",
      systemResetNotImplemented: "System reset is not implemented yet.",
    },
    columns: {
      lastActive: "Last Active",
    },
    buttons: {
      exportAnalytics: "Export Analytics",
      resetSystem: "Reset System",
    },
  },
  integrations: {
    title: "Integrations",
    selectProvider: "Select Integration",
    selectIntegration: "Select Integration",
    configureIntegration: "Configure Integration",
    description: "Manage your integrations and connections",
    addIntegration: "Add Integration",
    deleteConfirmation: {
      title: "Delete Integration",
      message: "Are you sure you want to delete this integration?",
      warning:
        "Caution: Removing this integration may cause pipelines that rely on it to fail.",
    },
    form: {
      search: {
        placeholder: "Search integrations",
      },
      title: "Add Integration",
      fields: {
        nodeId: {
          label: "Integration",
          tooltip: "Select an integration provider",
          errors: {
            required: "Integration selection is required",
          },
        },
        description: {
          label: "Description",
          tooltip: "Provide a description for this integration",
          errors: {
            required: "Description is required",
          },
        },
        environmentId: {
          label: "Environment",
          tooltip: "Select the environment for this integration",
          errors: {
            required: "Environment selection is required",
          },
        },
        enabled: {
          label: "Enabled",
          tooltip: "Enable or disable this integration",
          errors: {
            required: "Enabled is required",
          },
        },
        auth: {
          type: {
            label: "Authentication Type",
            tooltip: "Select the authentication method",
            options: {
              awsIam: "AWS IAM",
              apiKey: "API Key",
            },
            errors: {
              required: "Authentication type is required",
            },
          },
          credentials: {
            apiKey: {
              label: "API Key",
              tooltip: "Enter your API key",
              errors: {
                required: "API Key is required",
              },
            },
            iamRole: {
              label: "IAM Role",
              tooltip: "Enter the IAM role ARN",
              errors: {
                required: "IAM Role is required",
              },
            },
          },
        },
      },
      errors: {
        required: "This field is required",
        nodeId: {
          unrecognized_keys: "Invalid integration selection",
        },
      },
    },
  },
  pipelines: {
    title: "Pipelines",
    description: "Manage your media and metadata pipelines",
    searchPlaceholder: "Search pipelines...",
    actions: {
      create: "Add New Pipeline",
      import: "Import Pipeline",
    },
  },
  executions: {
    title: "Pipeline Executions",
    description: "Monitor and manage your pipeline executions",
    searchPlaceholder: "Search pipeline executions...",
    columns: {
      pipelineName: "Pipeline Name",
      status: "Status",
      startTime: "Start Time",
      endTime: "End Time",
      duration: "Duration",
      actions: "Actions",
    },
    actions: {
      retryFromCurrent: "Retry from current position",
      retryFromStart: "Retry from start",
      viewDetails: "View Details",
    },
  },
  users: {
    title: "User Management",
    description: "Manage system users and their access",
    actions: {
      addUser: "Add User",
    },
    apiMessages: {
      creating: {
        loading: "Creating user...",
        success: "User Created",
        successMessage: "New user has been successfully created.",
        error: "User Creation Failed",
      },
      updating: {
        loading: "Updating user...",
        success: "User Updated",
        successMessage: "User has been successfully updated.",
        error: "User Update Failed",
      },
      deleting: {
        loading: "Deleting user...",
        success: "User Deleted",
        successMessage: "User has been successfully deleted.",
        error: "User Deletion Failed",
      },
      enabling: {
        loading: "Enabling user...",
        success: "User Enabled",
        successMessage: "User has been successfully enabled.",
        error: "User Enable Failed",
      },
      disabling: {
        loading: "Disabling user...",
        success: "User Disabled",
        successMessage: "User has been successfully disabled.",
        error: "User Disable Failed",
      },
    },
    form: {
      title: {
        add: "Add User",
      },
      fields: {
        given_name: {
          label: "First Name",
          tooltip: "Enter the user's first name",
          helper: "",
        },
        family_name: {
          label: "Last Name",
          tooltip: "Enter the user's last name",
          helper: "",
        },
        email: {
          label: "Email",
          tooltip: "Enter the user's email address",
          helper: "",
        },
        roles: {
          label: "Roles",
          tooltip: "Select the roles for the user",
          options: {
            Admin: "Admin",
            Editor: "Editor",
            Viewer: "Viewer",
          },
        },
        email_verified: {
          label: "Email Verified",
          tooltip: "Indicate if the user's email has been verified",
        },
        enabled: {
          label: "Enabled",
          tooltip: "Enable or disable the user",
        },
      },
    },
    roles: {
      admin: "Admin",
      editor: "Editor",
      viewer: "Viewer",
    },
  },
  roles: {
    title: "Role Management",
    description: "Manage system roles and their permissions",
    actions: {
      addRole: "Add Role",
    },
  },
  settings: {
    environments: {
      title: "Environments",
      description: "Manage system environments and their configurations",
      addButton: "Add Environment",
      searchPlaceholder: "Search environments",
      createTitle: "Create Environment",
      form: {
        name: "Environment Name",
        region: "Region",
        status: {
          name: "Status",
          active: "Active",
          disabled: "Disabled",
        },
        costCenter: "Cost Center",
        team: "Team",
      },
    },
    systemSettings: {
      title: "System Settings",
      tabs: {
        search: "Search",
        regions: "Regions",
        notifications: "Notifications",
        security: "Security",
        performance: "Performance",
      },
      regions: {
        title: "Regions",
        description:
          "Enable and disable regions that assets can be indexed from and pipelines can be deployed to.",
      },
      search: {
        title: "Search Configuration",
        description:
          "Configure the search provider for enhanced search capabilities across your media assets.",
        provider: "Semantic Search Provider",
        configureProvider: "Configure Search Provider",
        editProvider: "Edit Provider",
        resetProvider: "Reset Provider",
        providerDetails: "Provider Details",
        providerName: "Provider Name",
        apiKey: "API Key",
        endpoint: "Endpoint URL (Optional)",
        enabled: "Search Enabled",
        noProvider: "No search provider configured.",
        configurePrompt: "Configure Twelve Labs to enable search capabilities.",
        semanticEnabled: "Semantic Search Enabled",
        semanticEnabledDesc: "Enable or disable semantic search functionality",
        providerDesc:
          "Select the embedding provider for semantic search capabilities",
        selectProvider: "Select Provider",
        editApiKey: "Edit", // pragma: allowlist secret
        configured: "Configured",
        configureApiKey: "Configure API Key", // pragma: allowlist secret
        apiKeyDesc:
          "Enter your Twelve Labs API key to enable semantic search functionality.",
        embeddingStore: "Semantic Search Embedding Store",
        embeddingStoreDesc:
          "Choose what embedding store to use for semantic searches",
        selectStore: "Select Store",
        saveSuccess: "Settings saved successfully",
        saveError: "Failed to save settings",
        cancelSuccess: "Changes cancelled",
        errorLoading: "Error loading search provider configuration",
      },
      notifications: {
        title: "Notifications Settings",
        comingSoon: "Notification settings coming soon.",
      },
      security: {
        title: "Security Settings",
        comingSoon: "Security settings coming soon.",
      },
      performance: {
        title: "Performance Settings",
        comingSoon: "Performance settings coming soon.",
      },
    },
  },
  common: {
    select: "Select",
    back: "Back",
    search: "Search",
    profile: "Profile",
    logout: "Logout",
    theme: "Theme",
    close: "Close",
    refresh: "Refresh",
    cancel: "Cancel",
    save: "Save",
    saving: "Saving...",
    loading: "Loading...",
    loadMore: "Load More",
    tableDensity: "Table Density",
    moreInfo: "More information",
    error: "Error",
    language: "Language",
    noResults: "No results found",
    selectFilter: "Select Filter",
    textFilter: "Text Filter",
    all: "All",
    filter: "Filter",
    noGroups: "No Groups",
    actions: {
      add: "Add",
      save: "Save",
      delete: "Delete",
      edit: "Edit",
      activate: "Activate",
      deactivate: "Deactivate",
    },
    columns: {
      permissionSets: "Permission Sets",
      username: "Username",
      firstName: "First Name",
      lastName: "Last Name",
      email: "Email",
      status: "Status",
      groups: "Groups",
      created: "Created",
      modified: "Modified",
      actions: "Actions",
    },
    status: {
      active: "Active",
      inactive: "Inactive",
    },
  },
  translation: {
    common: {
      actions: {
        add: "Add",
        edit: "Edit",
        delete: "Delete",
        activate: "Activate",
        deactivate: "Deactivate",
        create: "Create",
      },
      tableDensity: "Table Density",
      theme: "Theme",
      back: "Back",
      loading: "Loading...",
      error: "Something went wrong",
      save: "Save",
      cancel: "Cancel",
      delete: "Delete",
      edit: "Edit",
      search: "Search",
      profile: "Profile",
      filterColumn: "Filter",
      searchValue: "Search",
      logout: "Logout",
      language: "Language",
      alerts: "Alerts",
      warnings: "Warnings",
      notifications: "Notifications",
      searchPlaceholder: "Search or use key:value...",
      close: "Close",
      success: "Success",
      refresh: "Refresh",
      previous: "Previous",
      next: "Next",
      show: "Show",
      all: "All",
      status: {
        active: "Active",
        inactive: "Inactive",
      },
      rename: "Rename",
      root: "Root",
      folder: "Folder",
      loadMore: "Load More",
      darkMode: "Dark Mode",
      lightMode: "Light Mode",
      filter: "Filter",
      textFilter: "Text Filter",
      selectFilter: "Select Filter",
      clearFilter: "Clear Filter",
      columns: {
        username: "Username",
        firstName: "First Name",
        lastName: "Last Name",
        email: "Email",
        status: "Status",
        role: "Role",
        groups: "Groups",
        created: "Created",
        modified: "Modified",
        actions: "Actions",
      },
      noGroups: "No Groups",
      select: "Select",
      moreInfo: "More information",
    },
    users: {
      title: "User Management",
      search: "Search users",
      description: "Manage system users and their access",
      form: {
        fields: {
          given_name: {
            label: "First Name",
            tooltip: "Enter the user's first name",
            errors: {
              required: "First name is required",
            },
          },
          family_name: {
            label: "Last Name",
            tooltip: "Enter the user's last name",
            errors: {
              required: "Last name is required",
            },
          },
          email: {
            label: "Email",
            tooltip: "Enter the user's email address",
            errors: {
              required: "Email is required",
              invalid: "Invalid email address",
            },
          },
          enabled: {
            label: "Enabled",
            tooltip: "Enable or disable the user",
            errors: {
              required: "Enabled is required",
            },
          },
          roles: {
            label: "Roles",
            tooltip: "Select the roles for the user",
            errors: {
              required: "Roles are required",
            },
          },
          email_verified: {
            label: "Email Verified",
            tooltip: "Indicate if the user's email has been verified",
            errors: {
              required: "Email verification is required",
            },
          },
        },
      },
    },
    roles: {
      title: "Role Management",
      description: "Manage system roles and their permissions",
      admin: "Admin",
      editor: "Editor",
      viewer: "Viewer",
      actions: {
        addRole: "Add Role",
      },
    },
    columns: {
      username: "Username",
      firstName: "First Name",
      lastName: "Last Name",
      email: "Email",
      status: "Status",
      groups: "Groups",
      created: "Created",
      modified: "Modified",
      actions: "Actions",
    },
    actions: {
      addUser: "Add User",
      edit: "Edit User",
      delete: "Delete User",
      activate: "Activate User",
      deactivate: "Deactivate User",
    },
    status: {
      active: "Active",
      inactive: "Inactive",
    },
    errors: {
      loadFailed: "Failed to load users",
      saveFailed: "Failed to save user",
      deleteFailed: "Failed to delete user",
    },
    navigation: {
      home: "Home",
      collections: "Collections",
      settings: "Settings",
    },
    home: {
      welcome: "Welcome to Media Lake",
      description: "Guidance for your media, metadata, and workflows.",
      statistics: "Statistics",
      collections: "Collections",
      sharedCollections: "Shared Collections",
      favorites: "Favorites",
      smartFolders: "Smart Folders",
      connectedStorage: "Connected Storage",
      sharing: "Sharing",
      comingSoon: "Coming Soon",
    },
    notifications: {
      "Pipeline Complete": "Pipeline Complete",
      "Asset processing pipeline completed successfully":
        "Asset processing pipeline completed successfully",
      "Storage Warning": "Storage Warning",
      "Storage capacity reaching 80%": "Storage capacity reaching 80%",
      "Pipeline Failed": "Pipeline Failed",
      "Video processing pipeline failed": "Video processing pipeline failed",
    },
    modal: {
      confirmDelete: "Are you sure you want to delete this item?",
      confirmAction: "Are you sure you want to perform this action?",
      error: "An error occurred",
      success: "Operation completed successfully",
    },
    executions: {
      title: "Pipeline Executions",
      description: "Monitor and manage your pipeline executions",
      searchPlaceholder: "Search pipeline executions...",
      columns: {
        pipelineName: "Pipeline Name",
        status: "Status",
        startTime: "Start Time",
        endTime: "End Time",
        duration: "Duration",
        actions: "Actions",
      },
      status: {
        succeeded: "Succeeded",
        failed: "Failed",
        running: "Running",
        timedOut: "Timed Out",
        aborted: "Aborted",
      },
      actions: {
        retryFromCurrent: "Retry from current position",
        retryFromStart: "Retry from start",
        viewDetails: "View Details",
      },
      pagination: {
        page: "Page {{page}} of {{total}}",
        showEntries: "Show {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "Filter by name",
      },
      error: {
        loading: "Error loading S3 objects: {{message}}",
      },
      file: {
        info: "Size: {{size}} • Storage Class: {{storageClass}} • Modified: {{modified}}",
      },
      menu: {
        rename: "Rename",
        delete: "Delete",
      },
    },
    assets: {
      title: "Assets",
      connectedStorage: "Connected Storage",
    },
    metadata: {
      title: "Coming Soon",
      description:
        "We're working to bring you metadata management capabilities. Stay tuned!",
    },
    pipelines: {
      title: "Pipelines",
      description: "Manage your media and metadata pipelines",
      searchPlaceholder: "Search pipelines...",
      actions: {
        create: "Add New Pipeline",
        deploy: "Deploy Image Pipeline",
        addNew: "Add New Pipeline",
        viewAll: "View All Pipelines",
      },
      search: "Search pipelines",
      deploy: "Deploy Image Pipeline",
      addNew: "Add New Pipeline",
      columns: {
        name: "Name",
        creationDate: "Creation Date",
        system: "System",
        type: "Type",
        actions: "Actions",
      },
      editor: {
        title: "Pipeline Editor",
        save: "Save Pipeline",
        validate: "Validate Pipeline",
        sidebar: {
          title: "Nodes",
          dragNodes: "Drag nodes to the canvas",
          loading: "Loading nodes...",
          error: "Error loading nodes",
        },
        node: {
          configure: "Configure {{type}}",
          delete: "Delete Node",
          edit: "Edit Node",
        },
        edge: {
          title: "Edit Edge Label",
          label: "Edge Label",
          delete: "Delete Connection",
        },
        modals: {
          error: {
            title: "Error",
            incompatibleNodes:
              "The output of the previous node is not compatible with the input of the destination node.",
            validation: "Pipeline validation failed",
          },
          delete: {
            title: "Delete Pipeline",
            message:
              "Are you sure you want to delete this pipeline? This action cannot be undone.",
            confirm: "Type the pipeline name to confirm deletion:",
          },
        },
        controls: {
          undo: "Undo",
          redo: "Redo",
          zoomIn: "Zoom In",
          zoomOut: "Zoom Out",
          fitView: "Fit View",
          lockView: "Lock View",
        },
        notifications: {
          saved: "Pipeline saved successfully",
          validated: "Pipeline validation successful",
          error: {
            save: "Failed to save pipeline",
            validation: "Pipeline validation failed",
            incompatibleNodes: "Incompatible node connection",
          },
        },
      },
    },
    integrations: {
      title: "Integrations",
      description: "Manage your integrations and connections",
      addIntegration: "Add Integration",
      selectIntegration: "Select Integration",
      selectProvider: "Select Provider",
      configureIntegration: "Configure Integration",
      deleteConfirmation: {
        title: "Delete Integration",
        message: "Are you sure you want to delete this integration?",
        warning:
          "Warning: Deleting this integration may break pipelines that are using it.",
      },
      form: {
        title: "Add Integration",
        fields: {
          nodeId: {
            label: "Integration",
            tooltip: "Select an integration provider",
            errors: {
              required: "Integration selection is required",
            },
          },
          description: {
            label: "Description",
            tooltip: "Provide a description for this integration",
            helper: "Brief description of this integration",
            errors: {
              required: "Description is required",
            },
          },
          environmentId: {
            label: "Environment",
            tooltip: "Select the environment for this integration",
            errors: {
              required: "Environment selection is required",
            },
          },
          enabled: {
            label: "Enabled",
            tooltip: "Enable or disable this integration",
            errors: {
              required: "Enabled is required",
            },
          },
          auth: {
            type: {
              label: "Authentication Type",
              tooltip: "Select the authentication method",
              options: {
                awsIam: "AWS IAM",
                apiKey: "API Key",
              },
              errors: {
                required: "Authentication type is required",
              },
            },
            credentials: {
              apiKey: {
                label: "API Key",
                tooltip: "Enter your API key",
                helper: "API key for authentication with the service",
                errors: {
                  required: "API Key is required",
                },
              },
              iamRole: {
                label: "IAM Role",
                tooltip: "Enter the IAM role ARN",
                errors: {
                  required: "IAM Role is required",
                },
              },
            },
          },
        },
        search: {
          placeholder: "Search integrations",
        },

        errors: {
          required: "This field is required",
          nodeId: {
            unrecognized_keys: "Invalid integration selection",
          },
        },
      },
      columns: {
        nodeName: "Node Name",
        environment: "Environment",
        createdDate: "Created Date",
        modifiedDate: "Modified Date",
        actions: "Actions",
      },

      settings: {
        environments: {
          title: "Environments",
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "Add Group",
      editGroup: "Edit Group",
      deleteGroup: "Delete Group",
      createGroup: "Create Group",
      manageGroups: "Manage Groups",
      assignPermissionSet: "Assign Permission Set",
    },
    permissionSets: "Permission Sets",
    noPermissionSets: "No permission sets assigned",
  },
  permissionSets: {
    noAssignments: "No permission sets",
    actions: {
      addPermissionSet: "Add Permission Set",
      editPermissionSet: "Edit Permission Set",
      deletePermissionSet: "Delete Permission Set",
    },
  },
};
