export default {
    integrations: {
      selectProvider: 'Selecionar Integração',
      selectIntegration: 'Selecionar Integração',
      configureIntegration: 'Configurar Integração',
      form: {
        title: 'Adicionar Integração',
        fields: {
          nodeId: {
            label: 'Integração',
            tooltip: 'Selecione um provedor de integração',
            errors: {
              required: 'Seleção de integração é obrigatória'
            }
          },
          description: {
            label: 'Descrição',
            tooltip: 'Forneça uma descrição para esta integração',
            errors: {
              required: 'Descrição é obrigatória'
            }
          },
          environmentId: {
            label: 'Ambiente',
            tooltip: 'Selecione o ambiente para esta integração',
            errors: {
              required: 'Seleção de ambiente é obrigatória'
            }
          },
          enabled: {
            label: 'Habilitado',
            tooltip: 'Ative ou desative esta integração',
            errors: {
              required: 'Habilitado é obrigatório'
            }
          },
          auth: {
            type: {
              label: 'Tipo de Autenticação',
              tooltip: 'Selecione o método de autenticação',
              options: {
                awsIam: 'AWS IAM',
                apiKey: 'Chave de API'
              },
              errors: {
                required: 'Tipo de autenticação é obrigatório'
              }
            },
            credentials: {
              apiKey: {
                label: 'Chave de API',
                tooltip: 'Digite sua chave de API',
                errors: {
                  required: 'Chave de API é obrigatória'
                }
              },
              iamRole: {
                label: 'Função IAM',
                tooltip: 'Digite o ARN da função IAM',
                errors: {
                  required: 'Função IAM é obrigatória'
                }
              }
            }
          }
        },
        errors: {
          required: 'Este campo é obrigatório',
          nodeId: {
            unrecognized_keys: 'Seleção de integração inválida'
          }
        }
      }
    },
    common: {
      select: 'Selecionar',
      back: 'Voltar',
      actions: {
        add: 'Adicionar'
      }
    },
    translation: {
      common: {
        actions: {
          add: 'Adicionar',
          edit: 'Editar',
          delete: 'Excluir',
          activate: 'Ativar',
          deactivate: 'Desativar',
          create: 'Criar'
        },
        tableDensity: 'Densidade da Tabela',
        theme: 'Tema',
        back: 'Voltar',
        loading: 'Carregando...',
        error: 'Algo deu errado',
        save: 'Salvar',
        cancel: 'Cancelar',
        delete: 'Excluir',
        edit: 'Editar',
        search: 'Pesquisar',
        profile: 'Perfil',
        filterColumn: 'Filtrar',
        searchValue: 'Pesquisar',
        logout: 'Sair',
        language: 'Idioma',
        alerts: 'Alertas',
        warnings: 'Avisos',
        notifications: 'Notificações',
        searchPlaceholder: 'Pesquisar ou use chave:valor...',
        close: 'Fechar',
        success: 'Sucesso',
        refresh: 'Atualizar',
        previous: 'Anterior',
        next: 'Próximo',
        show: 'Mostrar',
        all: 'Todos',
        status: 'Status',
        rename: 'Renomear',
        root: 'Raiz',
        folder: 'Pasta',
        loadMore: 'Carregar Mais',
        darkMode: 'Modo Escuro',
        lightMode: 'Modo Claro',
        filter: 'Filtrar',
        textFilter: 'Filtro de Texto',
        selectFilter: 'Filtro de Seleção',
        clearFilter: 'Limpar Filtro',
        columns: 'Colunas',
        noGroups: 'Sem Grupos',
        select: 'Selecionar',
        moreInfo: 'Mais informações'
      },
      users: {
        title: 'Gerenciamento de Usuários',
        search: 'Pesquisar usuários',
        description: 'Gerencie os usuários do sistema e seus acessos',
        form: {
          fields: {
            given_name: {
              label: 'Nome',
              tooltip: "Digite o primeiro nome do usuário",
              errors: {
                required: 'Nome é obrigatório'
              }
            },
            family_name: {
              label: 'Sobrenome',
              tooltip: "Digite o sobrenome do usuário",
              errors: {
                required: 'Sobrenome é obrigatório'
              }
            },
            email: {
              label: 'Email',
              tooltip: "Digite o endereço de email do usuário",
              errors: {
                required: 'Email é obrigatório',
                invalid: 'Endereço de email inválido'
              }
            },
            enabled: {
              label: 'Habilitado',
              tooltip: 'Ative ou desative o usuário',
              errors: {
                required: 'Habilitado é obrigatório'
              }
            },
            roles: {
              label: 'Funções',
              tooltip: 'Selecione as funções para o usuário',
              errors: {
                required: 'Funções são obrigatórias'
              }
            },
            email_verified: {
              label: 'Email Verificado',
              tooltip: "Indique se o email do usuário foi verificado",
              errors: {
                required: 'Verificação de email é obrigatória'
              }
            }
          }
        }
      },
      roles: {
        title: 'Gerenciamento de Funções',
        description: 'Gerencie as funções do sistema e suas permissões',
        admin: 'Administrador',
        editor: 'Editor',
        viewer: 'Visualizador',
        actions: {
          addRole: 'Adicionar Função'
        }
      },
      columns: {
        username: 'Nome de Usuário',
        firstName: 'Nome',
        lastName: 'Sobrenome',
        email: 'Email',
        status: 'Status',
        groups: 'Grupos',
        created: 'Criado',
        modified: 'Modificado',
        actions: 'Ações'
      },
      actions: {
        addUser: 'Adicionar Usuário',
        edit: 'Editar Usuário',
        delete: 'Excluir Usuário',
        activate: 'Ativar Usuário',
        deactivate: 'Desativar Usuário'
      },
      status: {
        active: 'Ativo',
        inactive: 'Inativo'
      },
      errors: {
        loadFailed: 'Falha ao carregar os usuários',
        saveFailed: 'Falha ao salvar o usuário',
        deleteFailed: 'Falha ao excluir o usuário'
      },
      navigation: {
        home: 'Início',
        collections: 'Coleções',
        settings: 'Configurações'
      },
      home: {
        welcome: 'Bem-vindo ao MediaLake',
        description: 'Gerencie e organize seus arquivos de mídia de forma eficiente',
        statistics: 'Estatísticas',
        collections: 'Coleções',
        sharedCollections: 'Coleções Compartilhadas',
        favorites: 'Favoritos',
        smartFolders: 'Pastas Inteligentes',
        connectedStorage: 'Armazenamento Conectado'
      },
      notifications: {
        'Pipeline Complete': 'Pipeline Completo',
        'Asset processing pipeline completed successfully': 'Pipeline de processamento de ativos concluído com sucesso',
        'Storage Warning': 'Aviso de Armazenamento',
        'Storage capacity reaching 80%': 'Capacidade de armazenamento atingindo 80%',
        'Pipeline Failed': 'Pipeline Falhou',
        'Video processing pipeline failed': 'Pipeline de processamento de vídeo falhou'
      },
      modal: {
        confirmDelete: 'Tem certeza de que deseja excluir este item?',
        confirmAction: 'Tem certeza de que deseja realizar esta ação?',
        error: 'Ocorreu um erro',
        success: 'Operação concluída com sucesso'
      },
      executions: {
        title: 'Execuções de Pipeline',
        searchPlaceholder: 'Pesquisar execuções de pipeline...',
        description: 'Monitore e gerencie suas execuções de pipeline',
        columns: {
          pipelineName: 'Nome do Pipeline',
          status: 'Status',
          startTime: 'Hora de Início',
          endTime: 'Hora de Término',
          duration: 'Duração',
          actions: 'Ações'
        },
        status: {
          succeeded: 'Concluído',
          failed: 'Falhou',
          running: 'Em Execução',
          timedOut: 'Tempo Esgotado',
          aborted: 'Abortado'
        },
        actions: {
          retryFromCurrent: 'Tentar novamente a partir da posição atual',
          retryFromStart: 'Tentar novamente desde o início',
          viewDetails: 'Ver Detalhes'
        },
        pagination: {
          page: 'Página {{page}} de {{total}}',
          showEntries: 'Mostrar {{count}}'
        }
      },
      sidebar: {
        menu: {
          home: 'Início',
          assets: 'Ativos',
          pipelines: 'Pipelines',
          pipelineExecutions: 'Execuções de Pipeline',
          settings: 'Configurações'
        },
        submenu: {
          system: 'Configurações do Sistema',
          connectors: 'Conectores',
          userManagement: 'Gerenciamento de Usuários',
          roles: 'Funções',
          integrations: 'Integrações',
          environments: 'Ambientes'
        }
      },
      s3Explorer: {
        filter: {
          label: 'Filtrar por nome'
        },
        error: {
          loading: 'Erro ao carregar objetos S3: {{message}}'
        },
        file: {
          info: 'Tamanho: {{size}} • Classe de Armazenamento: {{storageClass}} • Modificado: {{modified}}'
        },
        menu: {
          rename: 'Renomear',
          delete: 'Excluir'
        }
      },
      assets: {
        title: 'Ativos',
        connectedStorage: 'Armazenamento Conectado'
      },
      metadata: {
        title: 'Em Breve',
        description: 'Estamos trabalhando para trazer recursos de gerenciamento de metadados. Fique ligado!'
      },
      pipelines: {
        title: 'Pipelines',
        searchPlaceholder: 'Pesquisar pipelines...',
        actions: {
          create: 'Adicionar Novo Pipeline',
          deploy: 'Implantar Pipeline de Imagens',
          addNew: 'Adicionar Novo Pipeline'
        },
        description: 'Gerencie seus pipelines de mídia e metadados',
        search: 'Pesquisar pipelines',
        deploy: 'Implantar Pipeline de Imagens',
        addNew: 'Adicionar Novo Pipeline',
        columns: {
          name: 'Nome',
          creationDate: 'Data de Criação',
          system: 'Sistema',
          type: 'Tipo',
          actions: 'Ações'
        },
        editor: {
          title: 'Editor de Pipeline',
          save: 'Salvar Pipeline',
          validate: 'Validar Pipeline',
          sidebar: {
            title: 'Nós',
            dragNodes: 'Arraste os nós para a tela',
            loading: 'Carregando nós...',
            error: 'Erro ao carregar nós'
          },
          node: {
            configure: 'Configurar {{type}}',
            delete: 'Excluir Nó',
            edit: 'Editar Nó'
          },
          edge: {
            title: 'Editar Rótulo da Conexão',
            label: 'Rótulo da Conexão',
            delete: 'Excluir Conexão'
          },
          modals: {
            error: {
              title: 'Erro',
              incompatibleNodes: 'A saída do nó anterior não é compatível com a entrada do nó de destino.',
              validation: 'Validação do pipeline falhou'
            },
            delete: {
              title: 'Excluir Pipeline',
              message: 'Tem certeza de que deseja excluir este pipeline? Esta ação não pode ser desfeita.',
              confirm: 'Digite o nome do pipeline para confirmar a exclusão:'
            }
          },
          controls: {
            undo: 'Desfazer',
            redo: 'Refazer',
            zoomIn: 'Aumentar Zoom',
            zoomOut: 'Diminuir Zoom',
            fitView: 'Ajustar Visualização',
            lockView: 'Bloquear Visualização'
          },
          notifications: {
            saved: 'Pipeline salvo com sucesso',
            validated: 'Validação do pipeline bem-sucedida',
            error: {
              save: 'Falha ao salvar pipeline',
              validation: 'Validação do pipeline falhou',
              incompatibleNodes: 'Conexão de nó incompatível'
            }
          }
        }
      },
      integrations: {
        title: 'Integrações',
        description: 'Gerencie suas integrações e conexões',
        addIntegration: 'Adicionar Integração',
        selectIntegration: 'Selecionar Integração',
        selectProvider: 'Selecionar Provedor',
        configureIntegration: 'Configurar Integração',
        columns: {
          nodeName: 'Nome do Nó',
          environment: 'Ambiente',
          createdDate: 'Data de Criação',
          modifiedDate: 'Data de Modificação',
          actions: 'Ações'
        },
        form: {
          title: 'Adicionar Integração',
          fields: {
            nodeId: {
              label: 'Integração',
              tooltip: 'Selecione um provedor de integração',
              errors: {
                required: 'Seleção de integração é obrigatória'
              }
            },
            description: {
              label: 'Descrição',
              tooltip: 'Forneça uma descrição para esta integração',
              errors: {
                required: 'Descrição é obrigatória'
              }
            },
            environmentId: {
              label: 'Ambiente',
              tooltip: 'Selecione o ambiente para esta integração',
              errors: {
                required: 'Seleção de ambiente é obrigatória'
              }
            },
            enabled: {
              label: 'Habilitado',
              tooltip: 'Ative ou desative esta integração',
              errors: {
                required: 'Habilitado é obrigatório'
              }
            },
            auth: {
              type: {
                label: 'Tipo de Autenticação',
                tooltip: 'Selecione o método de autenticação',
                options: {
                  awsIam: 'AWS IAM',
                  apiKey: 'Chave de API'
                },
                errors: {
                  required: 'Tipo de autenticação é obrigatório'
                }
              },
              credentials: {
                apiKey: {
                  label: 'Chave de API',
                  tooltip: 'Digite sua chave de API',
                  errors: {
                    required: 'Chave de API é obrigatória'
                  }
                },
                iamRole: {
                  label: 'Função IAM',
                  tooltip: 'Digite o ARN da função IAM',
                  errors: {
                    required: 'Função IAM é obrigatória'
                  }
                }
              }
            }
          },
          search: {
            placeholder: 'Pesquisar integrações...'
          },
          errors: {
            required: 'Este campo é obrigatório',
            nodeId: {
              unrecognized_keys: 'Seleção de integração inválida'
            }
          }
        },
        actions: {
          edit: 'Editar Integração',
          delete: 'Excluir Integração'
        },
        search: 'Pesquisar integrações...',
        status: {
          creating: 'Criando integração...',
          created: 'Integração Criada',
          createFailed: 'Falha na Criação da Integração',
          deleting: 'Excluindo integração...',
          deleted: 'Integração Excluída',
          deleteFailed: 'Falha na Exclusão da Integração'
        }
      },
      settings: {
        environments: {
          title: 'Ambientes',
          description: 'Gerencie os ambientes do sistema e suas configurações',
          search: 'Pesquisar ambientes',
          searchPlaceholder: 'Pesquisar ambientes...',
          addButton: 'Adicionar Ambiente',
          createTitle: 'Criar Ambiente',
          editTitle: 'Editar Ambiente',
          deleteSuccess: 'Ambiente excluído com sucesso',
          deleteError: 'Falha ao excluir ambiente',
          createSuccess: 'Ambiente criado com sucesso',
          updateSuccess: 'Ambiente atualizado com sucesso',
          submitError: 'Falha ao salvar ambiente',
          columns: {
            name: 'Nome',
            region: 'Região',
            status: 'Status',
            team: 'Equipe',
            costCenter: 'Centro de Custo',
            createdAt: 'Criado Em',
            updatedAt: 'Atualizado Em',
            actions: 'Ações'
          },
          status: {
            active: 'Ativo',
            disabled: 'Desativado'
          },
          actions: {
            edit: 'Editar Ambiente',
            delete: 'Excluir Ambiente'
          },
          form: {
            name: 'Nome do Ambiente',
            region: 'Região',
            costCenter: 'Centro de Custo',
            team: 'Equipe',
            status: {
              name: 'Status',
              active: 'Ativo',
              disabled: 'Desativado'
            }
          }
        },
        systemSettings: {
          title: 'Configurações do Sistema',
          tabs: {
            search: 'Pesquisar',
            notifications: 'Notificações',
            security: 'Segurança',
            performance: 'Desempenho'
          },
          search: {
            title: 'Configuração de Pesquisa',
            description: 'Configure o provedor de pesquisa para aprimorar as capacidades de busca em seus ativos de mídia.',
            provider: 'Provedor de Pesquisa:',
            configureProvider: 'Configurar Provedor',
            editProvider: 'Editar Provedor',
            resetProvider: 'Redefinir Provedor',
            providerDetails: 'Detalhes do Provedor',
            providerName: 'Nome do Provedor',
            providerType: 'Tipo de Provedor',
            apiKey: 'Chave de API',
            endpoint: 'URL do Endpoint',
            enabled: 'Pesquisa Habilitada',
            noProvider: 'Nenhum provedor de pesquisa configurado.',
            configurePrompt: 'Configure Twelve Labs para habilitar as capacidades de busca.',
            errorLoading: 'Erro ao carregar a configuração do provedor de pesquisa'
          },
          notifications: {
            title: 'Configurações de Notificações',
            comingSoon: 'Configurações de notificações em breve.'
          },
          security: {
            title: 'Configurações de Segurança',
            comingSoon: 'Configurações de segurança em breve.'
          },
          performance: {
            title: 'Configurações de Desempenho',
            comingSoon: 'Configurações de desempenho em breve.'
          }
        }
      }
    }
  }
  