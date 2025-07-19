export default {
  languages: {
    english: "אנגלית",
    german: "גרמנית",
    portuguese: "פורטוגזית",
    french: "צרפתית",
    chinese: "סינית",
    hindi: "הינדי",
    arabic: "ערבית",
    hebrew: "עברית",
    japanese: "יפנית",
    korean: "קוריאנית",
    spanish: "ספרדית",
  },
  assetsPage: {
    title: "נכסים",
    connectors: "מחברים",
    selectConnector: "בחר מחבר",
  },
  assetExplorer: {
    noConnectorSelected: "בחר מחבר כדי לצפות בנכסים",
    noAssetsFound: "לא נמצאו נכסים עבור מחבר זה",
    noIndexedAssets:
      'לא נמצאו נכסים ממודדים עבור מחבר זה עם הדלי "{{bucketName}}".',
    loadingAssets: "טוען נכסים...",
    menu: {
      rename: "שנה שם",
      share: "שתף",
      download: "הורד",
    },
    deleteDialog: {
      title: "אישור מחיקה",
      description:
        "האם אתה בטוח שברצונך למחוק נכס זה? פעולה זו אינה ניתנת לביטול.",
      cancel: "ביטול",
      confirm: "מחק",
    },
  },
  sidebar: {
    menu: {
      home: "בית",
      assets: "נכסים",
      pipelines: "צינורות",
      pipelineExecutions: "הרצת צינורות",
      settings: "הגדרות",
    },
    submenu: {
      system: "הגדרות מערכת",
      connectors: "מחברים",
      userManagement: "ניהול משתמשים",
      roles: "תפקידים",
      integrations: "אינטגרציות",
      environments: "סביבות",
    },
  },
  profile: {
    title: "פרופיל",
    description: "נהל את הגדרות החשבון והעדפותיך",
    changePhoto: "שנה תמונה",
    jobTitle: "תפקיד",
    organization: "ארגון",
    preferences: "העדפות",
    timezone: "אזור זמן",
    emailNotifications: "התראות דואר אלקטרוני",
    pushNotifications: "התראות דחיפה",
    changePassword: "שנה סיסמה",
    twoFactorAuth: "אימות דו-גורמי",
    appearance: "מראה",
  },
  app: {
    loading: "טוען...",
    errors: {
      loadingConfig: "שגיאה בטעינת תצורת AWS:",
      loadingUserAttributes: "שגיאה בטעינת מאפייני המשתמש:",
      signingOut: "שגיאה ביציאה:",
    },
    navigation: {
      preventedDuplicate: "מניעת ניווט כפול ל",
      navigating: "ניווט מ",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "חיפוש סמנטי",
    filters: {
      dateRange: "טווח תאריכים",
      contentType: "סוג תוכן",
      storageLocation: "מיקום אחסון",
      comingSoon: "סינונים נוספים בקרוב...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "שימוש באחסון",
      apiUsage: "שימוש ב-API",
      activeUsers: "משתמשים פעילים",
      systemLoad: "עומס מערכת",
    },
    errors: {
      userDeletionNotImplemented: "מחיקת משתמש אינה מיושמת עדיין.",
      userCreationNotImplemented: "יצירת משתמש אינה מיושמת עדיין.",
      userEditingNotImplemented: "עריכת משתמש אינה מיושמת עדיין.",
      analyticsExportNotImplemented: "ייצוא נתוני אנליטיקה אינו מיושם עדיין.",
      systemResetNotImplemented: "איפוס מערכת אינו מיושם עדיין.",
    },
    columns: {
      lastActive: "פעילות אחרונה",
    },
    buttons: {
      exportAnalytics: "ייצוא אנליטיקה",
      resetSystem: "אפס מערכת",
    },
  },
  integrations: {
    title: "אינטגרציות",
    selectProvider: "בחר אינטגרציה",
    selectIntegration: "בחר אינטגרציה",
    configureIntegration: "הגדר אינטגרציה",
    description: "נהל את האינטגרציות והחיבורים שלך",
    addIntegration: "הוסף אינטגרציה",
    form: {
      search: {
        placeholder: "חפש אינטגרציות",
      },
      title: "הוסף אינטגרציה",
      fields: {
        nodeId: {
          label: "אינטגרציה",
          tooltip: "בחר ספק אינטגרציה",
          errors: {
            required: "בחירת אינטגרציה הינה חובה",
          },
        },
        description: {
          label: "תיאור",
          tooltip: "ספק תיאור לאינטגרציה זו",
          helper: "תיאור קצר של אינטגרציה זו",
          errors: {
            required: "תיאור הינו חובה",
          },
        },
        environmentId: {
          label: "סביבה",
          tooltip: "בחר את הסביבה לאינטגרציה זו",
          errors: {
            required: "בחירת סביבה הינה חובה",
          },
        },
        enabled: {
          label: "מאופשר",
          tooltip: "הפעל או השבת אינטגרציה זו",
          errors: {
            required: "אופציית הפעלה הינה חובה",
          },
        },
        auth: {
          type: {
            label: "סוג אימות",
            tooltip: "בחר את שיטת האימות",
            options: {
              awsIam: "AWS IAM",
              apiKey: "מפתח API",
            },
            errors: {
              required: "סוג אימות הינו חובה",
            },
          },
          credentials: {
            apiKey: {
              label: "מפתח API",
              tooltip: "הזן את מפתח ה-API שלך",
              helper: "מפתח API לאימות עם השירות",
              errors: {
                required: "מפתח API הינו חובה",
              },
            },
            iamRole: {
              label: "תפקיד IAM",
              tooltip: "הזן את ARN של תפקיד ה-IAM",
              errors: {
                required: "תפקיד IAM הינו חובה",
              },
            },
          },
        },
      },
      errors: {
        required: "שדה זה הינו חובה",
        nodeId: {
          unrecognized_keys: "בחירת אינטגרציה לא תקינה",
        },
      },
    },
  },
  pipelines: {
    title: "צינורות",
    description: "נהל את צינורות המדיה והמטא-דאטה שלך",
    searchPlaceholder: "חפש צינורות...",
    actions: {
      create: "הוסף צינור חדש",
      import: "ייבא צינור",
    },
  },
  executions: {
    title: "הרצת צינורות",
    description: "עקוב ונטר את הרצת הצינורות שלך",
    searchPlaceholder: "חפש הרצת צינורות...",
    columns: {
      pipelineName: "שם הצינור",
      status: "מצב",
      startTime: "זמן התחלה",
      endTime: "זמן סיום",
      duration: "משך",
      actions: "פעולות",
    },
    actions: {
      retryFromCurrent: "נסה שוב מהמצב הנוכחי",
      retryFromStart: "נסה שוב מההתחלה",
      viewDetails: "צפה בפרטים",
    },
  },
  users: {
    title: "ניהול משתמשים",
    description: "נהל את משתמשי המערכת וההרשאות שלהם",
    actions: {
      addUser: "הוסף משתמש",
    },
    form: {
      title: {
        add: "הוסף משתמש",
      },
      fields: {
        given_name: {
          label: "שם פרטי",
          tooltip: "הזן את השם הפרטי של המשתמש",
          helper: "",
        },
        family_name: {
          label: "שם משפחה",
          tooltip: "הזן את שם המשפחה של המשתמש",
          helper: "",
        },
        email: {
          label: "אימייל",
          tooltip: "הזן את כתובת האימייל של המשתמש",
          helper: "",
        },
        roles: {
          label: "תפקידים",
          tooltip: "בחר את התפקידים למשתמש",
          options: {
            Admin: "מנהל",
            Editor: "עורך",
            Viewer: "צופה",
          },
        },
        email_verified: {
          label: "אימות אימייל",
          tooltip: "סמן אם כתובת האימייל של המשתמש אומתה",
        },
        enabled: {
          label: "מאופשר",
          tooltip: "הפעל או השבת את המשתמש",
        },
      },
    },
    roles: {
      admin: "מנהל",
      editor: "עורך",
      viewer: "צופה",
    },
  },
  roles: {
    title: "ניהול תפקידים",
    description: "נהל את התפקידים במערכת ואת ההרשאות שלהם",
    actions: {
      addRole: "הוסף תפקיד",
    },
  },
  settings: {
    environments: {
      title: "סביבות",
      description: "נהל את הסביבות במערכת והגדרותיהן",
      addButton: "הוסף סביבה",
      searchPlaceholder: "חפש סביבות",
      createTitle: "צור סביבה",
      form: {
        name: "שם הסביבה",
        region: "אזור",
        status: {
          name: "מצב",
          active: "פעיל",
          disabled: "מבוטל",
        },
        costCenter: "מרכז עלויות",
        team: "צוות",
      },
    },
    systemSettings: {
      title: "הגדרות מערכת",
      tabs: {
        search: "חיפוש",
        notifications: "התראות",
        security: "אבטחה",
        performance: "ביצועים",
      },
      search: {
        title: "תצורת חיפוש",
        description: "הגדר את ספק החיפוש לשיפור יכולות החיפוש בנכסי המדיה שלך.",
        provider: "ספק חיפוש:",
        configureProvider: "הגדר ספק חיפוש",
        editProvider: "ערוך ספק",
        resetProvider: "אפס ספק",
        providerDetails: "פרטי הספק",
        providerName: "שם הספק",
        apiKey: "מפתח API",
        endpoint: "כתובת URL של נקודת הקצה (אופציונלי)",
        enabled: "חיפוש מאופשר",
        noProvider: "לא הוגדר ספק חיפוש.",
        configurePrompt: "הגדר את Twelve Labs כדי להפעיל את יכולות החיפוש.",
      },
      notifications: {
        title: "הגדרות התראות",
        comingSoon: "הגדרות התראות יגיעו בקרוב.",
      },
      security: {
        title: "הגדרות אבטחה",
        comingSoon: "הגדרות אבטחה יגיעו בקרוב.",
      },
      performance: {
        title: "הגדרות ביצועים",
        comingSoon: "הגדרות ביצועים יגיעו בקרוב.",
      },
    },
    groups: {
      actions: {
        addGroup: "הוסף קבוצה",
        editGroup: "ערוך קבוצה",
        deleteGroup: "מחק קבוצה",
        createGroup: "צור קבוצה",
        manageGroups: "נהל קבוצות",
      },
    },
    permissionSets: {
      noAssignments: "אין סטי הרשאות",
      actions: {
        addPermissionSet: "הוסף סט הרשאות",
        editPermissionSet: "ערוך סט הרשאות",
        deletePermissionSet: "מחק סט הרשאות",
      },
    },
  },
  common: {
    select: "בחר",
    back: "חזור",
    search: "חפש",
    profile: "פרופיל",
    logout: "התנתק",
    theme: "ערכת נושא",
    close: "סגור",
    refresh: "רענן",
    cancel: "ביטול",
    save: "שמור",
    loading: "טוען...",
    loadMore: "טען עוד",
    tableDensity: "צפיפות טבלה",
    moreInfo: "מידע נוסף",
    error: "שגיאה",
    language: "שפה",
    delete: "מחק",
    create: "צור",
    actions: {
      add: "הוסף",
    },
    columns: {
      username: "שם משתמש",
      firstName: "שם פרטי",
      lastName: "שם משפחה",
      email: "אימייל",
      status: "מצב",
      groups: "קבוצות",
      created: "נוצר",
      modified: "עודכן",
      actions: "פעולות",
    },
    status: {
      active: "פעיל",
      inactive: "לא פעיל",
    },
  },
  translation: {
    common: {
      actions: {
        add: "הוסף",
        edit: "ערוך",
        delete: "מחק",
        activate: "הפעל",
        deactivate: "השבת",
        create: "צור",
      },
      tableDensity: "צפיפות טבלה",
      theme: "ערכת נושא",
      back: "חזור",
      loading: "טוען...",
      error: "משהו השתבש",
      save: "שמור",
      cancel: "ביטול",
      delete: "מחק",
      edit: "ערוך",
      search: "חפש",
      profile: "פרופיל",
      filterColumn: "סינון",
      searchValue: "חפש",
      logout: "התנתק",
      language: "שפה",
      alerts: "התראות",
      warnings: "אזהרות",
      notifications: "התראות",
      searchPlaceholder: "חפש או השתמש ב key:value...",
      close: "סגור",
      success: "הצלחה",
      refresh: "רענן",
      previous: "קודם",
      next: "הבא",
      show: "הצג",
      all: "הכל",
      status: {
        active: "פעיל",
        inactive: "לא פעיל",
      },
      rename: "שנה שם",
      root: "שורש",
      folder: "תיקייה",
      loadMore: "טען עוד",
      darkMode: "מצב כהה",
      lightMode: "מצב בהיר",
      filter: "סנן",
      textFilter: "סינון טקסט",
      selectFilter: "בחר סינון",
      clearFilter: "נקה סינון",
      columns: {
        username: "שם משתמש",
        firstName: "שם פרטי",
        lastName: "שם משפחה",
        email: "אימייל",
        status: "מצב",
        groups: "קבוצות",
        created: "נוצר",
        modified: "עודכן",
        actions: "פעולות",
      },
      noGroups: "אין קבוצות",
      select: "בחר",
      moreInfo: "מידע נוסף",
    },
    users: {
      title: "ניהול משתמשים",
      search: "חפש משתמשים",
      description: "נהל את משתמשי המערכת ואת ההרשאות שלהם",
      form: {
        fields: {
          given_name: {
            label: "שם פרטי",
            tooltip: "הזן את השם הפרטי של המשתמש",
            errors: {
              required: "שם פרטי הוא חובה",
            },
          },
          family_name: {
            label: "שם משפחה",
            tooltip: "הזן את שם המשפחה של המשתמש",
            errors: {
              required: "שם משפחה הוא חובה",
            },
          },
          email: {
            label: "אימייל",
            tooltip: "הזן את כתובת האימייל של המשתמש",
            errors: {
              required: "אימייל הוא חובה",
              invalid: "כתובת אימייל לא חוקית",
            },
          },
          enabled: {
            label: "מאופשר",
            tooltip: "הפעל או השבת את המשתמש",
            errors: {
              required: "יש לאפשר את המשתמש",
            },
          },
          roles: {
            label: "תפקידים",
            tooltip: "בחר את התפקידים למשתמש",
            errors: {
              required: "תפקידים הם חובה",
            },
          },
          email_verified: {
            label: "אימות אימייל",
            tooltip: "סמן אם כתובת האימייל של המשתמש אומתה",
            errors: {
              required: "אימות אימייל הוא חובה",
            },
          },
        },
      },
    },
    roles: {
      title: "ניהול תפקידים",
      description: "נהל את התפקידים במערכת ואת ההרשאות שלהם",
      admin: "מנהל",
      editor: "עורך",
      viewer: "צופה",
      actions: {
        addRole: "הוסף תפקיד",
      },
    },
    columns: {
      username: "שם משתמש",
      firstName: "שם פרטי",
      lastName: "שם משפחה",
      email: "אימייל",
      status: "מצב",
      groups: "קבוצות",
      created: "נוצר",
      modified: "עודכן",
      actions: "פעולות",
    },
    actions: {
      addUser: "הוסף משתמש",
      edit: "ערוך משתמש",
      delete: "מחק משתמש",
      activate: "הפעל משתמש",
      deactivate: "השבת משתמש",
    },
    status: {
      active: "פעיל",
      inactive: "לא פעיל",
    },
    errors: {
      loadFailed: "טעינת המשתמשים נכשלה",
      saveFailed: "שמירת המשתמש נכשלה",
      deleteFailed: "מחיקת המשתמש נכשלה",
    },
    navigation: {
      home: "בית",
      collections: "אוספים",
      settings: "הגדרות",
    },
    home: {
      welcome: "ברוכים הבאים ל-Media Lake",
      description: "נהל את קבצי המדיה שלך ביעילות",
      statistics: "סטטיסטיקות",
      collections: "אוספים",
      sharedCollections: "אוספים משותפים",
      favorites: "מועדפים",
      smartFolders: "תיקיות חכמות",
      connectedStorage: "אחסון מחובר",
      sharing: "שיתוף",
      comingSoon: "בקרוב",
    },
    notifications: {
      "Pipeline Complete": "צינור הושלם",
      "Asset processing pipeline completed successfully":
        "צינור עיבוד הנכסים הושלם בהצלחה",
      "Storage Warning": "אזהרת אחסון",
      "Storage capacity reaching 80%": "קיבולת האחסון מתקרבת ל-80%",
      "Pipeline Failed": "הצינור נכשל",
      "Video processing pipeline failed": "צינור עיבוד הווידאו נכשל",
    },
    modal: {
      confirmDelete: "האם אתה בטוח שברצונך למחוק פריט זה?",
      confirmAction: "האם אתה בטוח שברצונך לבצע פעולה זו?",
      error: "אירעה שגיאה",
      success: "הפעולה הושלמה בהצלחה",
    },
    executions: {
      title: "הרצת צינורות",
      description: "עקוב ונטר את הרצת הצינורות שלך",
      searchPlaceholder: "חפש הרצת צינורות...",
      columns: {
        pipelineName: "שם הצינור",
        status: "מצב",
        startTime: "זמן התחלה",
        endTime: "זמן סיום",
        duration: "משך",
        actions: "פעולות",
      },
      status: {
        succeeded: "הצליח",
        failed: "נכשל",
        running: "רץ",
        timedOut: "פג תוקף",
        aborted: "בוטל",
      },
      actions: {
        retryFromCurrent: "נסה שוב מהמצב הנוכחי",
        retryFromStart: "נסה שוב מההתחלה",
        viewDetails: "צפה בפרטים",
      },
      pagination: {
        page: "עמוד {{page}} מתוך {{total}}",
        showEntries: "הצג {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "סנן לפי שם",
      },
      error: {
        loading: "שגיאה בטעינת עצמים מ-S3: {{message}}",
      },
      file: {
        info: "גודל: {{size}} • מחלקת אחסון: {{storageClass}} • עודכן: {{modified}}",
      },
      menu: {
        rename: "שנה שם",
        delete: "מחק",
      },
    },
    assets: {
      title: "נכסים",
      connectedStorage: "אחסון מחובר",
    },
    metadata: {
      title: "בקרוב",
      description:
        "אנחנו עובדים כדי להביא לך יכולות ניהול מטא-דאטה. הישאר מעודכן!",
    },
    pipelines: {
      title: "צינורות",
      description: "נהל את צינורות המדיה והמטא-דאטה שלך",
      searchPlaceholder: "חפש צינורות...",
      actions: {
        create: "הוסף צינור חדש",
        deploy: "פרוס צינור תמונות",
        addNew: "הוסף צינור חדש",
        viewAll: "הצג את כל הצינורות",
      },
      search: "חפש צינורות",
      deploy: "פרוס צינור תמונות",
      addNew: "הוסף צינור חדש",
      columns: {
        name: "שם",
        creationDate: "תאריך יצירה",
        system: "מערכת",
        type: "סוג",
        actions: "פעולות",
      },
      editor: {
        title: "עורך צינורות",
        save: "שמור צינור",
        validate: "אמת צינור",
        sidebar: {
          title: "צמתים",
          dragNodes: "גרור צמתים אל הקנבס",
          loading: "טוען צמתים...",
          error: "שגיאה בטעינת צמתים",
        },
        node: {
          configure: "הגדר {{type}}",
          delete: "מחק צומת",
          edit: "ערוך צומת",
        },
        edge: {
          title: "ערוך תווית קו",
          label: "תווית קו",
          delete: "מחק חיבור",
        },
        modals: {
          error: {
            title: "שגיאה",
            incompatibleNodes: "פלט הצומת הקודם אינו תואם לקלט הצומת היעד.",
            validation: "אימות הצינור נכשל",
          },
          delete: {
            title: "מחק צינור",
            message:
              "האם אתה בטוח שברצונך למחוק צינור זה? פעולה זו אינה ניתנת לביטול.",
            confirm: "הקלד את שם הצינור לאישור המחיקה:",
          },
        },
        controls: {
          undo: "ביטול",
          redo: "ביצוע מחדש",
          zoomIn: "הגדל",
          zoomOut: "הקטן",
          fitView: "התאם תצוגה",
          lockView: "נעל תצוגה",
        },
        notifications: {
          saved: "הצינור נשמר בהצלחה",
          validated: "אימות הצינור הצליח",
          error: {
            save: "שמירת הצינור נכשלה",
            validation: "אימות הצינור נכשל",
            incompatibleNodes: "חיבור צמתים אינו תואם",
          },
        },
      },
    },
    integrations: {
      title: "אינטגרציות",
      description: "נהל את האינטגרציות והחיבורים שלך",
      addIntegration: "הוסף אינטגרציה",
      selectIntegration: "בחר אינטגרציה",
      selectProvider: "בחר ספק",
      configureIntegration: "הגדר אינטגרציה",
      form: {
        title: "הוסף אינטגרציה",
        fields: {
          nodeId: {
            label: "אינטגרציה",
            tooltip: "בחר ספק אינטגרציה",
            errors: {
              required: "בחירת אינטגרציה הינה חובה",
            },
          },
          description: {
            label: "תיאור",
            tooltip: "ספק תיאור לאינטגרציה זו",
            errors: {
              required: "תיאור הינו חובה",
            },
          },
          environmentId: {
            label: "סביבה",
            tooltip: "בחר את הסביבה לאינטגרציה זו",
            errors: {
              required: "בחירת סביבה הינה חובה",
            },
          },
          enabled: {
            label: "מאופשר",
            tooltip: "הפעל או השבת אינטגרציה זו",
            errors: {
              required: "אופציית הפעלה הינה חובה",
            },
          },
          auth: {
            type: {
              label: "סוג אימות",
              tooltip: "בחר את שיטת האימות",
              options: {
                awsIam: "AWS IAM",
                apiKey: "מפתח API",
              },
              errors: {
                required: "סוג אימות הינו חובה",
              },
            },
            credentials: {
              apiKey: {
                label: "מפתח API",
                tooltip: "הזן את מפתח ה-API שלך",
                errors: {
                  required: "מפתח API הינו חובה",
                },
              },
              iamRole: {
                label: "תפקיד IAM",
                tooltip: "הזן את ARN של תפקיד ה-IAM",
                errors: {
                  required: "תפקיד IAM הינו חובה",
                },
              },
            },
          },
        },
        search: {
          placeholder: "חפש אינטגרציות",
        },
        errors: {
          required: "שדה זה הינו חובה",
          nodeId: {
            unrecognized_keys: "בחירת אינטגרציה לא תקינה",
          },
        },
      },
      columns: {
        nodeName: "שם הצומת",
        environment: "סביבה",
        createdDate: "תאריך יצירה",
        modifiedDate: "תאריך עדכון",
        actions: "פעולות",
      },
      settings: {
        environments: {
          title: "סביבות",
        },
      },
    },
    groups: {
      actions: {
        addGroup: "הוסף קבוצה",
        editGroup: "ערוך קבוצה",
        deleteGroup: "מחק קבוצה",
        createGroup: "צור קבוצה",
        manageGroups: "נהל קבוצות",
      },
    },
    permissionSets: {
      noAssignments: "אין סטי הרשאות",
      actions: {
        addPermissionSet: "הוסף סט הרשאות",
        editPermissionSet: "ערוך סט הרשאות",
        deletePermissionSet: "מחק סט הרשאות",
      },
    },
  },
};
