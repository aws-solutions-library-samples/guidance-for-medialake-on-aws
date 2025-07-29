export default {
  languages: {
    english: "영어",
    german: "독일어",
    portuguese: "포르투갈어",
    french: "프랑스어",
    chinese: "중국어",
    hindi: "힌디어",
    arabic: "아랍어",
    hebrew: "히브리어",
    japanese: "일본어",
    korean: "한국어",
    spanish: "스페인어",
  },
  assetsPage: {
    title: "자산",
    connectors: "커넥터",
    selectConnector: "커넥터 선택",
  },
  connectors: {
    apiMessages: {
      creating: {
        loading: "커넥터 생성 중...",
        success: "커넥터가 생성되었습니다",
        successMessage: "새 커넥터가 성공적으로 생성되었습니다.",
        error: "커넥터 생성에 실패했습니다",
      },
      updating: {
        loading: "커넥터 업데이트 중...",
        success: "커넥터가 업데이트되었습니다",
        successMessage: "커넥터가 성공적으로 업데이트되었습니다.",
        error: "커넥터 업데이트에 실패했습니다",
      },
      deleting: {
        loading: "커넥터 삭제 중...",
        success: "커넥터가 삭제되었습니다",
        successMessage: "커넥터가 성공적으로 삭제되었습니다.",
        error: "커넥터 삭제에 실패했습니다",
      },
      enabling: {
        loading: "커넥터 활성화 중...",
        success: "커넥터가 활성화되었습니다",
        successMessage: "커넥터가 성공적으로 활성화되었습니다.",
        error: "커넥터 활성화에 실패했습니다",
      },
      disabling: {
        loading: "커넥터 비활성화 중...",
        success: "커넥터가 비활성화되었습니다",
        successMessage: "커넥터가 성공적으로 비활성화되었습니다.",
        error: "커넥터 비활성화에 실패했습니다",
      },
    },
  },
  assets: {
    favorite: "즐겨찾기",
    unfavorite: "즐겨찾기 해제",
    rename: "이름 변경",
    delete: "삭제",
    download: "다운로드",
    share: "공유",
    viewDetails: "세부 정보 보기",
    retry: "재시도",
    retryFromCurrent: "현재 위치에서 재시도",
  },
  assetExplorer: {
    noConnectorSelected: "자산을 보려면 커넥터를 선택하세요",
    noAssetsFound: "이 커넥터에 대한 자산을 찾을 수 없습니다",
    noIndexedAssets:
      '버킷 "{{bucketName}}"의 이 커넥터에 대한 인덱싱된 자산을 찾을 수 없습니다.',
    loadingAssets: "자산 로딩 중...",
    menu: {
      rename: "이름 변경",
      share: "공유",
      download: "다운로드",
    },
    deleteDialog: {
      title: "삭제 확인",
      description: "이 자산을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.",
      cancel: "취소",
      confirm: "삭제",
    },
  },
  home: {
    title: "홈",
    description: "미디어, 메타데이터 및 워크플로를 위한 가이던스.",
    statistics: "통계",
    collections: "컬렉션",
    sharedCollections: "공유 컬렉션",
    favorites: "즐겨찾기",
    smartFolders: "스마트 폴더",
    connectedStorage: "연결된 스토리지",
    sharing: "공유",
    comingSoon: "곧 출시",
  },
  sidebar: {
    menu: {
      home: "홈",
      assets: "자산",
      pipelines: "파이프라인",
      pipelineExecutions: "파이프라인 실행",
      settings: "설정",
    },
    submenu: {
      system: "시스템 설정",
      connectors: "커넥터",
      userManagement: "사용자 관리",
      roles: "역할",
      integrations: "통합",
      environments: "환경",
    },
  },
  profile: {
    title: "프로필",
    description: "계정 설정 및 기본 설정 관리",
    changePhoto: "사진 변경",
    jobTitle: "직책",
    organization: "조직",
    preferences: "기본 설정",
    timezone: "시간대",
    emailNotifications: "이메일 알림",
    pushNotifications: "푸시 알림",
    changePassword: "비밀번호 변경",
    twoFactorAuth: "2단계 인증",
    appearance: "외관",
    noFirstName: "사용자가 이름을 설정하지 않았습니다",
    noLastName: "사용자가 성을 설정하지 않았습니다",
  },
  app: {
    loading: "로딩 중...",
    errors: {
      loadingConfig: "AWS 구성 로딩 오류:",
      loadingUserAttributes: "사용자 속성 로딩 오류:",
      signingOut: "로그아웃 오류:",
    },
    navigation: {
      preventedDuplicate: "중복 네비게이션이 방지되었습니다",
      navigating: "네비게이션 중",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: {
      label: "시맨틱",
      enable: "시맨틱 검색 활성화",
      disable: "시맨틱 검색 비활성화",
    },
    filters: {
      dateRange: "날짜 범위",
      contentType: "콘텐츠 유형",
      storageLocation: "스토리지 위치",
      comingSoon: "더 많은 필터가 곧 제공됩니다...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "스토리지 사용량",
      apiUsage: "API 사용량",
      activeUsers: "활성 사용자",
      systemLoad: "시스템 부하",
    },
    errors: {
      userDeletionNotImplemented: "사용자 삭제가 아직 구현되지 않았습니다.",
      userCreationNotImplemented: "사용자 생성이 아직 구현되지 않았습니다.",
      userEditingNotImplemented: "사용자 편집이 아직 구현되지 않았습니다.",
      analyticsExportNotImplemented:
        "분석 내보내기가 아직 구현되지 않았습니다.",
      systemResetNotImplemented: "시스템 재설정이 아직 구현되지 않았습니다.",
    },
    columns: {
      lastActive: "마지막 활동",
    },
    buttons: {
      exportAnalytics: "분석 내보내기",
      resetSystem: "시스템 재설정",
    },
  },
  integrations: {
    title: "통합",
    selectProvider: "통합 선택",
    selectIntegration: "통합 선택",
    configureIntegration: "통합 구성",
    description: "통합 및 연결 관리",
    addIntegration: "통합 추가",
    deleteConfirmation: {
      title: "통합 삭제",
      message: "이 통합을 삭제하시겠습니까?",
      warning:
        "경고: 이 통합을 제거하면 이에 의존하는 파이프라인이 실패할 수 있습니다.",
    },
    form: {
      search: {
        placeholder: "통합 검색",
      },
      title: "통합 추가",
      fields: {
        nodeId: {
          label: "통합",
          tooltip: "통합 제공업체 선택",
          errors: {
            required: "통합 선택이 필요합니다",
          },
        },
        description: {
          label: "설명",
          tooltip: "이 통합에 대한 설명 입력",
          helper: "이 통합에 대한 간단한 설명",
          errors: {
            required: "설명이 필요합니다",
          },
        },
        environmentId: {
          label: "환경",
          tooltip: "이 통합의 환경 선택",
          errors: {
            required: "환경 선택이 필요합니다",
          },
        },
        enabled: {
          label: "활성화",
          tooltip: "이 통합을 활성화 또는 비활성화",
          errors: {
            required: "활성화가 필요합니다",
          },
        },
        auth: {
          type: {
            label: "인증 유형",
            tooltip: "인증 방법 선택",
            options: {
              awsIam: "AWS IAM",
              apiKey: "API 키",
            },
            errors: {
              required: "인증 유형이 필요합니다",
            },
          },
          credentials: {
            apiKey: {
              label: "API 키",
              tooltip: "API 키 입력",
              helper: "서비스 인증을 위한 API 키",
              errors: {
                required: "API 키가 필요합니다",
              },
            },
            iamRole: {
              label: "IAM 역할",
              tooltip: "IAM 역할 ARN 입력",
              errors: {
                required: "IAM 역할이 필요합니다",
              },
            },
          },
        },
      },
      errors: {
        required: "이 필드는 필수입니다",
        nodeId: {
          unrecognized_keys: "잘못된 통합 선택",
        },
      },
    },
  },
  pipelines: {
    title: "파이프라인",
    description: "미디어 및 메타데이터 파이프라인 관리",
    searchPlaceholder: "파이프라인 검색...",
    actions: {
      create: "새 파이프라인 추가",
      import: "파이프라인 가져오기",
    },
  },
  executions: {
    title: "파이프라인 실행",
    description: "파이프라인 실행 모니터링 및 관리",
    searchPlaceholder: "파이프라인 실행 검색...",
    columns: {
      pipelineName: "파이프라인 이름",
      status: "상태",
      startTime: "시작 시간",
      endTime: "종료 시간",
      duration: "지속 시간",
      actions: "작업",
    },
  },
  users: {
    title: "사용자 관리",
    description: "시스템 사용자 및 액세스 관리",
    actions: {
      addUser: "사용자 추가",
    },
    apiMessages: {
      creating: {
        loading: "사용자 생성 중...",
        success: "사용자가 생성되었습니다",
        successMessage: "새 사용자가 성공적으로 생성되었습니다.",
        error: "사용자 생성에 실패했습니다",
      },
      updating: {
        loading: "사용자 업데이트 중...",
        success: "사용자가 업데이트되었습니다",
        successMessage: "사용자가 성공적으로 업데이트되었습니다.",
        error: "사용자 업데이트에 실패했습니다",
      },
      deleting: {
        loading: "사용자 삭제 중...",
        success: "사용자가 삭제되었습니다",
        successMessage: "사용자가 성공적으로 삭제되었습니다.",
        error: "사용자 삭제에 실패했습니다",
      },
      enabling: {
        loading: "사용자 활성화 중...",
        success: "사용자가 활성화되었습니다",
        successMessage: "사용자가 성공적으로 활성화되었습니다.",
        error: "사용자 활성화에 실패했습니다",
      },
      disabling: {
        loading: "사용자 비활성화 중...",
        success: "사용자가 비활성화되었습니다",
        successMessage: "사용자가 성공적으로 비활성화되었습니다.",
        error: "사용자 비활성화에 실패했습니다",
      },
    },
    form: {
      title: {
        add: "사용자 추가",
      },
      fields: {
        given_name: {
          label: "이름",
          tooltip: "사용자의 이름 입력",
          helper: "",
        },
        family_name: {
          label: "성",
          tooltip: "사용자의 성 입력",
          helper: "",
        },
        email: {
          label: "이메일",
          tooltip: "사용자의 이메일 주소 입력",
          helper: "",
        },
        roles: {
          label: "역할",
          tooltip: "사용자의 역할 선택",
          options: {
            Admin: "관리자",
            Editor: "편집자",
            Viewer: "뷰어",
          },
        },
        email_verified: {
          label: "이메일 인증됨",
          tooltip: "사용자의 이메일이 인증되었는지 표시",
        },
        enabled: {
          label: "활성화",
          tooltip: "사용자를 활성화 또는 비활성화",
        },
      },
    },
    roles: {
      admin: "관리자",
      editor: "편집자",
      viewer: "뷰어",
    },
  },
  roles: {
    title: "역할 관리",
    description: "시스템 역할 및 권한 관리",
    actions: {
      addRole: "역할 추가",
    },
  },
  settings: {
    environments: {
      title: "환경",
      description: "시스템 환경 및 구성 관리",
      addButton: "환경 추가",
      searchPlaceholder: "환경 검색",
      createTitle: "환경 생성",
      form: {
        name: "환경 이름",
        region: "지역",
        status: {
          name: "상태",
          active: "활성",
          disabled: "비활성",
        },
        costCenter: "비용 센터",
        team: "팀",
      },
    },
    systemSettings: {
      title: "시스템 설정",
      tabs: {
        search: "검색",
        notifications: "알림",
        security: "보안",
        performance: "성능",
      },
      search: {
        title: "검색 구성",
        description:
          "미디어 자산의 고급 검색 기능을 위해 검색 제공업체를 구성합니다.",
        provider: "검색 제공업체:",
        configureProvider: "검색 제공업체 구성",
        editProvider: "제공업체 편집",
        resetProvider: "제공업체 재설정",
        providerDetails: "제공업체 세부 정보",
        providerName: "제공업체 이름",
        apiKey: "API 키",
        endpoint: "엔드포인트 URL (선택사항)",
        enabled: "검색 활성화",
        noProvider: "검색 제공업체가 구성되지 않았습니다.",
        configurePrompt: "검색 기능을 활성화하려면 Twelve Labs를 구성하세요.",
      },
      notifications: {
        title: "알림 설정",
        comingSoon: "알림 설정이 곧 제공됩니다.",
      },
      security: {
        title: "보안 설정",
        comingSoon: "보안 설정이 곧 제공됩니다.",
      },
      performance: {
        title: "성능 설정",
        comingSoon: "성능 설정이 곧 제공됩니다.",
      },
    },
  },
  common: {
    select: "선택",
    back: "뒤로",
    search: "검색",
    profile: "프로필",
    logout: "로그아웃",
    theme: "테마",
    close: "닫기",
    refresh: "새로고침",
    cancel: "취소",
    save: "저장",
    loading: "로딩 중...",
    loadMore: "더 보기",
    tableDensity: "테이블 밀도",
    moreInfo: "자세한 정보",
    error: "오류",
    language: "언어",
    noResults: "결과를 찾을 수 없습니다",
    selectFilter: "필터 선택",
    textFilter: "텍스트 필터",
    all: "모두",
    filter: "필터",
    noGroups: "그룹 없음",
    actions: {
      add: "추가",
      save: "저장",
      delete: "삭제",
      edit: "편집",
      activate: "활성화",
      deactivate: "비활성화",
    },
    columns: {
      permissionSets: "권한 세트",
      username: "사용자명",
      firstName: "이름",
      lastName: "성",
      email: "이메일",
      status: "상태",
      groups: "그룹",
      created: "생성일",
      modified: "수정일",
      actions: "작업",
    },
    status: {
      active: "활성",
      inactive: "비활성",
    },
  },
  translation: {
    common: {
      actions: {
        add: "추가",
        edit: "편집",
        delete: "삭제",
        activate: "활성화",
        deactivate: "비활성화",
        create: "생성",
      },
      tableDensity: "테이블 밀도",
      theme: "테마",
      back: "뒤로",
      loading: "로딩 중...",
      error: "문제가 발생했습니다",
      save: "저장",
      cancel: "취소",
      delete: "삭제",
      edit: "편집",
      search: "검색",
      profile: "프로필",
      filterColumn: "필터",
      searchValue: "검색",
      logout: "로그아웃",
      language: "언어",
      alerts: "알림",
      warnings: "경고",
      notifications: "알림",
      searchPlaceholder: "검색하거나 key:value 사용...",
      close: "닫기",
      success: "성공",
      refresh: "새로고침",
      previous: "이전",
      next: "다음",
      show: "표시",
      all: "모두",
      status: {
        active: "활성",
        inactive: "비활성",
      },
      rename: "이름 변경",
      root: "루트",
      folder: "폴더",
      loadMore: "더 보기",
      darkMode: "다크 모드",
      lightMode: "라이트 모드",
      filter: "필터",
      textFilter: "텍스트 필터",
      selectFilter: "필터 선택",
      clearFilter: "필터 지우기",
      columns: {
        username: "사용자명",
        firstName: "이름",
        lastName: "성",
        email: "이메일",
        status: "상태",
        groups: "그룹",
        created: "생성일",
        modified: "수정일",
        actions: "작업",
      },
      noGroups: "그룹 없음",
      select: "선택",
      moreInfo: "자세한 정보",
    },
    users: {
      title: "사용자 관리",
      search: "사용자 검색",
      description: "시스템 사용자 및 액세스 관리",
      form: {
        fields: {
          given_name: {
            label: "이름",
            tooltip: "사용자의 이름 입력",
            errors: {
              required: "이름은 필수입니다",
            },
          },
          family_name: {
            label: "성",
            tooltip: "사용자의 성 입력",
            errors: {
              required: "성은 필수입니다",
            },
          },
          email: {
            label: "이메일",
            tooltip: "사용자의 이메일 주소 입력",
            errors: {
              required: "이메일은 필수입니다",
              invalid: "잘못된 이메일 주소",
            },
          },
          enabled: {
            label: "활성화",
            tooltip: "사용자를 활성화 또는 비활성화",
            errors: {
              required: "활성화는 필수입니다",
            },
          },
          roles: {
            label: "역할",
            tooltip: "사용자의 역할 선택",
            errors: {
              required: "역할은 필수입니다",
            },
          },
          email_verified: {
            label: "이메일 인증됨",
            tooltip: "사용자의 이메일이 인증되었는지 표시",
            errors: {
              required: "이메일 인증은 필수입니다",
            },
          },
        },
      },
    },
    roles: {
      title: "역할 관리",
      description: "시스템 역할 및 권한 관리",
      admin: "관리자",
      editor: "편집자",
      viewer: "뷰어",
      actions: {
        addRole: "역할 추가",
      },
    },
    columns: {
      username: "사용자명",
      firstName: "이름",
      lastName: "성",
      email: "이메일",
      status: "상태",
      groups: "그룹",
      created: "생성일",
      modified: "수정일",
      actions: "작업",
    },
    actions: {
      addUser: "사용자 추가",
      edit: "사용자 편집",
      delete: "사용자 삭제",
      activate: "사용자 활성화",
      deactivate: "사용자 비활성화",
    },
    status: {
      active: "활성",
      inactive: "비활성",
    },
    errors: {
      loadFailed: "사용자 로딩에 실패했습니다",
      saveFailed: "사용자 저장에 실패했습니다",
      deleteFailed: "사용자 삭제에 실패했습니다",
    },
    navigation: {
      home: "홈",
      collections: "컬렉션",
      settings: "설정",
    },
    home: {
      welcome: "Media Lake에 오신 것을 환영합니다",
      description: "미디어 파일을 효율적으로 관리하고 정리하세요",
      statistics: "통계",
      collections: "컬렉션",
      sharedCollections: "공유 컬렉션",
      favorites: "즐겨찾기",
      smartFolders: "스마트 폴더",
      connectedStorage: "연결된 스토리지",
      sharing: "공유",
      comingSoon: "곧 출시",
    },
    notifications: {
      "Pipeline Complete": "파이프라인 완료",
      "Asset processing pipeline completed successfully":
        "자산 처리 파이프라인이 성공적으로 완료되었습니다",
      "Storage Warning": "스토리지 경고",
      "Storage capacity reaching 80%": "스토리지 용량이 80%에 도달했습니다",
      "Pipeline Failed": "파이프라인 실패",
      "Video processing pipeline failed":
        "비디오 처리 파이프라인이 실패했습니다",
    },
    modal: {
      confirmDelete: "이 항목을 삭제하시겠습니까?",
      confirmAction: "이 작업을 수행하시겠습니까?",
      error: "오류가 발생했습니다",
      success: "작업이 성공적으로 완료되었습니다",
    },
    executions: {
      title: "파이프라인 실행",
      description: "파이프라인 실행 모니터링 및 관리",
      searchPlaceholder: "파이프라인 실행 검색...",
      columns: {
        pipelineName: "파이프라인 이름",
        status: "상태",
        startTime: "시작 시간",
        endTime: "종료 시간",
        duration: "지속 시간",
        actions: "작업",
      },
      status: {
        succeeded: "성공",
        failed: "실패",
        running: "실행 중",
        timedOut: "시간 초과",
        aborted: "중단됨",
      },
      actions: {
        retryFromCurrent: "현재 위치에서 재시도",
        retryFromStart: "처음부터 재시도",
        viewDetails: "세부 정보 보기",
      },
      pagination: {
        page: "페이지 {{page}} / {{total}}",
        showEntries: "{{count}}개 표시",
      },
    },
    s3Explorer: {
      filter: {
        label: "이름으로 필터링",
      },
      error: {
        loading: "S3 객체 로딩 오류: {{message}}",
      },
      file: {
        info: "크기: {{size}} • 스토리지 클래스: {{storageClass}} • 수정됨: {{modified}}",
      },
      menu: {
        rename: "이름 변경",
        delete: "삭제",
      },
    },
    assets: {
      title: "자산",
      connectedStorage: "연결된 스토리지",
    },
    metadata: {
      title: "곧 출시",
      description:
        "메타데이터 관리 기능을 제공하기 위해 작업 중입니다. 기대해 주세요!",
    },
    pipelines: {
      title: "파이프라인",
      description: "미디어 및 메타데이터 파이프라인 관리",
      searchPlaceholder: "파이프라인 검색...",
      actions: {
        create: "새 파이프라인 추가",
        deploy: "이미지 파이프라인 배포",
        addNew: "새 파이프라인 추가",
        viewAll: "모든 파이프라인 보기",
      },
      search: "파이프라인 검색",
      deploy: "이미지 파이프라인 배포",
      addNew: "새 파이프라인 추가",
      columns: {
        name: "이름",
        creationDate: "생성일",
        system: "시스템",
        type: "유형",
        actions: "작업",
      },
      editor: {
        title: "파이프라인 편집기",
        save: "파이프라인 저장",
        validate: "파이프라인 검증",
        sidebar: {
          title: "노드",
          dragNodes: "노드를 캔버스로 드래그",
          loading: "노드 로딩 중...",
          error: "노드 로딩 오류",
        },
        node: {
          configure: "{{type}} 구성",
          delete: "노드 삭제",
          edit: "노드 편집",
        },
        edge: {
          title: "엣지 라벨 편집",
          label: "엣지 라벨",
          delete: "연결 삭제",
        },
        modals: {
          error: {
            title: "오류",
            incompatibleNodes:
              "이전 노드의 출력이 대상 노드의 입력과 호환되지 않습니다.",
            validation: "파이프라인 검증에 실패했습니다",
          },
          delete: {
            title: "파이프라인 삭제",
            message:
              "이 파이프라인을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.",
            confirm: "삭제를 확인하려면 파이프라인 이름을 입력하세요:",
          },
        },
        controls: {
          undo: "실행 취소",
          redo: "다시 실행",
          zoomIn: "확대",
          zoomOut: "축소",
          fitView: "뷰에 맞추기",
          lockView: "뷰 잠금",
        },
        notifications: {
          saved: "파이프라인이 성공적으로 저장되었습니다",
          validated: "파이프라인 검증이 성공했습니다",
          error: {
            save: "파이프라인 저장에 실패했습니다",
            validation: "파이프라인 검증에 실패했습니다",
            incompatibleNodes: "호환되지 않는 노드 연결",
          },
        },
      },
    },
    integrations: {
      title: "통합",
      description: "통합 및 연결 관리",
      addIntegration: "통합 추가",
      selectIntegration: "통합 선택",
      selectProvider: "제공업체 선택",
      configureIntegration: "통합 구성",
      deleteConfirmation: {
        title: "통합 삭제",
        message: "이 통합을 삭제하시겠습니까?",
        warning:
          "경고: 이 통합을 삭제하면 이를 사용하는 파이프라인이 손상될 수 있습니다.",
      },
      form: {
        title: "통합 추가",
        fields: {
          nodeId: {
            label: "통합",
            tooltip: "통합 제공업체 선택",
            errors: {
              required: "통합 선택이 필요합니다",
            },
          },
          description: {
            label: "설명",
            tooltip: "이 통합에 대한 설명 입력",
            helper: "이 통합에 대한 간단한 설명",
            errors: {
              required: "설명이 필요합니다",
            },
          },
          environmentId: {
            label: "환경",
            tooltip: "이 통합의 환경 선택",
            errors: {
              required: "환경 선택이 필요합니다",
            },
          },
          enabled: {
            label: "활성화",
            tooltip: "이 통합을 활성화 또는 비활성화",
            errors: {
              required: "활성화가 필요합니다",
            },
          },
          auth: {
            type: {
              label: "인증 유형",
              tooltip: "인증 방법 선택",
              options: {
                awsIam: "AWS IAM",
                apiKey: "API 키",
              },
              errors: {
                required: "인증 유형이 필요합니다",
              },
            },
            credentials: {
              apiKey: {
                label: "API 키",
                tooltip: "API 키 입력",
                helper: "서비스 인증을 위한 API 키",
                errors: {
                  required: "API 키가 필요합니다",
                },
              },
              iamRole: {
                label: "IAM 역할",
                tooltip: "IAM 역할 ARN 입력",
                errors: {
                  required: "IAM 역할이 필요합니다",
                },
              },
            },
          },
        },
        search: {
          placeholder: "통합 검색",
        },

        errors: {
          required: "이 필드는 필수입니다",
          nodeId: {
            unrecognized_keys: "잘못된 통합 선택",
          },
        },
      },
      columns: {
        nodeName: "노드 이름",
        environment: "환경",
        createdDate: "생성일",
        modifiedDate: "수정일",
        actions: "작업",
      },

      settings: {
        environments: {
          title: "환경",
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "그룹 추가",
      editGroup: "그룹 편집",
      deleteGroup: "그룹 삭제",
      createGroup: "그룹 생성",
      manageGroups: "그룹 관리",
    },
  },
  permissionSets: {
    noAssignments: "권한 세트 없음",
    actions: {
      addPermissionSet: "권한 세트 추가",
      editPermissionSet: "권한 세트 편집",
      deletePermissionSet: "권한 세트 삭제",
    },
  },
};
