export default {
  languages: {
    english: "英語",
    german: "ドイツ語",
    portuguese: "ポルトガル語",
    french: "フランス語",
    chinese: "中国語",
    hindi: "ヒンディー語",
    arabic: "アラビア語",
    hebrew: "ヘブライ語",
    japanese: "日本語",
    korean: "韓国語",
    spanish: "スペイン語",
  },
  assetsPage: {
    title: "アセット",
    connectors: "コネクタ",
    selectConnector: "コネクタを選択",
  },
  connectors: {
    apiMessages: {
      creating: {
        loading: "コネクタを作成中...",
        success: "コネクタが作成されました",
        successMessage: "新しいコネクタが正常に作成されました。",
        error: "コネクタの作成に失敗しました",
      },
      updating: {
        loading: "コネクタを更新中...",
        success: "コネクタが更新されました",
        successMessage: "コネクタが正常に更新されました。",
        error: "コネクタの更新に失敗しました",
      },
      deleting: {
        loading: "コネクタを削除中...",
        success: "コネクタが削除されました",
        successMessage: "コネクタが正常に削除されました。",
        error: "コネクタの削除に失敗しました",
      },
      enabling: {
        loading: "コネクタを有効化中...",
        success: "コネクタが有効化されました",
        successMessage: "コネクタが正常に有効化されました。",
        error: "コネクタの有効化に失敗しました",
      },
      disabling: {
        loading: "コネクタを無効化中...",
        success: "コネクタが無効化されました",
        successMessage: "コネクタが正常に無効化されました。",
        error: "コネクタの無効化に失敗しました",
      },
    },
  },
  assets: {
    favorite: "お気に入り",
    unfavorite: "お気に入りを解除",
    rename: "名前を変更",
    delete: "削除",
    download: "ダウンロード",
    share: "共有",
    viewDetails: "詳細を表示",
    retry: "再試行",
    retryFromCurrent: "現在の位置から再試行",
  },
  assetExplorer: {
    noConnectorSelected: "アセットを表示するにはコネクタを選択してください",
    noAssetsFound: "このコネクタのアセットが見つかりません",
    noIndexedAssets:
      'バケット "{{bucketName}}" のこのコネクタのインデックス化されたアセットが見つかりません。',
    loadingAssets: "アセットを読み込み中...",
    menu: {
      rename: "名前を変更",
      share: "共有",
      download: "ダウンロード",
    },
    deleteDialog: {
      title: "削除の確認",
      description:
        "このアセットを削除してもよろしいですか？この操作は元に戻せません。",
      cancel: "キャンセル",
      confirm: "削除",
    },
  },
  home: {
    title: "ホーム",
    description: "メディア、メタデータ、ワークフローのためのガイダンス。",
    statistics: "統計",
    collections: "コレクション",
    sharedCollections: "共有コレクション",
    favorites: "お気に入り",
    smartFolders: "スマートフォルダ",
    connectedStorage: "接続されたストレージ",
    sharing: "共有",
    comingSoon: "近日公開",
  },
  sidebar: {
    menu: {
      home: "ホーム",
      assets: "アセット",
      pipelines: "パイプライン",
      pipelineExecutions: "パイプライン実行",
      settings: "設定",
    },
    submenu: {
      system: "システム設定",
      connectors: "コネクタ",
      userManagement: "ユーザー管理",
      roles: "ロール",
      integrations: "統合",
      environments: "環境",
    },
  },
  profile: {
    title: "プロフィール",
    description: "アカウント設定と設定を管理",
    changePhoto: "写真を変更",
    jobTitle: "職種",
    organization: "組織",
    preferences: "設定",
    timezone: "タイムゾーン",
    emailNotifications: "メール通知",
    pushNotifications: "プッシュ通知",
    changePassword: "パスワードを変更",
    twoFactorAuth: "二要素認証",
    appearance: "外観",
    noFirstName: "ユーザーは名前を設定していません",
    noLastName: "ユーザーは姓を設定していません",
  },
  app: {
    loading: "読み込み中...",
    errors: {
      loadingConfig: "AWS設定の読み込みエラー:",
      loadingUserAttributes: "ユーザー属性の読み込みエラー:",
      signingOut: "サインアウトエラー:",
    },
    navigation: {
      preventedDuplicate: "重複ナビゲーションを防止しました",
      navigating: "ナビゲート中",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: {
      label: "セマンティック",
      enable: "セマンティック検索を有効にする",
      disable: "セマンティック検索を無効にする",
    },
    filters: {
      dateRange: "日付範囲",
      contentType: "コンテンツタイプ",
      storageLocation: "ストレージの場所",
      comingSoon: "より多くのフィルターが近日公開...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "ストレージ使用量",
      apiUsage: "API使用量",
      activeUsers: "アクティブユーザー",
      systemLoad: "システム負荷",
    },
    errors: {
      userDeletionNotImplemented: "ユーザー削除はまだ実装されていません。",
      userCreationNotImplemented: "ユーザー作成はまだ実装されていません。",
      userEditingNotImplemented: "ユーザー編集はまだ実装されていません。",
      analyticsExportNotImplemented:
        "アナリティクスエクスポートはまだ実装されていません。",
      systemResetNotImplemented: "システムリセットはまだ実装されていません。",
    },
    columns: {
      lastActive: "最終アクティブ",
    },
    buttons: {
      exportAnalytics: "アナリティクスをエクスポート",
      resetSystem: "システムをリセット",
    },
  },
  integrations: {
    title: "統合",
    selectProvider: "統合を選択",
    selectIntegration: "統合を選択",
    configureIntegration: "統合を設定",
    description: "統合と接続を管理",
    addIntegration: "統合を追加",
    deleteConfirmation: {
      title: "統合を削除",
      message: "この統合を削除してもよろしいですか？",
      warning:
        "警告: この統合を削除すると、それに依存するパイプラインが失敗する可能性があります。",
    },
    form: {
      search: {
        placeholder: "統合を検索",
      },
      title: "統合を追加",
      fields: {
        nodeId: {
          label: "統合",
          tooltip: "統合プロバイダーを選択",
          errors: {
            required: "統合の選択が必要です",
          },
        },
        description: {
          label: "説明",
          tooltip: "この統合の説明を入力",
          helper: "この統合の簡単な説明",
          errors: {
            required: "説明が必要です",
          },
        },
        environmentId: {
          label: "環境",
          tooltip: "この統合の環境を選択",
          errors: {
            required: "環境の選択が必要です",
          },
        },
        enabled: {
          label: "有効",
          tooltip: "この統合を有効または無効にする",
          errors: {
            required: "有効化が必要です",
          },
        },
        auth: {
          type: {
            label: "認証タイプ",
            tooltip: "認証方法を選択",
            options: {
              awsIam: "AWS IAM",
              apiKey: "APIキー",
            },
            errors: {
              required: "認証タイプが必要です",
            },
          },
          credentials: {
            apiKey: {
              label: "APIキー",
              tooltip: "APIキーを入力",
              helper: "サービス認証用のAPIキー",
              errors: {
                required: "APIキーが必要です",
              },
            },
            iamRole: {
              label: "IAMロール",
              tooltip: "IAMロールのARNを入力",
              errors: {
                required: "IAMロールが必要です",
              },
            },
          },
        },
      },
      errors: {
        required: "このフィールドは必須です",
        nodeId: {
          unrecognized_keys: "無効な統合選択",
        },
      },
    },
  },
  pipelines: {
    title: "パイプライン",
    description: "メディアとメタデータのパイプラインを管理",
    searchPlaceholder: "パイプラインを検索...",
    actions: {
      create: "新しいパイプラインを追加",
      import: "パイプラインをインポート",
    },
  },
  executions: {
    title: "パイプライン実行",
    description: "パイプライン実行を監視・管理",
    searchPlaceholder: "パイプライン実行を検索...",
    columns: {
      pipelineName: "パイプライン名",
      status: "ステータス",
      startTime: "開始時刻",
      endTime: "終了時刻",
      duration: "期間",
      actions: "アクション",
    },
  },
  users: {
    title: "ユーザー管理",
    description: "システムユーザーとそのアクセスを管理",
    actions: {
      addUser: "ユーザーを追加",
    },
    apiMessages: {
      creating: {
        loading: "ユーザーを作成中...",
        success: "ユーザーが作成されました",
        successMessage: "新しいユーザーが正常に作成されました。",
        error: "ユーザーの作成に失敗しました",
      },
      updating: {
        loading: "ユーザーを更新中...",
        success: "ユーザーが更新されました",
        successMessage: "ユーザーが正常に更新されました。",
        error: "ユーザーの更新に失敗しました",
      },
      deleting: {
        loading: "ユーザーを削除中...",
        success: "ユーザーが削除されました",
        successMessage: "ユーザーが正常に削除されました。",
        error: "ユーザーの削除に失敗しました",
      },
      enabling: {
        loading: "ユーザーを有効化中...",
        success: "ユーザーが有効化されました",
        successMessage: "ユーザーが正常に有効化されました。",
        error: "ユーザーの有効化に失敗しました",
      },
      disabling: {
        loading: "ユーザーを無効化中...",
        success: "ユーザーが無効化されました",
        successMessage: "ユーザーが正常に無効化されました。",
        error: "ユーザーの無効化に失敗しました",
      },
    },
    form: {
      title: {
        add: "ユーザーを追加",
      },
      fields: {
        given_name: {
          label: "名前",
          tooltip: "ユーザーの名前を入力",
          helper: "",
        },
        family_name: {
          label: "姓",
          tooltip: "ユーザーの姓を入力",
          helper: "",
        },
        email: {
          label: "メール",
          tooltip: "ユーザーのメールアドレスを入力",
          helper: "",
        },
        roles: {
          label: "ロール",
          tooltip: "ユーザーのロールを選択",
          options: {
            Admin: "管理者",
            Editor: "編集者",
            Viewer: "閲覧者",
          },
        },
        email_verified: {
          label: "メール認証済み",
          tooltip: "ユーザーのメールが認証済みかどうかを示す",
        },
        enabled: {
          label: "有効",
          tooltip: "ユーザーを有効または無効にする",
        },
      },
    },
    roles: {
      admin: "管理者",
      editor: "編集者",
      viewer: "閲覧者",
    },
  },
  roles: {
    title: "ロール管理",
    description: "システムロールとその権限を管理",
    actions: {
      addRole: "ロールを追加",
    },
  },
  settings: {
    environments: {
      title: "環境",
      description: "システム環境とその設定を管理",
      addButton: "環境を追加",
      searchPlaceholder: "環境を検索",
      createTitle: "環境を作成",
      form: {
        name: "環境名",
        region: "リージョン",
        status: {
          name: "ステータス",
          active: "アクティブ",
          disabled: "無効",
        },
        costCenter: "コストセンター",
        team: "チーム",
      },
    },
    systemSettings: {
      title: "システム設定",
      tabs: {
        search: "検索",
        notifications: "通知",
        security: "セキュリティ",
        performance: "パフォーマンス",
      },
      search: {
        title: "検索設定",
        description:
          "メディアアセットの高度な検索機能のために検索プロバイダーを設定します。",
        provider: "検索プロバイダー:",
        configureProvider: "検索プロバイダーを設定",
        editProvider: "プロバイダーを編集",
        resetProvider: "プロバイダーをリセット",
        providerDetails: "プロバイダー詳細",
        providerName: "プロバイダー名",
        apiKey: "APIキー",
        endpoint: "エンドポイントURL（オプション）",
        enabled: "検索有効",
        noProvider: "検索プロバイダーが設定されていません。",
        configurePrompt:
          "検索機能を有効にするためにTwelve Labsを設定してください。",
      },
      notifications: {
        title: "通知設定",
        comingSoon: "通知設定は近日公開予定です。",
      },
      security: {
        title: "セキュリティ設定",
        comingSoon: "セキュリティ設定は近日公開予定です。",
      },
      performance: {
        title: "パフォーマンス設定",
        comingSoon: "パフォーマンス設定は近日公開予定です。",
      },
    },
  },
  common: {
    select: "選択",
    back: "戻る",
    search: "検索",
    profile: "プロフィール",
    logout: "ログアウト",
    theme: "テーマ",
    close: "閉じる",
    refresh: "更新",
    cancel: "キャンセル",
    save: "保存",
    loading: "読み込み中...",
    loadMore: "さらに読み込む",
    tableDensity: "テーブル密度",
    moreInfo: "詳細情報",
    error: "エラー",
    language: "言語",
    noResults: "結果が見つかりません",
    selectFilter: "フィルターを選択",
    textFilter: "テキストフィルター",
    all: "すべて",
    filter: "フィルター",
    noGroups: "グループなし",
    actions: {
      add: "追加",
      save: "保存",
      delete: "削除",
      edit: "編集",
      activate: "有効化",
      deactivate: "無効化",
    },
    columns: {
      permissionSets: "権限セット",
      username: "ユーザー名",
      firstName: "名前",
      lastName: "姓",
      email: "メール",
      status: "ステータス",
      groups: "グループ",
      created: "作成日",
      modified: "更新日",
      actions: "アクション",
    },
    status: {
      active: "アクティブ",
      inactive: "非アクティブ",
    },
  },
  translation: {
    common: {
      actions: {
        add: "追加",
        edit: "編集",
        delete: "削除",
        activate: "有効化",
        deactivate: "無効化",
        create: "作成",
      },
      tableDensity: "テーブル密度",
      theme: "テーマ",
      back: "戻る",
      loading: "読み込み中...",
      error: "何かが間違っています",
      save: "保存",
      cancel: "キャンセル",
      delete: "削除",
      edit: "編集",
      search: "検索",
      profile: "プロフィール",
      filterColumn: "フィルター",
      searchValue: "検索",
      logout: "ログアウト",
      language: "言語",
      alerts: "アラート",
      warnings: "警告",
      notifications: "通知",
      searchPlaceholder: "検索またはkey:valueを使用...",
      close: "閉じる",
      success: "成功",
      refresh: "更新",
      previous: "前へ",
      next: "次へ",
      show: "表示",
      all: "すべて",
      status: {
        active: "アクティブ",
        inactive: "非アクティブ",
      },
      rename: "名前を変更",
      root: "ルート",
      folder: "フォルダ",
      loadMore: "さらに読み込む",
      darkMode: "ダークモード",
      lightMode: "ライトモード",
      filter: "フィルター",
      textFilter: "テキストフィルター",
      selectFilter: "フィルターを選択",
      clearFilter: "フィルターをクリア",
      columns: {
        username: "ユーザー名",
        firstName: "名前",
        lastName: "姓",
        email: "メール",
        status: "ステータス",
        groups: "グループ",
        created: "作成日",
        modified: "更新日",
        actions: "アクション",
      },
      noGroups: "グループなし",
      select: "選択",
      moreInfo: "詳細情報",
    },
    users: {
      title: "ユーザー管理",
      search: "ユーザーを検索",
      description: "システムユーザーとそのアクセスを管理",
      form: {
        fields: {
          given_name: {
            label: "名前",
            tooltip: "ユーザーの名前を入力",
            errors: {
              required: "名前は必須です",
            },
          },
          family_name: {
            label: "姓",
            tooltip: "ユーザーの姓を入力",
            errors: {
              required: "姓は必須です",
            },
          },
          email: {
            label: "メール",
            tooltip: "ユーザーのメールアドレスを入力",
            errors: {
              required: "メールは必須です",
              invalid: "無効なメールアドレス",
            },
          },
          enabled: {
            label: "有効",
            tooltip: "ユーザーを有効または無効にする",
            errors: {
              required: "有効化は必須です",
            },
          },
          roles: {
            label: "ロール",
            tooltip: "ユーザーのロールを選択",
            errors: {
              required: "ロールは必須です",
            },
          },
          email_verified: {
            label: "メール認証済み",
            tooltip: "ユーザーのメールが認証済みかどうかを示す",
            errors: {
              required: "メール認証は必須です",
            },
          },
        },
      },
    },
    roles: {
      title: "ロール管理",
      description: "システムロールとその権限を管理",
      admin: "管理者",
      editor: "編集者",
      viewer: "閲覧者",
      actions: {
        addRole: "ロールを追加",
      },
    },
    columns: {
      username: "ユーザー名",
      firstName: "名前",
      lastName: "姓",
      email: "メール",
      status: "ステータス",
      groups: "グループ",
      created: "作成日",
      modified: "更新日",
      actions: "アクション",
    },
    actions: {
      addUser: "ユーザーを追加",
      edit: "ユーザーを編集",
      delete: "ユーザーを削除",
      activate: "ユーザーを有効化",
      deactivate: "ユーザーを無効化",
    },
    status: {
      active: "アクティブ",
      inactive: "非アクティブ",
    },
    errors: {
      loadFailed: "ユーザーの読み込みに失敗しました",
      saveFailed: "ユーザーの保存に失敗しました",
      deleteFailed: "ユーザーの削除に失敗しました",
    },
    navigation: {
      home: "ホーム",
      collections: "コレクション",
      settings: "設定",
    },
    home: {
      welcome: "Media Lakeへようこそ",
      description: "メディアファイルを効率的に管理・整理",
      statistics: "統計",
      collections: "コレクション",
      sharedCollections: "共有コレクション",
      favorites: "お気に入り",
      smartFolders: "スマートフォルダ",
      connectedStorage: "接続されたストレージ",
      sharing: "共有",
      comingSoon: "近日公開",
    },
    notifications: {
      "Pipeline Complete": "パイプライン完了",
      "Asset processing pipeline completed successfully":
        "アセット処理パイプラインが正常に完了しました",
      "Storage Warning": "ストレージ警告",
      "Storage capacity reaching 80%": "ストレージ容量が80%に達しています",
      "Pipeline Failed": "パイプライン失敗",
      "Video processing pipeline failed":
        "ビデオ処理パイプラインが失敗しました",
    },
    modal: {
      confirmDelete: "このアイテムを削除してもよろしいですか？",
      confirmAction: "このアクションを実行してもよろしいですか？",
      error: "エラーが発生しました",
      success: "操作が正常に完了しました",
    },
    executions: {
      title: "パイプライン実行",
      description: "パイプライン実行を監視・管理",
      searchPlaceholder: "パイプライン実行を検索...",
      columns: {
        pipelineName: "パイプライン名",
        status: "ステータス",
        startTime: "開始時刻",
        endTime: "終了時刻",
        duration: "期間",
        actions: "アクション",
      },
      status: {
        succeeded: "成功",
        failed: "失敗",
        running: "実行中",
        timedOut: "タイムアウト",
        aborted: "中止",
      },
      actions: {
        retryFromCurrent: "現在の位置から再試行",
        retryFromStart: "最初から再試行",
        viewDetails: "詳細を表示",
      },
      pagination: {
        page: "ページ {{page}} / {{total}}",
        showEntries: "{{count}}件を表示",
      },
    },
    s3Explorer: {
      filter: {
        label: "名前でフィルター",
      },
      error: {
        loading: "S3オブジェクトの読み込みエラー: {{message}}",
      },
      file: {
        info: "サイズ: {{size}} • ストレージクラス: {{storageClass}} • 更新日: {{modified}}",
      },
      menu: {
        rename: "名前を変更",
        delete: "削除",
      },
    },
    assets: {
      title: "アセット",
      connectedStorage: "接続されたストレージ",
    },
    metadata: {
      title: "近日公開",
      description:
        "メタデータ管理機能をお届けするために作業中です。お楽しみに！",
    },
    pipelines: {
      title: "パイプライン",
      description: "メディアとメタデータのパイプラインを管理",
      searchPlaceholder: "パイプラインを検索...",
      actions: {
        create: "新しいパイプラインを追加",
        deploy: "画像パイプラインをデプロイ",
        addNew: "新しいパイプラインを追加",
        viewAll: "すべてのパイプラインを表示",
      },
      search: "パイプラインを検索",
      deploy: "画像パイプラインをデプロイ",
      addNew: "新しいパイプラインを追加",
      columns: {
        name: "名前",
        creationDate: "作成日",
        system: "システム",
        type: "タイプ",
        actions: "アクション",
      },
      editor: {
        title: "パイプラインエディター",
        save: "パイプラインを保存",
        validate: "パイプラインを検証",
        sidebar: {
          title: "ノード",
          dragNodes: "ノードをキャンバスにドラッグ",
          loading: "ノードを読み込み中...",
          error: "ノードの読み込みエラー",
        },
        node: {
          configure: "{{type}}を設定",
          delete: "ノードを削除",
          edit: "ノードを編集",
        },
        edge: {
          title: "エッジラベルを編集",
          label: "エッジラベル",
          delete: "接続を削除",
        },
        modals: {
          error: {
            title: "エラー",
            incompatibleNodes:
              "前のノードの出力が対象ノードの入力と互換性がありません。",
            validation: "パイプライン検証に失敗しました",
          },
          delete: {
            title: "パイプラインを削除",
            message:
              "このパイプラインを削除してもよろしいですか？この操作は元に戻せません。",
            confirm: "削除を確認するためにパイプライン名を入力してください:",
          },
        },
        controls: {
          undo: "元に戻す",
          redo: "やり直し",
          zoomIn: "ズームイン",
          zoomOut: "ズームアウト",
          fitView: "ビューに合わせる",
          lockView: "ビューをロック",
        },
        notifications: {
          saved: "パイプラインが正常に保存されました",
          validated: "パイプライン検証が成功しました",
          error: {
            save: "パイプラインの保存に失敗しました",
            validation: "パイプライン検証に失敗しました",
            incompatibleNodes: "互換性のないノード接続",
          },
        },
      },
    },
    integrations: {
      title: "統合",
      description: "統合と接続を管理",
      addIntegration: "統合を追加",
      selectIntegration: "統合を選択",
      selectProvider: "プロバイダーを選択",
      configureIntegration: "統合を設定",
      deleteConfirmation: {
        title: "統合を削除",
        message: "この統合を削除してもよろしいですか？",
        warning:
          "警告: この統合を削除すると、それを使用するパイプラインが破損する可能性があります。",
      },
      form: {
        title: "統合を追加",
        fields: {
          nodeId: {
            label: "統合",
            tooltip: "統合プロバイダーを選択",
            errors: {
              required: "統合の選択が必要です",
            },
          },
          description: {
            label: "説明",
            tooltip: "この統合の説明を入力",
            helper: "この統合の簡単な説明",
            errors: {
              required: "説明が必要です",
            },
          },
          environmentId: {
            label: "環境",
            tooltip: "この統合の環境を選択",
            errors: {
              required: "環境の選択が必要です",
            },
          },
          enabled: {
            label: "有効",
            tooltip: "この統合を有効または無効にする",
            errors: {
              required: "有効化が必要です",
            },
          },
          auth: {
            type: {
              label: "認証タイプ",
              tooltip: "認証方法を選択",
              options: {
                awsIam: "AWS IAM",
                apiKey: "APIキー",
              },
              errors: {
                required: "認証タイプが必要です",
              },
            },
            credentials: {
              apiKey: {
                label: "APIキー",
                tooltip: "APIキーを入力",
                helper: "サービス認証用のAPIキー",
                errors: {
                  required: "APIキーが必要です",
                },
              },
              iamRole: {
                label: "IAMロール",
                tooltip: "IAMロールのARNを入力",
                errors: {
                  required: "IAMロールが必要です",
                },
              },
            },
          },
        },
        search: {
          placeholder: "統合を検索",
        },

        errors: {
          required: "このフィールドは必須です",
          nodeId: {
            unrecognized_keys: "無効な統合選択",
          },
        },
      },
      columns: {
        nodeName: "ノード名",
        environment: "環境",
        createdDate: "作成日",
        modifiedDate: "更新日",
        actions: "アクション",
      },

      settings: {
        environments: {
          title: "環境",
        },
      },
    },
  },
  groups: {
    actions: {
      addGroup: "グループを追加",
      editGroup: "グループを編集",
      deleteGroup: "グループを削除",
      createGroup: "グループを作成",
      manageGroups: "グループを管理",
    },
  },
  permissionSets: {
    noAssignments: "権限セットなし",
    actions: {
      addPermissionSet: "権限セットを追加",
      editPermissionSet: "権限セットを編集",
      deletePermissionSet: "権限セットを削除",
    },
  },
};
