export default {
  languages: {
    english: "Inglês",
    german: "Alemão",
    portuguese: "Português",
    french: "Francês",
    chinese: "Chinês",
    hindi: "Hindi",
    arabic: "Árabe",
    hebrew: "Hebraico",
    japanese: "Japonês",
    korean: "Coreano",
    spanish: "Espanhol",
  },
  assetsPage: {
    title: "Ativos",
    connectors: "Conectores",
    selectConnector: "Selecione um conector",
  },
  assetExplorer: {
    noConnectorSelected: "Selecione um conector para visualizar os ativos",
    noAssetsFound: "Nenhum ativo encontrado para este conector",
    noIndexedAssets:
      'Nenhum ativo indexado foi encontrado para este conector com o bucket "{{bucketName}}".',
    loadingAssets: "Carregando ativos...",
    menu: {
      rename: "Renomear",
      share: "Compartilhar",
      download: "Baixar",
    },
    deleteDialog: {
      title: "Confirmar exclusão",
      description:
        "Tem certeza de que deseja excluir este ativo? Esta ação não pode ser desfeita.",
      cancel: "Cancelar",
      confirm: "Excluir",
    },
  },
  sidebar: {
    menu: {
      home: "Início",
      assets: "Ativos",
      pipelines: "Pipelines",
      pipelineExecutions: "Execuções de Pipeline",
      settings: "Configurações",
    },
    submenu: {
      system: "Configurações do Sistema",
      connectors: "Conectores",
      userManagement: "Gerenciamento de Usuários",
      roles: "Funções",
      integrations: "Integrações",
      environments: "Ambientes",
    },
  },
  profile: {
    title: "Perfil",
    description: "Gerencie suas configurações e preferências de conta",
    changePhoto: "Alterar Foto",
    jobTitle: "Cargo",
    organization: "Organização",
    preferences: "Preferências",
    timezone: "Fuso Horário",
    emailNotifications: "Notificações por Email",
    pushNotifications: "Notificações Push",
    changePassword: "Alterar Senha",
    twoFactorAuth: "Autenticação de Dois Fatores",
    appearance: "Aparência",
  },
  app: {
    loading: "Carregando...",
    errors: {
      loadingConfig: "Erro ao carregar configuração AWS:",
      loadingUserAttributes: "Erro ao carregar atributos do usuário:",
      signingOut: "Erro ao sair:",
    },
    navigation: {
      preventedDuplicate: "Navegação duplicada impedida para",
      navigating: "Navegando de",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "Pesquisa Semântica",
    filters: {
      dateRange: "Intervalo de Data",
      contentType: "Tipo de Conteúdo",
      storageLocation: "Local de Armazenamento",
      comingSoon: "Mais filtros em breve...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "Uso de Armazenamento",
      apiUsage: "Uso de API",
      activeUsers: "Usuários Ativos",
      systemLoad: "Carga do Sistema",
    },
    errors: {
      userDeletionNotImplemented:
        "A exclusão de usuário ainda não foi implementada.",
      userCreationNotImplemented:
        "A criação de usuário ainda não foi implementada.",
      userEditingNotImplemented:
        "A edição de usuário ainda não foi implementada.",
      analyticsExportNotImplemented:
        "A exportação de análises ainda não foi implementada.",
      systemResetNotImplemented:
        "A redefinição do sistema ainda não foi implementada.",
    },
    columns: {
      lastActive: "Último Acesso",
    },
    buttons: {
      exportAnalytics: "Exportar Análises",
      resetSystem: "Redefinir Sistema",
    },
  },
  common: {
    select: "Selecionar",
    back: "Voltar",
    search: "Pesquisar",
    profile: "Perfil",
    logout: "Sair",
    theme: "Tema",
    close: "Fechar",
    refresh: "Atualizar",
    cancel: "Cancelar",
    save: "Salvar",
    loading: "Carregando...",
    loadMore: "Carregar Mais",
    tableDensity: "Densidade da Tabela",
    moreInfo: "Mais informações",
    error: "Erro",
    language: "Idioma",
    delete: "Excluir",
    create: "Criar",
    actions: {
      add: "Adicionar",
    },
    columns: {
      username: "Nome de Usuário",
      firstName: "Nome",
      lastName: "Sobrenome",
      email: "Email",
      status: "Status",
      groups: "Grupos",
      created: "Criado",
      modified: "Modificado",
      actions: "Ações",
    },
    status: {
      active: "Ativo",
      inactive: "Inativo",
    },
  },
  pipelines: {
    title: "Pipelines",
    description: "Gerencie seus pipelines de mídia e metadados",
    searchPlaceholder: "Pesquisar pipelines...",
    actions: {
      create: "Adicionar Novo Pipeline",
      viewAll: "Ver Todos os Pipelines",
      import: "Importar Pipeline",
    },
  },
  users: {
    title: "Gerenciamento de Usuários",
    description: "Gerencie os usuários do sistema e seus acessos",
    actions: {
      addUser: "Adicionar Usuário",
    },
    form: {
      title: {
        add: "Adicionar Usuário",
      },
      fields: {
        given_name: {
          label: "Nome",
          tooltip: "Digite o primeiro nome do usuário",
          helper: "",
        },
        family_name: {
          label: "Sobrenome",
          tooltip: "Digite o sobrenome do usuário",
          helper: "",
        },
        email: {
          label: "Email",
          tooltip: "Digite o endereço de email do usuário",
          helper: "",
        },
        roles: {
          label: "Funções",
          tooltip: "Selecione as funções para o usuário",
          options: {
            Admin: "Administrador",
            Editor: "Editor",
            Viewer: "Visualizador",
          },
        },
        email_verified: {
          label: "Email Verificado",
          tooltip: "Indique se o email do usuário foi verificado",
        },
        enabled: {
          label: "Habilitado",
          tooltip: "Ative ou desative o usuário",
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
    title: "Gerenciamento de Funções",
    description: "Gerencie as funções do sistema e suas permissões",
    actions: {
      addRole: "Adicionar Função",
    },
  },
  integrations: {
    title: "Integrações",
    description: "Gerencie suas integrações e conexões",
    addIntegration: "Adicionar Integração",
    selectProvider: "Selecionar Integração",
    selectIntegration: "Selecionar Integração",
    configureIntegration: "Configurar Integração",
    form: {
      title: "Adicionar Integração",
      search: {
        placeholder: "Pesquisar integrações",
      },
      fields: {
        nodeId: {
          label: "Integração",
          tooltip: "Selecione um provedor de integração",
          errors: {
            required: "Seleção de integração é obrigatória",
          },
        },
        description: {
          label: "Descrição",
          tooltip: "Forneça uma descrição para esta integração",
          helper: "Breve descrição desta integração",
          errors: {
            required: "Descrição é obrigatória",
          },
        },
        environmentId: {
          label: "Ambiente",
          tooltip: "Selecione o ambiente para esta integração",
          errors: {
            required: "Seleção de ambiente é obrigatória",
          },
        },
        enabled: {
          label: "Habilitado",
          tooltip: "Ative ou desative esta integração",
          errors: {
            required: "Habilitado é obrigatório",
          },
        },
        auth: {
          type: {
            label: "Tipo de Autenticação",
            tooltip: "Selecione o método de autenticação",
            options: {
              awsIam: "AWS IAM",
              apiKey: "Chave de API",
            },
            errors: {
              required: "Tipo de autenticação é obrigatório",
            },
          },
          credentials: {
            apiKey: {
              label: "Chave de API",
              tooltip: "Digite sua chave de API",
              helper: "Chave de API para autenticação com o serviço",
              errors: {
                required: "Chave de API é obrigatória",
              },
            },
            iamRole: {
              label: "Função IAM",
              tooltip: "Digite o ARN da função IAM",
              errors: {
                required: "Função IAM é obrigatória",
              },
            },
          },
        },
      },
      errors: {
        required: "Este campo é obrigatório",
        nodeId: {
          unrecognized_keys: "Seleção de integração inválida",
        },
      },
    },
  },
  settings: {
    environments: {
      title: "Ambientes",
      description: "Gerencie os ambientes do sistema",
      addButton: "Adicionar Ambiente",
      searchPlaceholder: "Pesquisar ambientes",
      createTitle: "Criar Ambiente",
      editTitle: "Editar Ambiente",
      deleteSuccess: "Ambiente excluído com sucesso",
      deleteError: "Erro ao excluir ambiente",
      createSuccess: "Ambiente criado com sucesso",
      updateSuccess: "Ambiente atualizado com sucesso",
      submitError: "Erro ao salvar ambiente",
      search: "Pesquisar ambientes",
      columns: {
        name: "Nome",
        region: "Região",
        status: "Status",
        team: "Equipe",
        costCenter: "Centro de Custo",
        createdAt: "Criado em",
        updatedAt: "Atualizado em",
        actions: "Ações",
      },
      status: {
        active: "Ativo",
        disabled: "Desativado",
      },
      actions: {
        edit: "Editar Ambiente",
        delete: "Excluir Ambiente",
      },
      form: {
        name: "Nome do Ambiente",
        region: "Região",
        status: {
          name: "Status",
          active: "Ativo",
          disabled: "Desativado",
        },
        costCenter: "Centro de Custo",
        team: "Equipe",
      },
    },
    systemSettings: {
      title: "Configurações do Sistema",
      tabs: {
        search: "Pesquisa",
        notifications: "Notificações",
        security: "Segurança",
        performance: "Desempenho",
      },
      search: {
        title: "Configuração de Pesquisa",
        description:
          "Configure o provedor de pesquisa para recursos avançados de pesquisa em seus ativos de mídia.",
        provider: "Provedor de Pesquisa:",
        configureProvider: "Configurar Provedor de Pesquisa",
        editProvider: "Editar Provedor",
        resetProvider: "Redefinir Provedor",
        providerDetails: "Detalhes do Provedor",
        providerName: "Nome do Provedor",
        apiKey: "Chave de API",
        endpoint: "URL do Endpoint (Opcional)",
        enabled: "Pesquisa Ativada",
        noProvider: "Nenhum provedor de pesquisa configurado.",
        configurePrompt:
          "Configure o Twelve Labs para habilitar recursos de pesquisa.",
      },
      notifications: {
        title: "Configurações de Notificações",
        comingSoon: "Configurações de notificações em breve.",
      },
      security: {
        title: "Configurações de Segurança",
        comingSoon: "Configurações de segurança em breve.",
      },
      performance: {
        title: "Configurações de Desempenho",
        comingSoon: "Configurações de desempenho em breve.",
      },
    },
  },
  executions: {
    title: "Execuções de Pipeline",
    description: "Monitore e gerencie suas execuções de pipeline",
    searchPlaceholder: "Pesquisar execuções de pipeline...",
    columns: {
      pipelineName: "Nome do Pipeline",
      status: "Status",
      startTime: "Hora de Início",
      endTime: "Hora de Término",
      duration: "Duração",
      actions: "Ações",
    },
    actions: {
      retryFromCurrent: "Tentar novamente a partir da posição atual",
      retryFromStart: "Tentar novamente desde o início",
      viewDetails: "Ver Detalhes",
    },
  },
  translation: {
    common: {
      actions: {
        add: "Adicionar",
        edit: "Editar",
        delete: "Excluir",
        activate: "Ativar",
        deactivate: "Desativar",
        create: "Criar",
      },
      tableDensity: "Densidade da Tabela",
      theme: "Tema",
      back: "Voltar",
      loading: "Carregando...",
      error: "Algo deu errado",
      save: "Salvar",
      cancel: "Cancelar",
      delete: "Excluir",
      edit: "Editar",
      search: "Pesquisar",
      profile: "Perfil",
      filterColumn: "Filtrar",
      searchValue: "Pesquisar",
      logout: "Sair",
      language: "Idioma",
      alerts: "Alertas",
      warnings: "Avisos",
      notifications: "Notificações",
      searchPlaceholder: "Pesquisar ou use chave:valor...",
      close: "Fechar",
      success: "Sucesso",
      refresh: "Atualizar",
      previous: "Anterior",
      next: "Próximo",
      show: "Mostrar",
      all: "Todos",
      status: "Status",
      rename: "Renomear",
      root: "Raiz",
      folder: "Pasta",
      loadMore: "Carregar Mais",
      darkMode: "Modo Escuro",
      lightMode: "Modo Claro",
      filter: "Filtrar",
      textFilter: "Filtro de Texto",
      selectFilter: "Filtro de Seleção",
      clearFilter: "Limpar Filtro",
      columns: "Colunas",
      noGroups: "Sem Grupos",
      select: "Selecionar",
      moreInfo: "Mais informações",
    },
    users: {
      title: "Gerenciamento de Usuários",
      search: "Pesquisar usuários",
      description: "Gerencie os usuários do sistema e seus acessos",
      form: {
        fields: {
          given_name: {
            label: "Nome",
            tooltip: "Digite o primeiro nome do usuário",
            errors: {
              required: "Nome é obrigatório",
            },
          },
          family_name: {
            label: "Sobrenome",
            tooltip: "Digite o sobrenome do usuário",
            errors: {
              required: "Sobrenome é obrigatório",
            },
          },
          email: {
            label: "Email",
            tooltip: "Digite o endereço de email do usuário",
            errors: {
              required: "Email é obrigatório",
              invalid: "Endereço de email inválido",
            },
          },
          enabled: {
            label: "Habilitado",
            tooltip: "Ative ou desative o usuário",
            errors: {
              required: "Habilitado é obrigatório",
            },
          },
          roles: {
            label: "Funções",
            tooltip: "Selecione as funções para o usuário",
            errors: {
              required: "Funções são obrigatórias",
            },
          },
          email_verified: {
            label: "Email Verificado",
            tooltip: "Indique se o email do usuário foi verificado",
            errors: {
              required: "Verificação de email é obrigatória",
            },
          },
        },
      },
    },
    roles: {
      title: "Gerenciamento de Funções",
      description: "Gerencie as funções do sistema e suas permissões",
      admin: "Administrador",
      editor: "Editor",
      viewer: "Visualizador",
      actions: {
        addRole: "Adicionar Função",
      },
    },
    columns: {
      username: "Nome de Usuário",
      firstName: "Nome",
      lastName: "Sobrenome",
      email: "Email",
      status: "Status",
      groups: "Grupos",
      created: "Criado",
      modified: "Modificado",
      actions: "Ações",
    },
    actions: {
      addUser: "Adicionar Usuário",
      edit: "Editar Usuário",
      delete: "Excluir Usuário",
      activate: "Ativar Usuário",
      deactivate: "Desativar Usuário",
    },
    status: {
      active: "Ativo",
      inactive: "Inativo",
    },
    errors: {
      loadFailed: "Falha ao carregar os usuários",
      saveFailed: "Falha ao salvar o usuário",
      deleteFailed: "Falha ao excluir o usuário",
    },
    navigation: {
      home: "Início",
      collections: "Coleções",
      settings: "Configurações",
    },
    home: {
      welcome: "Bem-vindo ao Media Lake",
      description:
        "Gerencie e organize seus arquivos de mídia de forma eficiente",
      statistics: "Estatísticas",
      collections: "Coleções",
      sharedCollections: "Coleções Compartilhadas",
      favorites: "Favoritos",
      smartFolders: "Pastas Inteligentes",
      connectedStorage: "Armazenamento Conectado",
      sharing: "Compartilhamento",
      comingSoon: "Em breve",
    },
    notifications: {
      "Pipeline Complete": "Pipeline Completo",
      "Asset processing pipeline completed successfully":
        "Pipeline de processamento de ativos concluído com sucesso",
      "Storage Warning": "Aviso de Armazenamento",
      "Storage capacity reaching 80%":
        "Capacidade de armazenamento atingindo 80%",
      "Pipeline Failed": "Pipeline Falhou",
      "Video processing pipeline failed":
        "Pipeline de processamento de vídeo falhou",
    },
    modal: {
      confirmDelete: "Tem certeza de que deseja excluir este item?",
      confirmAction: "Tem certeza de que deseja realizar esta ação?",
      error: "Ocorreu um erro",
      success: "Operação concluída com sucesso",
    },
    executions: {
      title: "Execuções de Pipeline",
      searchPlaceholder: "Pesquisar execuções de pipeline...",
      description: "Monitore e gerencie suas execuções de pipeline",
      columns: {
        pipelineName: "Nome do Pipeline",
        status: "Status",
        startTime: "Hora de Início",
        endTime: "Hora de Término",
        duration: "Duração",
        actions: "Ações",
      },
      status: {
        succeeded: "Concluído",
        failed: "Falhou",
        running: "Em Execução",
        timedOut: "Tempo Esgotado",
        aborted: "Abortado",
      },
      actions: {
        retryFromCurrent: "Tentar novamente a partir da posição atual",
        retryFromStart: "Tentar novamente desde o início",
        viewDetails: "Ver Detalhes",
      },
      pagination: {
        page: "Página {{page}} de {{total}}",
        showEntries: "Mostrar {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "Filtrar por nome",
      },
      error: {
        loading: "Erro ao carregar objetos S3: {{message}}",
      },
      file: {
        info: "Tamanho: {{size}} • Classe de Armazenamento: {{storageClass}} • Modificado: {{modified}}",
      },
      menu: {
        rename: "Renomear",
        delete: "Excluir",
      },
    },
    assets: {
      title: "Ativos",
      connectedStorage: "Armazenamento Conectado",
    },
    metadata: {
      title: "Em Breve",
      description:
        "Estamos trabalhando para trazer recursos de gerenciamento de metadados. Fique ligado!",
    },
    pipelines: {
      title: "Pipelines",
      searchPlaceholder: "Pesquisar pipelines...",
      actions: {
        create: "Adicionar Novo Pipeline",
        deploy: "Implantar Pipeline de Imagens",
        addNew: "Adicionar Novo Pipeline",
        viewAll: "Ver Todos os Pipelines",
      },
      description: "Gerencie seus pipelines de mídia e metadados",
      search: "Pesquisar pipelines",
      deploy: "Implantar Pipeline de Imagens",
      addNew: "Adicionar Novo Pipeline",
      columns: {
        name: "Nome",
        creationDate: "Data de Criação",
        system: "Sistema",
        type: "Tipo",
        actions: "Ações",
      },
      editor: {
        title: "Editor de Pipeline",
        save: "Salvar Pipeline",
        validate: "Validar Pipeline",
        sidebar: {
          title: "Nós",
          dragNodes: "Arraste os nós para a tela",
          loading: "Carregando nós...",
          error: "Erro ao carregar nós",
        },
        node: {
          configure: "Configurar {{type}}",
          delete: "Excluir Nó",
          edit: "Editar Nó",
        },
        edge: {
          title: "Editar Rótulo da Conexão",
          label: "Rótulo da Conexão",
          delete: "Excluir Conexão",
        },
        modals: {
          error: {
            title: "Erro",
            incompatibleNodes:
              "A saída do nó anterior não é compatível com a entrada do nó de destino.",
            validation: "Validação do pipeline falhou",
          },
          delete: {
            title: "Excluir Pipeline",
            message:
              "Tem certeza de que deseja excluir este pipeline? Esta ação não pode ser desfeita.",
            confirm: "Digite o nome do pipeline para confirmar a exclusão:",
          },
        },
        controls: {
          undo: "Desfazer",
          redo: "Refazer",
          zoomIn: "Aumentar Zoom",
          zoomOut: "Diminuir Zoom",
          fitView: "Ajustar Visualização",
          lockView: "Bloquear Visualização",
        },
        notifications: {
          saved: "Pipeline salvo com sucesso",
          validated: "Validação do pipeline bem-sucedida",
          error: {
            save: "Falha ao salvar pipeline",
            validation: "Validação do pipeline falhou",
            incompatibleNodes: "Conexão de nó incompatível",
          },
        },
      },
    },
    integrations: {
      title: "Integrações",
      description: "Gerencie suas integrações e conexões",
      addIntegration: "Adicionar Integração",
      selectIntegration: "Selecionar Integração",
      selectProvider: "Selecionar Provedor",
      configureIntegration: "Configurar Integração",
      columns: {
        nodeName: "Nome do Nó",
        environment: "Ambiente",
        createdDate: "Data de Criação",
        modifiedDate: "Data de Modificação",
        actions: "Ações",
      },
      form: {
        title: "Adicionar Integração",
        fields: {
          nodeId: {
            label: "Integração",
            tooltip: "Selecione um provedor de integração",
            errors: {
              required: "Seleção de integração é obrigatória",
            },
          },
          description: {
            label: "Descrição",
            tooltip: "Forneça uma descrição para esta integração",
            errors: {
              required: "Descrição é obrigatória",
            },
          },
          environmentId: {
            label: "Ambiente",
            tooltip: "Selecione o ambiente para esta integração",
            errors: {
              required: "Seleção de ambiente é obrigatória",
            },
          },
          enabled: {
            label: "Habilitado",
            tooltip: "Ative ou desative esta integração",
            errors: {
              required: "Habilitado é obrigatório",
            },
          },
          auth: {
            type: {
              label: "Tipo de Autenticação",
              tooltip: "Selecione o método de autenticação",
              options: {
                awsIam: "AWS IAM",
                apiKey: "Chave de API",
              },
              errors: {
                required: "Tipo de autenticação é obrigatório",
              },
            },
            credentials: {
              apiKey: {
                label: "Chave de API",
                tooltip: "Digite sua chave de API",
                errors: {
                  required: "Chave de API é obrigatória",
                },
              },
              iamRole: {
                label: "Função IAM",
                tooltip: "Digite o ARN da função IAM",
                errors: {
                  required: "Função IAM é obrigatória",
                },
              },
            },
            settings: {
              environments: {
                title: "Ambientes",
              },
            },
          },
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "Adicionar Grupo",
      editGroup: "Editar Grupo",
      deleteGroup: "Excluir Grupo",
      createGroup: "Criar Grupo",
      manageGroups: "Gerenciar Grupos",
    },
  },
  permissionSets: {
    noAssignments: "Nenhum conjunto de permissões",
    actions: {
      addPermissionSet: "Adicionar Conjunto de Permissões",
      editPermissionSet: "Editar Conjunto de Permissões",
      deletePermissionSet: "Excluir Conjunto de Permissões",
    },
  },
};
