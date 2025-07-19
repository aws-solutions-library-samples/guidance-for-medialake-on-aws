export default {
  languages: {
    english: "英语",
    german: "德语",
    portuguese: "葡萄牙语",
    french: "法语",
    chinese: "中文",
    hindi: "印地语",
    arabic: "阿拉伯语",
    hebrew: "希伯来语",
    japanese: "日语",
    korean: "韩语",
    spanish: "西班牙语",
  },
  assetsPage: {
    title: "资产",
    connectors: "连接器",
    selectConnector: "选择连接器",
  },
  assetExplorer: {
    noConnectorSelected: "选择连接器以查看资产",
    noAssetsFound: "未找到此连接器的资产",
    noIndexedAssets: '未在存储桶 "{{bucketName}}" 中找到此连接器的索引资产。',
    loadingAssets: "正在加载资产...",
    menu: {
      rename: "重命名",
      share: "分享",
      download: "下载",
    },
    deleteDialog: {
      title: "确认删除",
      description: "您确定要删除此资产吗？此操作不可撤销。",
      cancel: "取消",
      confirm: "删除",
    },
  },
  sidebar: {
    menu: {
      home: "首页",
      assets: "资产",
      pipelines: "管道",
      pipelineExecutions: "管道执行",
      settings: "设置",
    },
    submenu: {
      system: "系统设置",
      connectors: "连接器",
      userManagement: "用户管理",
      roles: "角色",
      integrations: "集成",
      environments: "环境",
    },
  },
  profile: {
    title: "个人资料",
    description: "管理您的账户设置和偏好",
    changePhoto: "更换照片",
    jobTitle: "职位",
    organization: "组织",
    preferences: "偏好",
    timezone: "时区",
    emailNotifications: "邮件通知",
    pushNotifications: "推送通知",
    changePassword: "更改密码",
    twoFactorAuth: "两步验证",
    appearance: "外观",
  },
  app: {
    loading: "加载中...",
    errors: {
      loadingConfig: "加载AWS配置错误：",
      loadingUserAttributes: "加载用户属性错误：",
      signingOut: "退出登录错误：",
    },
    navigation: {
      preventedDuplicate: "阻止了重复导航到",
      navigating: "正在从...导航",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "语义搜索",
    filters: {
      dateRange: "日期范围",
      contentType: "内容类型",
      storageLocation: "存储位置",
      comingSoon: "更多筛选即将推出...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "存储使用量",
      apiUsage: "API使用量",
      activeUsers: "活跃用户",
      systemLoad: "系统负载",
    },
    errors: {
      userDeletionNotImplemented: "用户删除功能尚未实现。",
      userCreationNotImplemented: "用户创建功能尚未实现。",
      userEditingNotImplemented: "用户编辑功能尚未实现。",
      analyticsExportNotImplemented: "分析数据导出功能尚未实现。",
      systemResetNotImplemented: "系统重置功能尚未实现。",
    },
    columns: {
      lastActive: "最后活动时间",
    },
    buttons: {
      exportAnalytics: "导出分析",
      resetSystem: "重置系统",
    },
  },
  integrations: {
    title: "集成",
    selectProvider: "选择集成",
    selectIntegration: "选择集成",
    configureIntegration: "配置集成",
    description: "管理您的集成和连接",
    addIntegration: "添加集成",
    form: {
      search: {
        placeholder: "搜索集成",
      },
      title: "添加集成",
      fields: {
        nodeId: {
          label: "集成",
          tooltip: "选择一个集成提供商",
          errors: {
            required: "必须选择集成",
          },
        },
        description: {
          label: "描述",
          tooltip: "为此集成提供描述",
          helper: "此集成的简要描述",
          errors: {
            required: "描述为必填项",
          },
        },
        environmentId: {
          label: "环境",
          tooltip: "选择此集成的环境",
          errors: {
            required: "必须选择环境",
          },
        },
        enabled: {
          label: "启用",
          tooltip: "启用或禁用此集成",
          errors: {
            required: "启用为必填项",
          },
        },
        auth: {
          type: {
            label: "认证类型",
            tooltip: "选择认证方法",
            options: {
              awsIam: "AWS IAM",
              apiKey: "API密钥",
            },
            errors: {
              required: "必须选择认证类型",
            },
          },
          credentials: {
            apiKey: {
              label: "API密钥",
              tooltip: "输入您的API密钥",
              helper: "用于服务认证的API密钥",
              errors: {
                required: "必须输入API密钥",
              },
            },
            iamRole: {
              label: "IAM角色",
              tooltip: "输入IAM角色ARN",
              errors: {
                required: "必须输入IAM角色",
              },
            },
          },
        },
      },
      errors: {
        required: "此字段为必填项",
        nodeId: {
          unrecognized_keys: "无效的集成选择",
        },
      },
    },
  },
  pipelines: {
    title: "管道",
    description: "管理您的媒体和元数据管道",
    searchPlaceholder: "搜索管道...",
    actions: {
      create: "添加新管道",
      import: "导入管道",
    },
  },
  executions: {
    title: "管道执行",
    description: "监控并管理您的管道执行",
    searchPlaceholder: "搜索管道执行...",
    columns: {
      pipelineName: "管道名称",
      status: "状态",
      startTime: "开始时间",
      endTime: "结束时间",
      duration: "时长",
      actions: "操作",
    },
    actions: {
      retryFromCurrent: "从当前位置重试",
      retryFromStart: "从头重试",
      viewDetails: "查看详情",
    },
  },
  users: {
    title: "用户管理",
    description: "管理系统用户及其权限",
    actions: {
      addUser: "添加用户",
    },
    form: {
      title: {
        add: "添加用户",
      },
      fields: {
        given_name: {
          label: "名",
          tooltip: "输入用户的名字",
          helper: "",
        },
        family_name: {
          label: "姓",
          tooltip: "输入用户的姓",
          helper: "",
        },
        email: {
          label: "电子邮件",
          tooltip: "输入用户的电子邮件地址",
          helper: "",
        },
        roles: {
          label: "角色",
          tooltip: "选择用户的角色",
          options: {
            Admin: "管理员",
            Editor: "编辑",
            Viewer: "查看者",
          },
        },
        email_verified: {
          label: "邮箱验证",
          tooltip: "指示用户的邮箱是否已验证",
        },
        enabled: {
          label: "启用",
          tooltip: "启用或禁用该用户",
        },
      },
    },
    roles: {
      admin: "管理员",
      editor: "编辑",
      viewer: "查看者",
    },
  },
  roles: {
    title: "角色管理",
    description: "管理系统角色及其权限",
    actions: {
      addRole: "添加角色",
    },
  },
  settings: {
    environments: {
      title: "环境",
      description: "管理系统环境及其配置",
      addButton: "添加环境",
      searchPlaceholder: "搜索环境",
      createTitle: "创建环境",
      form: {
        name: "环境名称",
        region: "区域",
        status: {
          name: "状态",
          active: "激活",
          disabled: "禁用",
        },
        costCenter: "成本中心",
        team: "团队",
      },
    },
    systemSettings: {
      title: "系统设置",
      tabs: {
        search: "搜索",
        notifications: "通知",
        security: "安全",
        performance: "性能",
      },
      search: {
        title: "搜索配置",
        description: "配置搜索提供商以增强您媒体资产的搜索功能。",
        provider: "搜索提供商：",
        configureProvider: "配置搜索提供商",
        editProvider: "编辑提供商",
        resetProvider: "重置提供商",
        providerDetails: "提供商详情",
        providerName: "提供商名称",
        apiKey: "API密钥",
        endpoint: "端点URL（可选）",
        enabled: "启用搜索",
        noProvider: "未配置搜索提供商。",
        configurePrompt: "配置 Twelve Labs 以启用搜索功能。",
      },
      notifications: {
        title: "通知设置",
        comingSoon: "通知设置即将推出。",
      },
      security: {
        title: "安全设置",
        comingSoon: "安全设置即将推出。",
      },
      performance: {
        title: "性能设置",
        comingSoon: "性能设置即将推出。",
      },
    },
    groups: {
      actions: {
        addGroup: "添加组",
        editGroup: "编辑组",
        deleteGroup: "删除组",
        createGroup: "创建组",
        manageGroups: "管理组",
      },
    },
    permissionSets: {
      noAssignments: "无权限集",
      actions: {
        addPermissionSet: "添加权限集",
        editPermissionSet: "编辑权限集",
        deletePermissionSet: "删除权限集",
      },
    },
  },
  common: {
    select: "选择",
    back: "返回",
    search: "搜索",
    profile: "个人资料",
    logout: "退出登录",
    theme: "主题",
    close: "关闭",
    refresh: "刷新",
    cancel: "取消",
    save: "保存",
    loading: "加载中...",
    loadMore: "加载更多",
    tableDensity: "表格密度",
    moreInfo: "更多信息",
    error: "错误",
    language: "语言",
    delete: "删除",
    create: "创建",
    actions: {
      add: "添加",
    },
    columns: {
      username: "用户名",
      firstName: "名",
      lastName: "姓",
      email: "电子邮件",
      status: "状态",
      groups: "组",
      created: "创建时间",
      modified: "修改时间",
      actions: "操作",
    },
    status: {
      active: "激活",
      inactive: "未激活",
    },
  },
  translation: {
    common: {
      actions: {
        add: "添加",
        edit: "编辑",
        delete: "删除",
        activate: "激活",
        deactivate: "停用",
        create: "创建",
      },
      tableDensity: "表格密度",
      theme: "主题",
      back: "返回",
      loading: "加载中...",
      error: "出了点问题",
      save: "保存",
      cancel: "取消",
      delete: "删除",
      edit: "编辑",
      search: "搜索",
      profile: "个人资料",
      filterColumn: "筛选",
      searchValue: "搜索",
      logout: "退出登录",
      language: "语言",
      alerts: "提醒",
      warnings: "警告",
      notifications: "通知",
      searchPlaceholder: "搜索或使用 key:value...",
      close: "关闭",
      success: "成功",
      refresh: "刷新",
      previous: "上一页",
      next: "下一页",
      show: "显示",
      all: "全部",
      status: {
        active: "激活",
        inactive: "未激活",
      },
      rename: "重命名",
      root: "根目录",
      folder: "文件夹",
      loadMore: "加载更多",
      darkMode: "深色模式",
      lightMode: "浅色模式",
      filter: "筛选",
      textFilter: "文本筛选",
      selectFilter: "选择筛选",
      clearFilter: "清除筛选",
      columns: {
        username: "用户名",
        firstName: "名",
        lastName: "姓",
        email: "电子邮件",
        status: "状态",
        groups: "组",
        created: "创建时间",
        modified: "修改时间",
        actions: "操作",
      },
      noGroups: "无组",
      select: "选择",
      moreInfo: "更多信息",
    },
    users: {
      title: "用户管理",
      search: "搜索用户",
      description: "管理系统用户及其权限",
      form: {
        fields: {
          given_name: {
            label: "名",
            tooltip: "输入用户的名字",
            errors: {
              required: "名字为必填项",
            },
          },
          family_name: {
            label: "姓",
            tooltip: "输入用户的姓",
            errors: {
              required: "姓为必填项",
            },
          },
          email: {
            label: "电子邮件",
            tooltip: "输入用户的电子邮件地址",
            errors: {
              required: "电子邮件为必填项",
              invalid: "无效的电子邮件地址",
            },
          },
          enabled: {
            label: "启用",
            tooltip: "启用或禁用用户",
            errors: {
              required: "必须启用",
            },
          },
          roles: {
            label: "角色",
            tooltip: "选择用户的角色",
            errors: {
              required: "必须选择角色",
            },
          },
          email_verified: {
            label: "邮箱验证",
            tooltip: "指示用户邮箱是否已验证",
            errors: {
              required: "邮箱验证为必填项",
            },
          },
        },
      },
    },
    roles: {
      title: "角色管理",
      description: "管理系统角色及其权限",
      admin: "管理员",
      editor: "编辑",
      viewer: "查看者",
      actions: {
        addRole: "添加角色",
      },
    },
    columns: {
      username: "用户名",
      firstName: "名",
      lastName: "姓",
      email: "电子邮件",
      status: "状态",
      groups: "组",
      created: "创建时间",
      modified: "修改时间",
      actions: "操作",
    },
    actions: {
      addUser: "添加用户",
      edit: "编辑用户",
      delete: "删除用户",
      activate: "激活用户",
      deactivate: "停用用户",
    },
    status: {
      active: "激活",
      inactive: "未激活",
    },
    errors: {
      loadFailed: "加载用户失败",
      saveFailed: "保存用户失败",
      deleteFailed: "删除用户失败",
    },
    navigation: {
      home: "首页",
      collections: "收藏",
      settings: "设置",
    },
    home: {
      welcome: "欢迎使用 Media Lake",
      description: "高效管理和组织您的媒体文件",
      statistics: "统计",
      collections: "收藏",
      sharedCollections: "共享收藏",
      favorites: "收藏夹",
      smartFolders: "智能文件夹",
      connectedStorage: "已连接存储",
      sharing: "分享",
      comingSoon: "即将推出",
    },
    notifications: {
      "Pipeline Complete": "管道完成",
      "Asset processing pipeline completed successfully":
        "资产处理管道已成功完成",
      "Storage Warning": "存储警告",
      "Storage capacity reaching 80%": "存储容量达到80%",
      "Pipeline Failed": "管道失败",
      "Video processing pipeline failed": "视频处理管道失败",
    },
    modal: {
      confirmDelete: "您确定要删除此项吗？",
      confirmAction: "您确定要执行此操作吗？",
      error: "发生错误",
      success: "操作成功完成",
    },
    executions: {
      title: "管道执行",
      description: "监控并管理您的管道执行",
      searchPlaceholder: "搜索管道执行...",
      columns: {
        pipelineName: "管道名称",
        status: "状态",
        startTime: "开始时间",
        endTime: "结束时间",
        duration: "时长",
        actions: "操作",
      },
      status: {
        succeeded: "成功",
        failed: "失败",
        running: "运行中",
        timedOut: "超时",
        aborted: "中止",
      },
      actions: {
        retryFromCurrent: "从当前位置重试",
        retryFromStart: "从头重试",
        viewDetails: "查看详情",
      },
      pagination: {
        page: "第 {{page}} 页，共 {{total}} 页",
        showEntries: "显示 {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "按名称过滤",
      },
      error: {
        loading: "加载S3对象时出错：{{message}}",
      },
      file: {
        info: "大小：{{size}} • 存储类别：{{storageClass}} • 修改时间：{{modified}}",
      },
      menu: {
        rename: "重命名",
        delete: "删除",
      },
    },
    assets: {
      title: "资产",
      connectedStorage: "已连接存储",
    },
    metadata: {
      title: "敬请期待",
      description: "我们正在努力为您带来元数据管理功能，请继续关注！",
    },
    pipelines: {
      title: "管道",
      description: "管理您的媒体和元数据管道",
      searchPlaceholder: "搜索管道...",
      actions: {
        create: "添加新管道",
        deploy: "部署图像管道",
        addNew: "添加新管道",
        viewAll: "查看所有管道",
      },
      search: "搜索管道",
      deploy: "部署图像管道",
      addNew: "添加新管道",
      columns: {
        name: "名称",
        creationDate: "创建日期",
        system: "系统",
        type: "类型",
        actions: "操作",
      },
      editor: {
        title: "管道编辑器",
        save: "保存管道",
        validate: "验证管道",
        sidebar: {
          title: "节点",
          dragNodes: "将节点拖到画布上",
          loading: "加载节点中...",
          error: "加载节点错误",
        },
        node: {
          configure: "配置 {{type}}",
          delete: "删除节点",
          edit: "编辑节点",
        },
        edge: {
          title: "编辑连线标签",
          label: "连线标签",
          delete: "删除连接",
        },
        modals: {
          error: {
            title: "错误",
            incompatibleNodes: "前一个节点的输出与目标节点的输入不兼容。",
            validation: "管道验证失败",
          },
          delete: {
            title: "删除管道",
            message: "您确定要删除此管道吗？此操作不可撤销。",
            confirm: "输入管道名称以确认删除：",
          },
        },
        controls: {
          undo: "撤销",
          redo: "重做",
          zoomIn: "放大",
          zoomOut: "缩小",
          fitView: "适应视图",
          lockView: "锁定视图",
        },
        notifications: {
          saved: "管道保存成功",
          validated: "管道验证成功",
          error: {
            save: "保存管道失败",
            validation: "管道验证失败",
            incompatibleNodes: "节点连接不兼容",
          },
        },
      },
    },
    integrations: {
      title: "集成",
      description: "管理您的集成和连接",
      addIntegration: "添加集成",
      selectIntegration: "选择集成",
      selectProvider: "选择提供商",
      configureIntegration: "配置集成",
      form: {
        title: "添加集成",
        fields: {
          nodeId: {
            label: "集成",
            tooltip: "选择一个集成提供商",
            errors: {
              required: "必须选择集成",
            },
          },
          description: {
            label: "描述",
            tooltip: "为此集成提供描述",
            errors: {
              required: "描述为必填项",
            },
          },
          environmentId: {
            label: "环境",
            tooltip: "选择此集成的环境",
            errors: {
              required: "必须选择环境",
            },
          },
          enabled: {
            label: "启用",
            tooltip: "启用或禁用此集成",
            errors: {
              required: "启用为必填项",
            },
          },
          auth: {
            type: {
              label: "认证类型",
              tooltip: "选择认证方法",
              options: {
                awsIam: "AWS IAM",
                apiKey: "API密钥",
              },
              errors: {
                required: "必须选择认证类型",
              },
            },
            credentials: {
              apiKey: {
                label: "API密钥",
                tooltip: "输入您的API密钥",
                errors: {
                  required: "必须输入API密钥",
                },
              },
              iamRole: {
                label: "IAM角色",
                tooltip: "输入IAM角色ARN",
                errors: {
                  required: "必须输入IAM角色",
                },
              },
            },
          },
        },
        search: {
          placeholder: "搜索集成",
        },
        errors: {
          required: "此字段为必填项",
          nodeId: {
            unrecognized_keys: "无效的集成选择",
          },
        },
      },
      columns: {
        nodeName: "节点名称",
        environment: "环境",
        createdDate: "创建日期",
        modifiedDate: "修改日期",
        actions: "操作",
      },
      settings: {
        environments: {
          title: "环境",
        },
      },
    },
    groups: {
      actions: {
        addGroup: "添加组",
        editGroup: "编辑组",
        deleteGroup: "删除组",
        createGroup: "创建组",
        manageGroups: "管理组",
      },
    },
    permissionSets: {
      noAssignments: "无权限集",
      actions: {
        addPermissionSet: "添加权限集",
        editPermissionSet: "编辑权限集",
        deletePermissionSet: "删除权限集",
      },
    },
  },
};
