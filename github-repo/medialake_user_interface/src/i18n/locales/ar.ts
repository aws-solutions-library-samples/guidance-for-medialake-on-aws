export default {
  languages: {
    english: "الإنجليزية",
    german: "الألمانية",
    portuguese: "البرتغالية",
    french: "الفرنسية",
    chinese: "الصينية",
    hindi: "الهندية",
    arabic: "العربية",
    hebrew: "العبرية",
    japanese: "اليابانية",
    korean: "الكورية",
    spanish: "الإسبانية",
  },
  assetsPage: {
    title: "الأصول",
    connectors: "الموصلات",
    selectConnector: "اختر موصل",
  },
  assetExplorer: {
    noConnectorSelected: "اختر موصل لعرض الأصول",
    noAssetsFound: "لم يتم العثور على أصول لهذا الموصل",
    noIndexedAssets:
      'لم يتم العثور على أصول مفهرسة لهذا الموصل في الحاوية "{{bucketName}}".',
    loadingAssets: "جارٍ تحميل الأصول...",
    menu: {
      rename: "إعادة التسمية",
      share: "مشاركة",
      download: "تنزيل",
    },
    deleteDialog: {
      title: "تأكيد الحذف",
      description:
        "هل أنت متأكد أنك تريد حذف هذا الأصل؟ لا يمكن التراجع عن هذا الإجراء.",
      cancel: "إلغاء",
      confirm: "حذف",
    },
  },
  sidebar: {
    menu: {
      home: "الرئيسية",
      assets: "الأصول",
      pipelines: "خطوط الأنابيب",
      pipelineExecutions: "تنفيذ خطوط الأنابيب",
      settings: "الإعدادات",
    },
    submenu: {
      system: "إعدادات النظام",
      connectors: "الموصلات",
      userManagement: "إدارة المستخدمين",
      roles: "الأدوار",
      integrations: "التكاملات",
      environments: "البيئات",
    },
  },
  profile: {
    title: "الملف الشخصي",
    description: "قم بإدارة إعدادات حسابك وتفضيلاتك",
    changePhoto: "تغيير الصورة",
    jobTitle: "المسمى الوظيفي",
    organization: "المنظمة",
    preferences: "التفضيلات",
    timezone: "المنطقة الزمنية",
    emailNotifications: "إشعارات البريد الإلكتروني",
    pushNotifications: "إشعارات الدفع",
    changePassword: "تغيير كلمة المرور",
    twoFactorAuth: "المصادقة الثنائية",
    appearance: "المظهر",
  },
  app: {
    loading: "جارٍ التحميل...",
    errors: {
      loadingConfig: "خطأ في تحميل إعدادات AWS:",
      loadingUserAttributes: "خطأ في تحميل سمات المستخدم:",
      signingOut: "خطأ في تسجيل الخروج:",
    },
    navigation: {
      preventedDuplicate: "تم منع التنقل المكرر إلى",
      navigating: "جارٍ التنقل من",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "البحث الدلالي",
    filters: {
      dateRange: "نطاق التاريخ",
      contentType: "نوع المحتوى",
      storageLocation: "مكان التخزين",
      comingSoon: "المزيد من الفلاتر قادمة قريباً...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "استخدام التخزين",
      apiUsage: "استخدام API",
      activeUsers: "المستخدمون النشطون",
      systemLoad: "عبء النظام",
    },
    errors: {
      userDeletionNotImplemented: "لم يتم تنفيذ حذف المستخدم بعد.",
      userCreationNotImplemented: "لم يتم تنفيذ إنشاء المستخدم بعد.",
      userEditingNotImplemented: "لم يتم تنفيذ تعديل المستخدم بعد.",
      analyticsExportNotImplemented: "لم يتم تنفيذ تصدير التحليلات بعد.",
      systemResetNotImplemented: "لم يتم تنفيذ إعادة تعيين النظام بعد.",
    },
    columns: {
      lastActive: "آخر نشاط",
    },
    buttons: {
      exportAnalytics: "تصدير التحليلات",
      resetSystem: "إعادة تعيين النظام",
    },
  },
  integrations: {
    title: "التكاملات",
    selectProvider: "اختر التكامل",
    selectIntegration: "اختر التكامل",
    configureIntegration: "تكوين التكامل",
    description: "قم بإدارة تكاملاتك واتصالاتك",
    addIntegration: "إضافة تكامل",
    form: {
      search: {
        placeholder: "ابحث عن التكاملات",
      },
      title: "إضافة تكامل",
      fields: {
        nodeId: {
          label: "التكامل",
          tooltip: "اختر مزود التكامل",
          errors: {
            required: "اختيار التكامل مطلوب",
          },
        },
        description: {
          label: "الوصف",
          tooltip: "قم بتوفير وصف لهذا التكامل",
          helper: "وصف موجز لهذا التكامل",
          errors: {
            required: "الوصف مطلوب",
          },
        },
        environmentId: {
          label: "البيئة",
          tooltip: "اختر البيئة لهذا التكامل",
          errors: {
            required: "اختيار البيئة مطلوب",
          },
        },
        enabled: {
          label: "مُفعل",
          tooltip: "فعّل أو عطّل هذا التكامل",
          errors: {
            required: "التفعيل مطلوب",
          },
        },
        auth: {
          type: {
            label: "نوع المصادقة",
            tooltip: "اختر طريقة المصادقة",
            options: {
              awsIam: "AWS IAM",
              apiKey: "مفتاح API",
            },
            errors: {
              required: "نوع المصادقة مطلوب",
            },
          },
          credentials: {
            apiKey: {
              label: "مفتاح API",
              tooltip: "أدخل مفتاح API الخاص بك",
              helper: "مفتاح API للمصادقة مع الخدمة",
              errors: {
                required: "مفتاح API مطلوب",
              },
            },
            iamRole: {
              label: "دور IAM",
              tooltip: "أدخل ARN لدور IAM",
              errors: {
                required: "دور IAM مطلوب",
              },
            },
          },
        },
      },
      errors: {
        required: "هذا الحقل مطلوب",
        nodeId: {
          unrecognized_keys: "اختيار التكامل غير صالح",
        },
      },
    },
  },
  pipelines: {
    title: "خطوط الأنابيب",
    description: "قم بإدارة خطوط أنابيب الوسائط والبيانات الوصفية الخاصة بك",
    searchPlaceholder: "ابحث عن خطوط الأنابيب...",
    actions: {
      create: "إضافة خط أنابيب جديد",
      import: "استيراد خط أنابيب",
    },
  },
  executions: {
    title: "تنفيذ خطوط الأنابيب",
    description: "راقب وأدر تنفيذ خطوط الأنابيب الخاصة بك",
    searchPlaceholder: "ابحث عن تنفيذ خطوط الأنابيب...",
    columns: {
      pipelineName: "اسم خط الأنابيب",
      status: "الحالة",
      startTime: "وقت البدء",
      endTime: "وقت الانتهاء",
      duration: "المدة",
      actions: "الإجراءات",
    },
    actions: {
      retryFromCurrent: "أعد المحاولة من النقطة الحالية",
      retryFromStart: "أعد المحاولة من البداية",
      viewDetails: "عرض التفاصيل",
    },
  },
  users: {
    title: "إدارة المستخدمين",
    description: "قم بإدارة مستخدمي النظام ووصولهم",
    actions: {
      addUser: "إضافة مستخدم",
    },
    form: {
      title: {
        add: "إضافة مستخدم",
      },
      fields: {
        given_name: {
          label: "الاسم الأول",
          tooltip: "أدخل الاسم الأول للمستخدم",
          helper: "",
        },
        family_name: {
          label: "اسم العائلة",
          tooltip: "أدخل اسم العائلة للمستخدم",
          helper: "",
        },
        email: {
          label: "البريد الإلكتروني",
          tooltip: "أدخل عنوان البريد الإلكتروني للمستخدم",
          helper: "",
        },
        roles: {
          label: "الأدوار",
          tooltip: "اختر الأدوار للمستخدم",
          options: {
            Admin: "المسؤول",
            Editor: "المحرر",
            Viewer: "المشاهد",
          },
        },
        email_verified: {
          label: "تم التحقق من البريد الإلكتروني",
          tooltip: "أشر إلى ما إذا تم التحقق من بريد المستخدم الإلكتروني",
        },
        enabled: {
          label: "مُفعل",
          tooltip: "فعّل أو عطّل المستخدم",
        },
      },
    },
    roles: {
      admin: "المسؤول",
      editor: "المحرر",
      viewer: "المشاهد",
    },
  },
  roles: {
    title: "إدارة الأدوار",
    description: "قم بإدارة أدوار النظام وأذوناتهم",
    actions: {
      addRole: "إضافة دور",
    },
  },
  settings: {
    environments: {
      title: "البيئات",
      description: "قم بإدارة بيئات النظام وتكويناتها",
      addButton: "إضافة بيئة",
      searchPlaceholder: "ابحث عن البيئات",
      createTitle: "إنشاء بيئة",
      form: {
        name: "اسم البيئة",
        region: "المنطقة",
        status: {
          name: "الحالة",
          active: "نشط",
          disabled: "معطل",
        },
        costCenter: "مركز التكلفة",
        team: "الفريق",
      },
    },
    systemSettings: {
      title: "إعدادات النظام",
      tabs: {
        search: "البحث",
        notifications: "الإشعارات",
        security: "الأمان",
        performance: "الأداء",
      },
      search: {
        title: "إعدادات البحث",
        description:
          "قم بتكوين مزود البحث لتحسين قدرات البحث عبر أصول الوسائط الخاصة بك.",
        provider: "مزود البحث:",
        configureProvider: "تكوين مزود البحث",
        editProvider: "تعديل المزود",
        resetProvider: "إعادة تعيين المزود",
        providerDetails: "تفاصيل المزود",
        providerName: "اسم المزود",
        apiKey: "مفتاح API",
        endpoint: "عنوان URL للنقطة النهاية (اختياري)",
        enabled: "تمكين البحث",
        noProvider: "لم يتم تكوين مزود بحث.",
        configurePrompt: "قم بتكوين Twelve Labs لتمكين قدرات البحث.",
      },
      notifications: {
        title: "إعدادات الإشعارات",
        comingSoon: "الإعدادات ستتوفر قريباً.",
      },
      security: {
        title: "إعدادات الأمان",
        comingSoon: "الإعدادات ستتوفر قريباً.",
      },
      performance: {
        title: "إعدادات الأداء",
        comingSoon: "الإعدادات ستتوفر قريباً.",
      },
    },
    groups: {
      actions: {
        addGroup: "إضافة مجموعة",
        editGroup: "تعديل المجموعة",
        deleteGroup: "حذف المجموعة",
        createGroup: "إنشاء مجموعة",
        manageGroups: "إدارة المجموعات",
      },
    },
    permissionSets: {
      noAssignments: "لا توجد مجموعات أذونات",
      actions: {
        addPermissionSet: "إضافة مجموعة أذونات",
        editPermissionSet: "تعديل مجموعة الأذونات",
        deletePermissionSet: "حذف مجموعة الأذونات",
      },
    },
  },
  common: {
    select: "اختر",
    back: "رجوع",
    search: "بحث",
    profile: "الملف الشخصي",
    logout: "تسجيل الخروج",
    theme: "السمة",
    close: "إغلاق",
    refresh: "تحديث",
    cancel: "إلغاء",
    save: "حفظ",
    loading: "جارٍ التحميل...",
    loadMore: "تحميل المزيد",
    tableDensity: "كثافة الجدول",
    moreInfo: "مزيد من المعلومات",
    error: "خطأ",
    language: "اللغة",
    delete: "حذف",
    create: "إنشاء",
    actions: {
      add: "إضافة",
    },
    columns: {
      username: "اسم المستخدم",
      firstName: "الاسم الأول",
      lastName: "اسم العائلة",
      email: "البريد الإلكتروني",
      status: "الحالة",
      groups: "المجموعات",
      created: "تاريخ الإنشاء",
      modified: "تاريخ التعديل",
      actions: "الإجراءات",
    },
    status: {
      active: "نشط",
      inactive: "غير نشط",
    },
  },
  translation: {
    common: {
      actions: {
        add: "إضافة",
        edit: "تعديل",
        delete: "حذف",
        activate: "تفعيل",
        deactivate: "تعطيل",
        create: "إنشاء",
      },
      tableDensity: "كثافة الجدول",
      theme: "السمة",
      back: "رجوع",
      loading: "جارٍ التحميل...",
      error: "حدث خطأ ما",
      save: "حفظ",
      cancel: "إلغاء",
      delete: "حذف",
      edit: "تعديل",
      search: "بحث",
      profile: "الملف الشخصي",
      filterColumn: "تصفية العمود",
      searchValue: "بحث",
      logout: "تسجيل الخروج",
      language: "اللغة",
      alerts: "تنبيهات",
      warnings: "تحذيرات",
      notifications: "إشعارات",
      searchPlaceholder: "ابحث أو استخدم المفتاح:القيمة...",
      close: "إغلاق",
      success: "نجاح",
      refresh: "تحديث",
      previous: "السابق",
      next: "التالي",
      show: "عرض",
      all: "الكل",
      status: {
        active: "نشط",
        inactive: "غير نشط",
      },
      rename: "إعادة التسمية",
      root: "الجذر",
      folder: "المجلد",
      loadMore: "تحميل المزيد",
      darkMode: "الوضع الداكن",
      lightMode: "الوضع الفاتح",
      filter: "تصفية",
      textFilter: "تصفية نصية",
      selectFilter: "اختر الفلتر",
      clearFilter: "مسح الفلتر",
      columns: {
        username: "اسم المستخدم",
        firstName: "الاسم الأول",
        lastName: "اسم العائلة",
        email: "البريد الإلكتروني",
        status: "الحالة",
        groups: "المجموعات",
        created: "تاريخ الإنشاء",
        modified: "تاريخ التعديل",
        actions: "الإجراءات",
      },
      noGroups: "لا توجد مجموعات",
      select: "اختر",
      moreInfo: "مزيد من المعلومات",
    },
    users: {
      title: "إدارة المستخدمين",
      search: "ابحث عن المستخدمين",
      description: "قم بإدارة مستخدمي النظام ووصولهم",
      form: {
        fields: {
          given_name: {
            label: "الاسم الأول",
            tooltip: "أدخل الاسم الأول للمستخدم",
            errors: {
              required: "الاسم الأول مطلوب",
            },
          },
          family_name: {
            label: "اسم العائلة",
            tooltip: "أدخل اسم العائلة للمستخدم",
            errors: {
              required: "اسم العائلة مطلوب",
            },
          },
          email: {
            label: "البريد الإلكتروني",
            tooltip: "أدخل عنوان البريد الإلكتروني للمستخدم",
            errors: {
              required: "البريد الإلكتروني مطلوب",
              invalid: "عنوان البريد الإلكتروني غير صالح",
            },
          },
          enabled: {
            label: "مُفعل",
            tooltip: "فعّل أو عطّل المستخدم",
            errors: {
              required: "التفعيل مطلوب",
            },
          },
          roles: {
            label: "الأدوار",
            tooltip: "اختر الأدوار للمستخدم",
            errors: {
              required: "الأدوار مطلوبة",
            },
          },
          email_verified: {
            label: "تم التحقق من البريد الإلكتروني",
            tooltip: "أشر إلى ما إذا تم التحقق من بريد المستخدم الإلكتروني",
            errors: {
              required: "التحقق من البريد الإلكتروني مطلوب",
            },
          },
        },
      },
    },
    roles: {
      title: "إدارة الأدوار",
      description: "قم بإدارة أدوار النظام وأذوناتهم",
      admin: "المسؤول",
      editor: "المحرر",
      viewer: "المشاهد",
      actions: {
        addRole: "إضافة دور",
      },
    },
    columns: {
      username: "اسم المستخدم",
      firstName: "الاسم الأول",
      lastName: "اسم العائلة",
      email: "البريد الإلكتروني",
      status: "الحالة",
      groups: "المجموعات",
      created: "تاريخ الإنشاء",
      modified: "تاريخ التعديل",
      actions: "الإجراءات",
    },
    actions: {
      addUser: "إضافة مستخدم",
      edit: "تعديل المستخدم",
      delete: "حذف المستخدم",
      activate: "تفعيل المستخدم",
      deactivate: "تعطيل المستخدم",
    },
    status: {
      active: "نشط",
      inactive: "غير نشط",
    },
    errors: {
      loadFailed: "فشل تحميل المستخدمين",
      saveFailed: "فشل في حفظ المستخدم",
      deleteFailed: "فشل في حذف المستخدم",
    },
    navigation: {
      home: "الرئيسية",
      collections: "المجموعات",
      settings: "الإعدادات",
    },
    home: {
      welcome: "مرحبًا بكم في Media Lake",
      description: "إرشادات لوسائطك وبياناتك الوصفية وسير العمل.",
      statistics: "الإحصائيات",
      collections: "المجموعات",
      sharedCollections: "المجموعات المشتركة",
      favorites: "المفضلة",
      smartFolders: "المجلدات الذكية",
      connectedStorage: "التخزين المتصل",
      sharing: "المشاركة",
      comingSoon: "قريبًا",
    },
    notifications: {
      "Pipeline Complete": "اكتمل خط الأنابيب",
      "Asset processing pipeline completed successfully":
        "اكتمل خط معالجة الأصول بنجاح",
      "Storage Warning": "تحذير التخزين",
      "Storage capacity reaching 80%": "سعة التخزين تقترب من 80%",
      "Pipeline Failed": "فشل خط الأنابيب",
      "Video processing pipeline failed": "فشل خط معالجة الفيديو",
    },
    modal: {
      confirmDelete: "هل أنت متأكد أنك تريد حذف هذا العنصر؟",
      confirmAction: "هل أنت متأكد أنك تريد تنفيذ هذا الإجراء؟",
      error: "حدث خطأ",
      success: "اكتملت العملية بنجاح",
    },
    executions: {
      title: "تنفيذ خطوط الأنابيب",
      description: "راقب وأدر تنفيذ خطوط الأنابيب الخاصة بك",
      searchPlaceholder: "ابحث عن تنفيذ خطوط الأنابيب...",
      columns: {
        pipelineName: "اسم خط الأنابيب",
        status: "الحالة",
        startTime: "وقت البدء",
        endTime: "وقت الانتهاء",
        duration: "المدة",
        actions: "الإجراءات",
      },
      status: {
        succeeded: "ناجح",
        failed: "فشل",
        running: "قيد التشغيل",
        timedOut: "انتهى الوقت",
        aborted: "ألغيت",
      },
      actions: {
        retryFromCurrent: "أعد المحاولة من النقطة الحالية",
        retryFromStart: "أعد المحاولة من البداية",
        viewDetails: "عرض التفاصيل",
      },
      pagination: {
        page: "الصفحة {{page}} من {{total}}",
        showEntries: "أظهر {{count}}",
      },
    },
    s3Explorer: {
      filter: {
        label: "تصفية حسب الاسم",
      },
      error: {
        loading: "خطأ في تحميل كائنات S3: {{message}}",
      },
      file: {
        info: "الحجم: {{size}} • فئة التخزين: {{storageClass}} • تم التعديل: {{modified}}",
      },
      menu: {
        rename: "إعادة التسمية",
        delete: "حذف",
      },
    },
    assets: {
      title: "الأصول",
      connectedStorage: "التخزين المتصل",
    },
    metadata: {
      title: "قريبًا",
      description: "نعمل على تقديم قدرات إدارة البيانات الوصفية. ترقب!",
    },
    pipelines: {
      title: "خطوط الأنابيب",
      description: "قم بإدارة خطوط أنابيب الوسائط والبيانات الوصفية الخاصة بك",
      searchPlaceholder: "ابحث عن خطوط الأنابيب...",
      actions: {
        create: "إضافة خط أنابيب جديد",
        deploy: "نشر خط أنابيب الصور",
        addNew: "إضافة خط أنابيب جديد",
        viewAll: "عرض جميع خطوط الأنابيب",
      },
      search: "ابحث عن خطوط الأنابيب",
      deploy: "نشر خط أنابيب الصور",
      addNew: "إضافة خط أنابيب جديد",
      columns: {
        name: "الاسم",
        creationDate: "تاريخ الإنشاء",
        system: "النظام",
        type: "النوع",
        actions: "الإجراءات",
      },
      editor: {
        title: "محرر خط الأنابيب",
        save: "حفظ خط الأنابيب",
        validate: "التحقق من خط الأنابيب",
        sidebar: {
          title: "العقد",
          dragNodes: "اسحب العقد إلى اللوحة",
          loading: "جارٍ تحميل العقد...",
          error: "خطأ في تحميل العقد",
        },
        node: {
          configure: "تكوين {{type}}",
          delete: "حذف العقدة",
          edit: "تعديل العقدة",
        },
        edge: {
          title: "تحرير تسمية الاتصال",
          label: "تسمية الاتصال",
          delete: "حذف الاتصال",
        },
        modals: {
          error: {
            title: "خطأ",
            incompatibleNodes:
              "مخرجات العقدة السابقة غير متوافقة مع مدخلات العقدة الوجهة.",
            validation: "فشل التحقق من خط الأنابيب",
          },
          delete: {
            title: "حذف خط الأنابيب",
            message:
              "هل أنت متأكد أنك تريد حذف هذا الخط؟ لا يمكن التراجع عن هذا الإجراء.",
            confirm: "اكتب اسم خط الأنابيب لتأكيد الحذف:",
          },
        },
        controls: {
          undo: "تراجع",
          redo: "إعادة",
          zoomIn: "تكبير",
          zoomOut: "تصغير",
          fitView: "تعديل العرض",
          lockView: "قفل العرض",
        },
        notifications: {
          saved: "تم حفظ خط الأنابيب بنجاح",
          validated: "تم التحقق من خط الأنابيب بنجاح",
          error: {
            save: "فشل حفظ خط الأنابيب",
            validation: "فشل التحقق من خط الأنابيب",
            incompatibleNodes: "الاتصال بين العقد غير متوافق",
          },
        },
      },
    },
    integrations: {
      title: "التكاملات",
      description: "قم بإدارة تكاملاتك واتصالاتك",
      addIntegration: "إضافة تكامل",
      selectIntegration: "اختر التكامل",
      selectProvider: "اختر المزود",
      configureIntegration: "تكوين التكامل",
      form: {
        title: "إضافة تكامل",
        fields: {
          nodeId: {
            label: "التكامل",
            tooltip: "اختر مزود التكامل",
            errors: {
              required: "اختيار التكامل مطلوب",
            },
          },
          description: {
            label: "الوصف",
            tooltip: "قم بتوفير وصف لهذا التكامل",
            errors: {
              required: "الوصف مطلوب",
            },
          },
          environmentId: {
            label: "البيئة",
            tooltip: "اختر البيئة لهذا التكامل",
            errors: {
              required: "اختيار البيئة مطلوب",
            },
          },
          enabled: {
            label: "مُفعل",
            tooltip: "فعّل أو عطّل هذا التكامل",
            errors: {
              required: "التفعيل مطلوب",
            },
          },
          auth: {
            type: {
              label: "نوع المصادقة",
              tooltip: "اختر طريقة المصادقة",
              options: {
                awsIam: "AWS IAM",
                apiKey: "مفتاح API",
              },
              errors: {
                required: "نوع المصادقة مطلوب",
              },
            },
            credentials: {
              apiKey: {
                label: "مفتاح API",
                tooltip: "أدخل مفتاح API الخاص بك",
                errors: {
                  required: "مفتاح API مطلوب",
                },
              },
              iamRole: {
                label: "دور IAM",
                tooltip: "أدخل ARN لدور IAM",
                errors: {
                  required: "دور IAM مطلوب",
                },
              },
            },
          },
        },
        search: {
          placeholder: "ابحث عن التكاملات",
        },
        errors: {
          required: "هذا الحقل مطلوب",
          nodeId: {
            unrecognized_keys: "اختيار التكامل غير صالح",
          },
        },
      },
      columns: {
        nodeName: "اسم العقدة",
        environment: "البيئة",
        createdDate: "تاريخ الإنشاء",
        modifiedDate: "تاريخ التعديل",
        actions: "الإجراءات",
      },
      settings: {
        environments: {
          title: "البيئات",
        },
      },
    },
  },
};
