export default {
  languages: {
    english: "Inglés",
    german: "Alemán",
    portuguese: "Portugués",
    french: "Francés",
    chinese: "Chino",
    hindi: "Hindi",
    arabic: "Árabe",
    hebrew: "Hebreo",
    japanese: "Japonés",
    korean: "Coreano",
    spanish: "Español",
  },
  assetsPage: {
    title: "Activos",
    connectors: "Conectores",
    selectConnector: "Seleccionar un conector",
  },
  connectors: {
    apiMessages: {
      creating: {
        loading: "Creando conector...",
        success: "Conector creado",
        successMessage: "El nuevo conector se ha creado exitosamente.",
        error: "Error al crear el conector",
      },
      updating: {
        loading: "Actualizando conector...",
        success: "Conector actualizado",
        successMessage: "El conector se ha actualizado exitosamente.",
        error: "Error al actualizar el conector",
      },
      deleting: {
        loading: "Eliminando conector...",
        success: "Conector eliminado",
        successMessage: "El conector se ha eliminado exitosamente.",
        error: "Error al eliminar el conector",
      },
      enabling: {
        loading: "Habilitando conector...",
        success: "Conector habilitado",
        successMessage: "El conector se ha habilitado exitosamente.",
        error: "Error al habilitar el conector",
      },
      disabling: {
        loading: "Deshabilitando conector...",
        success: "Conector deshabilitado",
        successMessage: "El conector se ha deshabilitado exitosamente.",
        error: "Error al deshabilitar el conector",
      },
    },
  },
  assets: {
    favorite: "Favorito",
    unfavorite: "Quitar de favoritos",
    rename: "Renombrar",
    delete: "Eliminar",
    download: "Descargar",
    share: "Compartir",
    viewDetails: "Ver detalles",
    retry: "Reintentar",
    retryFromCurrent: "Reintentar desde la posición actual",
  },
  assetExplorer: {
    noConnectorSelected: "Selecciona un conector para ver los activos",
    noAssetsFound: "No se encontraron activos para este conector",
    noIndexedAssets:
      'No se encontraron activos indexados para este conector con el bucket "{{bucketName}}".',
    loadingAssets: "Cargando activos...",
    menu: {
      rename: "Renombrar",
      share: "Compartir",
      download: "Descargar",
    },
    deleteDialog: {
      title: "Confirmar eliminación",
      description:
        "¿Estás seguro de que quieres eliminar este activo? Esta acción no se puede deshacer.",
      cancel: "Cancelar",
      confirm: "Eliminar",
    },
  },
  home: {
    title: "Inicio",
    description: "Guía para tus medios, metadatos y flujos de trabajo.",
    statistics: "Estadísticas",
    collections: "Colecciones",
    sharedCollections: "Colecciones compartidas",
    favorites: "Favoritos",
    smartFolders: "Carpetas inteligentes",
    connectedStorage: "Almacenamiento conectado",
    sharing: "Compartir",
    comingSoon: "Próximamente",
  },
  sidebar: {
    menu: {
      home: "Inicio",
      assets: "Activos",
      pipelines: "Pipelines",
      pipelineExecutions: "Ejecuciones de pipeline",
      settings: "Configuración",
    },
    submenu: {
      system: "Configuración del sistema",
      connectors: "Conectores",
      userManagement: "Gestión de usuarios",
      roles: "Roles",
      integrations: "Integraciones",
      environments: "Entornos",
    },
  },
  profile: {
    title: "Perfil",
    description: "Gestiona la configuración y preferencias de tu cuenta",
    changePhoto: "Cambiar foto",
    jobTitle: "Cargo",
    organization: "Organización",
    preferences: "Preferencias",
    timezone: "Zona horaria",
    emailNotifications: "Notificaciones por email",
    pushNotifications: "Notificaciones push",
    changePassword: "Cambiar contraseña",
    twoFactorAuth: "Autenticación de dos factores",
    appearance: "Apariencia",
    noFirstName: "El usuario no tiene un nombre configurado",
    noLastName: "El usuario no tiene un apellido configurado",
  },
  app: {
    loading: "Cargando...",
    errors: {
      loadingConfig: "Error al cargar la configuración de AWS:",
      loadingUserAttributes: "Error al cargar los atributos del usuario:",
      signingOut: "Error al cerrar sesión:",
    },
    navigation: {
      preventedDuplicate: "Se previno la navegación duplicada a",
      navigating: "Navegando desde",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: {
      label: "Semántico",
      enable: "Habilitar búsqueda semántica",
      disable: "Deshabilitar búsqueda semántica",
    },
    filters: {
      dateRange: "Rango de fechas",
      contentType: "Tipo de contenido",
      storageLocation: "Ubicación de almacenamiento",
      comingSoon: "Más filtros próximamente...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "Uso de almacenamiento",
      apiUsage: "Uso de API",
      activeUsers: "Usuarios activos",
      systemLoad: "Carga del sistema",
    },
    errors: {
      userDeletionNotImplemented:
        "La eliminación de usuarios aún no está implementada.",
      userCreationNotImplemented:
        "La creación de usuarios aún no está implementada.",
      userEditingNotImplemented:
        "La edición de usuarios aún no está implementada.",
      analyticsExportNotImplemented:
        "La exportación de analíticas aún no está implementada.",
      systemResetNotImplemented:
        "El reinicio del sistema aún no está implementado.",
    },
    columns: {
      lastActive: "Última actividad",
    },
    buttons: {
      exportAnalytics: "Exportar analíticas",
      resetSystem: "Reiniciar sistema",
    },
  },
  integrations: {
    title: "Integraciones",
    selectProvider: "Seleccionar integración",
    selectIntegration: "Seleccionar integración",
    configureIntegration: "Configurar integración",
    description: "Gestiona tus integraciones y conexiones",
    addIntegration: "Agregar integración",
    deleteConfirmation: {
      title: "Eliminar integración",
      message: "¿Estás seguro de que quieres eliminar esta integración?",
      warning:
        "Precaución: Eliminar esta integración puede causar que fallen los pipelines que dependen de ella.",
    },
    form: {
      search: {
        placeholder: "Buscar integraciones",
      },
      title: "Agregar integración",
      fields: {
        nodeId: {
          label: "Integración",
          tooltip: "Selecciona un proveedor de integración",
          errors: {
            required: "La selección de integración es requerida",
          },
        },
        description: {
          label: "Descripción",
          tooltip: "Proporciona una descripción para esta integración",
          helper: "Breve descripción de esta integración",
          errors: {
            required: "La descripción es requerida",
          },
        },
        environmentId: {
          label: "Entorno",
          tooltip: "Selecciona el entorno para esta integración",
          errors: {
            required: "La selección de entorno es requerida",
          },
        },
        enabled: {
          label: "Habilitado",
          tooltip: "Habilita o deshabilita esta integración",
          errors: {
            required: "Habilitado es requerido",
          },
        },
        auth: {
          type: {
            label: "Tipo de autenticación",
            tooltip: "Selecciona el método de autenticación",
            options: {
              awsIam: "AWS IAM",
              apiKey: "Clave API",
            },
            errors: {
              required: "El tipo de autenticación es requerido",
            },
          },
          credentials: {
            apiKey: {
              label: "Clave API",
              tooltip: "Ingresa tu clave API",
              helper: "Clave API para autenticación con el servicio",
              errors: {
                required: "La clave API es requerida",
              },
            },
            iamRole: {
              label: "Rol IAM",
              tooltip: "Ingresa el ARN del rol IAM",
              errors: {
                required: "El rol IAM es requerido",
              },
            },
          },
        },
      },
      errors: {
        required: "Este campo es requerido",
        nodeId: {
          unrecognized_keys: "Selección de integración inválida",
        },
      },
    },
  },
  pipelines: {
    title: "Pipelines",
    description: "Gestiona tus pipelines de medios y metadatos",
    searchPlaceholder: "Buscar pipelines...",
    actions: {
      create: "Agregar nuevo pipeline",
      import: "Importar pipeline",
    },
  },
  executions: {
    title: "Ejecuciones de pipeline",
    description: "Monitorea y gestiona tus ejecuciones de pipeline",
    searchPlaceholder: "Buscar ejecuciones de pipeline...",
    columns: {
      pipelineName: "Nombre del pipeline",
      status: "Estado",
      startTime: "Hora de inicio",
      endTime: "Hora de fin",
      duration: "Duración",
      actions: "Acciones",
    },
  },
  users: {
    title: "Gestión de usuarios",
    description: "Gestiona los usuarios del sistema y su acceso",
    actions: {
      addUser: "Agregar usuario",
    },
    apiMessages: {
      creating: {
        loading: "Creando usuario...",
        success: "Usuario creado",
        successMessage: "El nuevo usuario se ha creado exitosamente.",
        error: "Error al crear el usuario",
      },
      updating: {
        loading: "Actualizando usuario...",
        success: "Usuario actualizado",
        successMessage: "El usuario se ha actualizado exitosamente.",
        error: "Error al actualizar el usuario",
      },
      deleting: {
        loading: "Eliminando usuario...",
        success: "Usuario eliminado",
        successMessage: "El usuario se ha eliminado exitosamente.",
        error: "Error al eliminar el usuario",
      },
      enabling: {
        loading: "Habilitando usuario...",
        success: "Usuario habilitado",
        successMessage: "El usuario se ha habilitado exitosamente.",
        error: "Error al habilitar el usuario",
      },
      disabling: {
        loading: "Deshabilitando usuario...",
        success: "Usuario deshabilitado",
        successMessage: "El usuario se ha deshabilitado exitosamente.",
        error: "Error al deshabilitar el usuario",
      },
    },
    form: {
      title: {
        add: "Agregar usuario",
      },
      fields: {
        given_name: {
          label: "Nombre",
          tooltip: "Ingresa el nombre del usuario",
          helper: "",
        },
        family_name: {
          label: "Apellido",
          tooltip: "Ingresa el apellido del usuario",
          helper: "",
        },
        email: {
          label: "Email",
          tooltip: "Ingresa la dirección de email del usuario",
          helper: "",
        },
        roles: {
          label: "Roles",
          tooltip: "Selecciona los roles para el usuario",
          options: {
            Admin: "Administrador",
            Editor: "Editor",
            Viewer: "Visualizador",
          },
        },
        email_verified: {
          label: "Email verificado",
          tooltip: "Indica si el email del usuario ha sido verificado",
        },
        enabled: {
          label: "Habilitado",
          tooltip: "Habilita o deshabilita el usuario",
        },
      },
    },
    roles: {
      admin: "Administrador",
      editor: "Editor",
      viewer: "Visualizador",
    },
  },
  roles: {
    title: "Gestión de roles",
    description: "Gestiona los roles del sistema y sus permisos",
    actions: {
      addRole: "Agregar rol",
    },
  },
  settings: {
    environments: {
      title: "Entornos",
      description: "Gestiona los entornos del sistema y sus configuraciones",
      addButton: "Agregar entorno",
      searchPlaceholder: "Buscar entornos",
      createTitle: "Crear entorno",
      form: {
        name: "Nombre del entorno",
        region: "Región",
        status: {
          name: "Estado",
          active: "Activo",
          disabled: "Deshabilitado",
        },
        costCenter: "Centro de costos",
        team: "Equipo",
      },
    },
    systemSettings: {
      title: "Configuración del sistema",
      tabs: {
        search: "Búsqueda",
        notifications: "Notificaciones",
        security: "Seguridad",
        performance: "Rendimiento",
      },
      search: {
        title: "Configuración de búsqueda",
        description:
          "Configura el proveedor de búsqueda para capacidades de búsqueda mejoradas en tus activos multimedia.",
        provider: "Proveedor de búsqueda:",
        configureProvider: "Configurar proveedor de búsqueda",
        editProvider: "Editar proveedor",
        resetProvider: "Reiniciar proveedor",
        providerDetails: "Detalles del proveedor",
        providerName: "Nombre del proveedor",
        apiKey: "Clave API",
        endpoint: "URL del endpoint (Opcional)",
        enabled: "Búsqueda habilitada",
        noProvider: "No hay proveedor de búsqueda configurado.",
        configurePrompt:
          "Configura Twelve Labs para habilitar las capacidades de búsqueda.",
      },
      notifications: {
        title: "Configuración de notificaciones",
        comingSoon: "Configuración de notificaciones próximamente.",
      },
      security: {
        title: "Configuración de seguridad",
        comingSoon: "Configuración de seguridad próximamente.",
      },
      performance: {
        title: "Configuración de rendimiento",
        comingSoon: "Configuración de rendimiento próximamente.",
      },
    },
  },
  common: {
    select: "Seleccionar",
    back: "Atrás",
    search: "Buscar",
    profile: "Perfil",
    logout: "Cerrar sesión",
    theme: "Tema",
    close: "Cerrar",
    refresh: "Actualizar",
    cancel: "Cancelar",
    save: "Guardar",
    loading: "Cargando...",
    loadMore: "Cargar más",
    tableDensity: "Densidad de tabla",
    moreInfo: "Más información",
    error: "Error",
    language: "Idioma",
    noResults: "No se encontraron resultados",
    selectFilter: "Seleccionar filtro",
    textFilter: "Filtro de texto",
    all: "Todos",
    filter: "Filtro",
    noGroups: "Sin grupos",
    actions: {
      add: "Agregar",
      save: "Guardar",
      delete: "Eliminar",
      edit: "Editar",
      activate: "Activar",
      deactivate: "Desactivar",
    },
    columns: {
      permissionSets: "Conjuntos de permisos",
      username: "Nombre de usuario",
      firstName: "Nombre",
      lastName: "Apellido",
      email: "Email",
      status: "Estado",
      groups: "Grupos",
      created: "Creado",
      modified: "Modificado",
      actions: "Acciones",
    },
    status: {
      active: "Activo",
      inactive: "Inactivo",
    },
  },
  translation: {
    common: {
      actions: {
        add: "Agregar",
        edit: "Editar",
        delete: "Eliminar",
        activate: "Activar",
        deactivate: "Desactivar",
        create: "Crear",
      },
      tableDensity: "Densidad de tabla",
      theme: "Tema",
      back: "Atrás",
      loading: "Cargando...",
      error: "Algo salió mal",
      save: "Guardar",
      cancel: "Cancelar",
      delete: "Eliminar",
      edit: "Editar",
      search: "Buscar",
      profile: "Perfil",
      filterColumn: "Filtro",
      searchValue: "Buscar",
      logout: "Cerrar sesión",
      language: "Idioma",
      alerts: "Alertas",
      warnings: "Advertencias",
      notifications: "Notificaciones",
      searchPlaceholder: "Buscar o usar clave:valor...",
      close: "Cerrar",
      success: "Éxito",
      refresh: "Actualizar",
      previous: "Anterior",
      next: "Siguiente",
      show: "Mostrar",
      all: "Todos",
      status: {
        active: "Activo",
        inactive: "Inactivo",
      },
      rename: "Renombrar",
      root: "Raíz",
      folder: "Carpeta",
      loadMore: "Cargar más",
      darkMode: "Modo oscuro",
      lightMode: "Modo claro",
      filter: "Filtro",
      textFilter: "Filtro de texto",
      selectFilter: "Seleccionar filtro",
      clearFilter: "Limpiar filtro",
      columns: {
        username: "Nombre de usuario",
        firstName: "Nombre",
        lastName: "Apellido",
        email: "Email",
        status: "Estado",
        groups: "Grupos",
        created: "Creado",
        modified: "Modificado",
        actions: "Acciones",
      },
      noGroups: "Sin grupos",
      select: "Seleccionar",
      moreInfo: "Más información",
    },
    users: {
      title: "Gestión de usuarios",
      search: "Buscar usuarios",
      description: "Gestiona los usuarios del sistema y su acceso",
      form: {
        fields: {
          given_name: {
            label: "Nombre",
            tooltip: "Ingresa el nombre del usuario",
            errors: {
              required: "El nombre es requerido",
            },
          },
          family_name: {
            label: "Apellido",
            tooltip: "Ingresa el apellido del usuario",
            errors: {
              required: "El apellido es requerido",
            },
          },
          email: {
            label: "Email",
            tooltip: "Ingresa la dirección de email del usuario",
            errors: {
              required: "El email es requerido",
              invalid: "Dirección de email inválida",
            },
          },
          enabled: {
            label: "Habilitado",
            tooltip: "Habilita o deshabilita el usuario",
            errors: {
              required: "Habilitado es requerido",
            },
          },
          roles: {
            label: "Roles",
            tooltip: "Selecciona los roles para el usuario",
            errors: {
              required: "Los roles son requeridos",
            },
          },
          email_verified: {
            label: "Email verificado",
            tooltip: "Indica si el email del usuario ha sido verificado",
            errors: {
              required: "La verificación de email es requerida",
            },
          },
        },
      },
    },
    roles: {
      title: "Gestión de roles",
      description: "Gestiona los roles del sistema y sus permisos",
      admin: "Administrador",
      editor: "Editor",
      viewer: "Visualizador",
      actions: {
        addRole: "Agregar rol",
      },
    },
    columns: {
      username: "Nombre de usuario",
      firstName: "Nombre",
      lastName: "Apellido",
      email: "Email",
      status: "Estado",
      groups: "Grupos",
      created: "Creado",
      modified: "Modificado",
      actions: "Acciones",
    },
    actions: {
      addUser: "Agregar usuario",
      edit: "Editar usuario",
      delete: "Eliminar usuario",
      activate: "Activar usuario",
      deactivate: "Desactivar usuario",
    },
    status: {
      active: "Activo",
      inactive: "Inactivo",
    },
    errors: {
      loadFailed: "Error al cargar usuarios",
      saveFailed: "Error al guardar usuario",
      deleteFailed: "Error al eliminar usuario",
    },
    navigation: {
      home: "Inicio",
      collections: "Colecciones",
      settings: "Configuración",
    },
    home: {
      welcome: "Bienvenido a Media Lake",
      description:
        "Gestiona y organiza tus archivos multimedia de manera eficiente",
      statistics: "Estadísticas",
      collections: "Colecciones",
      sharedCollections: "Colecciones compartidas",
      favorites: "Favoritos",
      smartFolders: "Carpetas inteligentes",
      connectedStorage: "Almacenamiento conectado",
      sharing: "Compartir",
      comingSoon: "Próximamente",
    },
    notifications: {
      "Pipeline Complete": "Pipeline completado",
      "Asset processing pipeline completed successfully":
        "El pipeline de procesamiento de activos se completó exitosamente",
      "Storage Warning": "Advertencia de almacenamiento",
      "Storage capacity reaching 80%":
        "La capacidad de almacenamiento está llegando al 80%",
      "Pipeline Failed": "Pipeline falló",
      "Video processing pipeline failed":
        "El pipeline de procesamiento de video falló",
    },
    modal: {
      confirmDelete: "¿Estás seguro de que quieres eliminar este elemento?",
      confirmAction: "¿Estás seguro de que quieres realizar esta acción?",
      error: "Ocurrió un error",
      success: "Operación completada exitosamente",
    },
    executions: {
      title: "Ejecuciones de pipeline",
      description: "Monitorea y gestiona tus ejecuciones de pipeline",
      searchPlaceholder: "Buscar ejecuciones de pipeline...",
      columns: {
        pipelineName: "Nombre del pipeline",
        status: "Estado",
        startTime: "Hora de inicio",
        endTime: "Hora de fin",
        duration: "Duración",
        actions: "Acciones",
      },
      status: {
        succeeded: "Exitoso",
        failed: "Falló",
        running: "Ejecutándose",
        timedOut: "Tiempo agotado",
        aborted: "Abortado",
      },
      actions: {
        retryFromCurrent: "Reintentar desde la posición actual",
        retryFromStart: "Reintentar desde el inicio",
        viewDetails: "Ver detalles",
      },
      pagination: {
        page: "Página {{page}} de {{total}}",
        showEntries: "Mostrar {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "Filtrar por nombre",
      },
      error: {
        loading: "Error al cargar objetos S3: {{message}}",
      },
      file: {
        info: "Tamaño: {{size}} • Clase de almacenamiento: {{storageClass}} • Modificado: {{modified}}",
      },
      menu: {
        rename: "Renombrar",
        delete: "Eliminar",
      },
    },
    assets: {
      title: "Activos",
      connectedStorage: "Almacenamiento conectado",
    },
    metadata: {
      title: "Próximamente",
      description:
        "Estamos trabajando para traerte capacidades de gestión de metadatos. ¡Mantente atento!",
    },
    pipelines: {
      title: "Pipelines",
      description: "Gestiona tus pipelines de medios y metadatos",
      searchPlaceholder: "Buscar pipelines...",
      actions: {
        create: "Agregar nuevo pipeline",
        deploy: "Desplegar pipeline de imágenes",
        addNew: "Agregar nuevo pipeline",
        viewAll: "Ver todos los pipelines",
      },
      search: "Buscar pipelines",
      deploy: "Desplegar pipeline de imágenes",
      addNew: "Agregar nuevo pipeline",
      columns: {
        name: "Nombre",
        creationDate: "Fecha de creación",
        system: "Sistema",
        type: "Tipo",
        actions: "Acciones",
      },
      editor: {
        title: "Editor de pipeline",
        save: "Guardar pipeline",
        validate: "Validar pipeline",
        sidebar: {
          title: "Nodos",
          dragNodes: "Arrastra nodos al lienzo",
          loading: "Cargando nodos...",
          error: "Error al cargar nodos",
        },
        node: {
          configure: "Configurar {{type}}",
          delete: "Eliminar nodo",
          edit: "Editar nodo",
        },
        edge: {
          title: "Editar etiqueta de conexión",
          label: "Etiqueta de conexión",
          delete: "Eliminar conexión",
        },
        modals: {
          error: {
            title: "Error",
            incompatibleNodes:
              "La salida del nodo anterior no es compatible con la entrada del nodo de destino.",
            validation: "La validación del pipeline falló",
          },
          delete: {
            title: "Eliminar pipeline",
            message:
              "¿Estás seguro de que quieres eliminar este pipeline? Esta acción no se puede deshacer.",
            confirm:
              "Escribe el nombre del pipeline para confirmar la eliminación:",
          },
        },
        controls: {
          undo: "Deshacer",
          redo: "Rehacer",
          zoomIn: "Acercar",
          zoomOut: "Alejar",
          fitView: "Ajustar vista",
          lockView: "Bloquear vista",
        },
        notifications: {
          saved: "Pipeline guardado exitosamente",
          validated: "Validación del pipeline exitosa",
          error: {
            save: "Error al guardar el pipeline",
            validation: "La validación del pipeline falló",
            incompatibleNodes: "Conexión de nodo incompatible",
          },
        },
      },
    },
    integrations: {
      title: "Integraciones",
      description: "Gestiona tus integraciones y conexiones",
      addIntegration: "Agregar integración",
      selectIntegration: "Seleccionar integración",
      selectProvider: "Seleccionar proveedor",
      configureIntegration: "Configurar integración",
      deleteConfirmation: {
        title: "Eliminar integración",
        message: "¿Estás seguro de que quieres eliminar esta integración?",
        warning:
          "Advertencia: Eliminar esta integración puede romper pipelines que la están usando.",
      },
      form: {
        title: "Agregar integración",
        fields: {
          nodeId: {
            label: "Integración",
            tooltip: "Selecciona un proveedor de integración",
            errors: {
              required: "La selección de integración es requerida",
            },
          },
          description: {
            label: "Descripción",
            tooltip: "Proporciona una descripción para esta integración",
            helper: "Breve descripción de esta integración",
            errors: {
              required: "La descripción es requerida",
            },
          },
          environmentId: {
            label: "Entorno",
            tooltip: "Selecciona el entorno para esta integración",
            errors: {
              required: "La selección de entorno es requerida",
            },
          },
          enabled: {
            label: "Habilitado",
            tooltip: "Habilita o deshabilita esta integración",
            errors: {
              required: "Habilitado es requerido",
            },
          },
          auth: {
            type: {
              label: "Tipo de autenticación",
              tooltip: "Selecciona el método de autenticación",
              options: {
                awsIam: "AWS IAM",
                apiKey: "Clave API",
              },
              errors: {
                required: "El tipo de autenticación es requerido",
              },
            },
            credentials: {
              apiKey: {
                label: "Clave API",
                tooltip: "Ingresa tu clave API",
                helper: "Clave API para autenticación con el servicio",
                errors: {
                  required: "La clave API es requerida",
                },
              },
              iamRole: {
                label: "Rol IAM",
                tooltip: "Ingresa el ARN del rol IAM",
                errors: {
                  required: "El rol IAM es requerido",
                },
              },
            },
          },
        },
        search: {
          placeholder: "Buscar integraciones",
        },

        errors: {
          required: "Este campo es requerido",
          nodeId: {
            unrecognized_keys: "Selección de integración inválida",
          },
        },
      },
      columns: {
        nodeName: "Nombre del nodo",
        environment: "Entorno",
        createdDate: "Fecha de creación",
        modifiedDate: "Fecha de modificación",
        actions: "Acciones",
      },

      settings: {
        environments: {
          title: "Entornos",
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "Agregar grupo",
      editGroup: "Editar grupo",
      deleteGroup: "Eliminar grupo",
      createGroup: "Crear grupo",
      manageGroups: "Gestionar grupos",
    },
  },
  permissionSets: {
    noAssignments: "Sin conjuntos de permisos",
    actions: {
      addPermissionSet: "Agregar conjunto de permisos",
      editPermissionSet: "Editar conjunto de permisos",
      deletePermissionSet: "Eliminar conjunto de permisos",
    },
  },
};
