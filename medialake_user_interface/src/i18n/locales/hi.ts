export default {
  languages: {
    english: "अंग्रे़ी",
    german: "जर्मन",
    portuguese: "पुर्तगाली",
    french: "फ्रेंच",
    chinese: "चीनी",
    hindi: "हिन्दी",
    arabic: "अरबी",
    hebrew: "हिब्रू",
    japanese: "जापानी",
    korean: "कोरियाई",
    spanish: "स्पेनिश",
  },
  assetsPage: {
    title: "संपत्तियाँ",
    connectors: "कनेक्टर",
    selectConnector: "कनेक्टर चुनें",
  },
  assetExplorer: {
    noConnectorSelected: "संपत्तियाँ देखने के लिए कनेक्टर चुनें",
    noAssetsFound: "इस कनेक्टर के लिए कोई संपत्ति नहीं मिली",
    noIndexedAssets:
      'बकेट "{{bucketName}}" के साथ इस कनेक्टर के लिए कोई इंडेक्स की गई संपत्ति नहीं मिली।',
    loadingAssets: "संपत्तियाँ लोड हो रही हैं...",
    menu: {
      rename: "नाम बदलें",
      share: "साझा करें",
      download: "डाउनलोड करें",
    },
    deleteDialog: {
      title: "हटाने की पुष्टि करें",
      description:
        "क्या आप वाकई इस संपत्ति को हटाना चाहते हैं? यह कार्रवाई पूर्ववत नहीं की जा सकती।",
      cancel: "रद्द करें",
      confirm: "हटाएँ",
    },
  },
  sidebar: {
    menu: {
      home: "होम",
      assets: "संपत्तियाँ",
      pipelines: "पाइपलाइन्स",
      pipelineExecutions: "पाइपलाइन निष्पादन",
      settings: "सेटिंग्स",
    },
    submenu: {
      system: "सिस्टम सेटिंग्स",
      connectors: "कनेक्टर",
      userManagement: "उपयोगकर्ता प्रबंधन",
      roles: "भूमिकाएँ",
      integrations: "एकीकरण",
      environments: "पर्यावरण",
    },
  },
  profile: {
    title: "प्रोफ़ाइल",
    description: "अपने खाते की सेटिंग्स और प्राथमिकताएँ प्रबंधित करें",
    changePhoto: "फ़ोटो बदलें",
    jobTitle: "पद",
    organization: "संगठन",
    preferences: "प्राथमिकताएँ",
    timezone: "समय क्षेत्र",
    emailNotifications: "ईमेल सूचनाएँ",
    pushNotifications: "पुश सूचनाएँ",
    changePassword: "पासवर्ड बदलें",
    twoFactorAuth: "दो-कारक प्रमाणीकरण",
    appearance: "दिखावट",
  },
  app: {
    loading: "लोड हो रहा है...",
    errors: {
      loadingConfig: "AWS विन्यास लोड करते समय त्रुटि:",
      loadingUserAttributes: "उपयोगकर्ता गुण लोड करते समय त्रुटि:",
      signingOut: "साइन आउट करते समय त्रुटि:",
    },
    navigation: {
      preventedDuplicate: "डुप्लिकेट नेविगेशन रोका गया",
      navigating: "नेविगेट कर रहे हैं",
    },
    branding: {
      name: "Media Lake",
    },
  },
  search: {
    semantic: "सार्थक खोज",
    filters: {
      dateRange: "तारीख सीमा",
      contentType: "सामग्री का प्रकार",
      storageLocation: "स्टोरेज स्थान",
      comingSoon: "अधिक फ़िल्टर जल्द ही आ रहे हैं...",
    },
  },
  admin: {
    metrics: {
      storageUsage: "स्टोरेज उपयोग",
      apiUsage: "API उपयोग",
      activeUsers: "सक्रिय उपयोगकर्ता",
      systemLoad: "सिस्टम लोड",
    },
    errors: {
      userDeletionNotImplemented: "उपयोगकर्ता हटाना अभी लागू नहीं किया गया है।",
      userCreationNotImplemented:
        "उपयोगकर्ता निर्माण अभी लागू नहीं किया गया है।",
      userEditingNotImplemented: "उपयोगकर्ता संपादन अभी लागू नहीं किया गया है।",
      analyticsExportNotImplemented:
        "एनालिटिक्स निर्यात अभी लागू नहीं किया गया है।",
      systemResetNotImplemented: "सिस्टम रीसेट अभी लागू नहीं किया गया है।",
    },
    columns: {
      lastActive: "अंतिम सक्रियता",
    },
    buttons: {
      exportAnalytics: "एनालिटिक्स निर्यात करें",
      resetSystem: "सिस्टम रीसेट करें",
    },
  },
  integrations: {
    title: "एकीकरण",
    selectProvider: "एकीकरण का चयन करें",
    selectIntegration: "एकीकरण चुनें",
    configureIntegration: "एकीकरण कॉन्फ़िगर करें",
    description: "अपने एकीकरण और कनेक्शनों को प्रबंधित करें",
    addIntegration: "एकीकरण जोड़ें",
    form: {
      search: {
        placeholder: "एकीकरण खोजें",
      },
      title: "एकीकरण जोड़ें",
      fields: {
        nodeId: {
          label: "एकीकरण",
          tooltip: "एक एकीकरण प्रदाता चुनें",
          errors: {
            required: "एकीकरण का चयन अनिवार्य है",
          },
        },
        description: {
          label: "विवरण",
          tooltip: "इस एकीकरण के लिए विवरण प्रदान करें",
          helper: "इस एकीकरण का संक्षिप्त विवरण",
          errors: {
            required: "विवरण आवश्यक है",
          },
        },
        environmentId: {
          label: "पर्यावरण",
          tooltip: "इस एकीकरण के लिए पर्यावरण चुनें",
          errors: {
            required: "पर्यावरण का चयन अनिवार्य है",
          },
        },
        enabled: {
          label: "सक्रिय",
          tooltip: "इस एकीकरण को सक्रिय या निष्क्रिय करें",
          errors: {
            required: "सक्रिय अनिवार्य है",
          },
        },
        auth: {
          type: {
            label: "प्रमाणीकरण प्रकार",
            tooltip: "प्रमाणीकरण विधि चुनें",
            options: {
              awsIam: "AWS IAM",
              apiKey: "API कुंजी",
            },
            errors: {
              required: "प्रमाणीकरण प्रकार अनिवार्य है",
            },
          },
          credentials: {
            apiKey: {
              label: "API कुंजी",
              tooltip: "अपनी API कुंजी दर्ज करें",
              helper: "सेवा के साथ प्रमाणीकरण के लिए API कुंजी",
              errors: {
                required: "API कुंजी आवश्यक है",
              },
            },
            iamRole: {
              label: "IAM भूमिका",
              tooltip: "IAM भूमिका का ARN दर्ज करें",
              errors: {
                required: "IAM भूमिका आवश्यक है",
              },
            },
          },
        },
      },
      errors: {
        required: "यह फ़ील्ड अनिवार्य है",
        nodeId: {
          unrecognized_keys: "अमान्य एकीकरण चयन",
        },
      },
    },
  },
  pipelines: {
    title: "पाइपलाइन्स",
    description: "अपने मीडिया और मेटाडाटा पाइपलाइन्स का प्रबंधन करें",
    searchPlaceholder: "पाइपलाइन्स खोजें...",
    actions: {
      create: "नया पाइपलाइन जोड़ें",
      import: "पाइपलाइन आयात करें",
    },
  },
  executions: {
    title: "पाइपलाइन निष्पादन",
    description: "अपने पाइपलाइन निष्पादनों की निगरानी और प्रबंधन करें",
    searchPlaceholder: "पाइपलाइन निष्पादन खोजें...",
    columns: {
      pipelineName: "पाइपलाइन का नाम",
      status: "स्थिति",
      startTime: "शुरू होने का समय",
      endTime: "समाप्ति समय",
      duration: "अवधि",
      actions: "क्रियाएँ",
    },
    actions: {
      retryFromCurrent: "वर्तमान स्थिति से पुनः प्रयास करें",
      retryFromStart: "शुरू से पुनः प्रयास करें",
      viewDetails: "विवरण देखें",
    },
  },
  users: {
    title: "उपयोगकर्ता प्रबंधन",
    description: "सिस्टम उपयोगकर्ताओं और उनके एक्सेस का प्रबंधन करें",
    actions: {
      addUser: "उपयोगकर्ता जोड़ें",
    },
    form: {
      title: {
        add: "उपयोगकर्ता जोड़ें",
      },
      fields: {
        given_name: {
          label: "पहला नाम",
          tooltip: "उपयोगकर्ता का पहला नाम दर्ज करें",
          helper: "",
        },
        family_name: {
          label: "अंतिम नाम",
          tooltip: "उपयोगकर्ता का अंतिम नाम दर्ज करें",
          helper: "",
        },
        email: {
          label: "ईमेल",
          tooltip: "उपयोगकर्ता का ईमेल पता दर्ज करें",
          helper: "",
        },
        roles: {
          label: "भूमिकाएँ",
          tooltip: "उपयोगकर्ता के लिए भूमिकाएँ चुनें",
          options: {
            Admin: "प्रशासक",
            Editor: "संपादक",
            Viewer: "दर्शक",
          },
        },
        email_verified: {
          label: "ईमेल सत्यापित",
          tooltip: "यह संकेत करें कि उपयोगकर्ता का ईमेल सत्यापित है",
        },
        enabled: {
          label: "सक्रिय",
          tooltip: "उपयोगकर्ता को सक्रिय या निष्क्रिय करें",
        },
      },
    },
    roles: {
      admin: "प्रशासक",
      editor: "संपादक",
      viewer: "दर्शक",
    },
  },
  roles: {
    title: "भूमिका प्रबंधन",
    description: "सिस्टम भूमिकाओं और उनके अनुमतियों का प्रबंधन करें",
    actions: {
      addRole: "भूमिका जोड़ें",
    },
  },
  settings: {
    environments: {
      title: "पर्यावरण",
      description: "सिस्टम पर्यावरण और उनके विन्यास का प्रबंधन करें",
      addButton: "पर्यावरण जोड़ें",
      searchPlaceholder: "पर्यावरण खोजें",
      createTitle: "पर्यावरण बनाएँ",
      form: {
        name: "पर्यावरण का नाम",
        region: "क्षेत्र",
        status: {
          name: "स्थिति",
          active: "सक्रिय",
          disabled: "निष्क्रिय",
        },
        costCenter: "लागत केंद्र",
        team: "टीम",
      },
    },
    systemSettings: {
      title: "सिस्टम सेटिंग्स",
      tabs: {
        search: "खोज",
        notifications: "सूचनाएँ",
        security: "सुरक्षा",
        performance: "प्रदर्शन",
      },
      search: {
        title: "खोज विन्यास",
        description:
          "अपने मीडिया संपत्तियों में उन्नत खोज क्षमताओं के लिए खोज प्रदाता को कॉन्फ़िगर करें।",
        provider: "खोज प्रदाता:",
        configureProvider: "खोज प्रदाता कॉन्फ़िगर करें",
        editProvider: "प्रदाता संपादित करें",
        resetProvider: "प्रदाता रीसेट करें",
        providerDetails: "प्रदाता विवरण",
        providerName: "प्रदाता का नाम",
        apiKey: "API कुंजी",
        endpoint: "एंडपॉइंट URL (वैकल्पिक)",
        enabled: "खोज सक्षम",
        noProvider: "कोई खोज प्रदाता कॉन्फ़िगर नहीं है।",
        configurePrompt:
          "खोज क्षमताओं को सक्षम करने के लिए Twelve Labs कॉन्फ़िगर करें।",
      },
      notifications: {
        title: "सूचना सेटिंग्स",
        comingSoon: "जल्द ही सूचनाओं की सेटिंग्स उपलब्ध होंगी।",
      },
      security: {
        title: "सुरक्षा सेटिंग्स",
        comingSoon: "जल्द ही सुरक्षा सेटिंग्स उपलब्ध होंगी।",
      },
      performance: {
        title: "प्रदर्शन सेटिंग्स",
        comingSoon: "जल्द ही प्रदर्शन सेटिंग्स उपलब्ध होंगी।",
      },
    },
    groups: {
      actions: {
        addGroup: "समूह जोड़ें",
        editGroup: "समूह संपादित करें",
        deleteGroup: "समूह हटाएँ",
        createGroup: "समूह बनाएँ",
        manageGroups: "समूहों का प्रबंधन करें",
      },
    },
    permissionSets: {
      noAssignments: "कोई अनुमति सेट नहीं",
      actions: {
        addPermissionSet: "अनुमति सेट जोड़ें",
        editPermissionSet: "अनुमति सेट संपादित करें",
        deletePermissionSet: "अनुमति सेट हटाएँ",
      },
    },
  },
  common: {
    select: "चुनें",
    back: "वापस",
    search: "खोजें",
    profile: "प्रोफ़ाइल",
    logout: "लॉग आउट",
    theme: "थीम",
    close: "बंद करें",
    refresh: "रिफ्रेश करें",
    cancel: "रद्द करें",
    save: "सहेजें",
    loading: "लोड हो रहा है...",
    loadMore: "और लोड करें",
    tableDensity: "टेबल घनत्व",
    moreInfo: "अधिक जानकारी",
    error: "त्रुटि",
    language: "भाषा",
    delete: "हटाएँ",
    create: "बनाएँ",
    actions: {
      add: "जोड़ें",
    },
    columns: {
      username: "उपयोगकर्ता नाम",
      firstName: "पहला नाम",
      lastName: "अंतिम नाम",
      email: "ईमेल",
      status: "स्थिति",
      groups: "समूह",
      created: "निर्मित",
      modified: "संशोधित",
      actions: "क्रियाएँ",
    },
    status: {
      active: "सक्रिय",
      inactive: "निष्क्रिय",
    },
  },
  translation: {
    common: {
      actions: {
        add: "जोड़ें",
        edit: "संपादित करें",
        delete: "हटाएँ",
        activate: "सक्रिय करें",
        deactivate: "निष्क्रिय करें",
        create: "बनाएँ",
      },
      tableDensity: "टेबल घनत्व",
      theme: "थीम",
      back: "वापस",
      loading: "लोड हो रहा है...",
      error: "कुछ गलत हो गया",
      save: "सहेजें",
      cancel: "रद्द करें",
      delete: "हटाएँ",
      edit: "संपादित करें",
      search: "खोजें",
      profile: "प्रोफ़ाइल",
      filterColumn: "फ़िल्टर",
      searchValue: "खोजें",
      logout: "लॉग आउट",
      language: "भाषा",
      alerts: "अलर्ट",
      warnings: "चेतावनी",
      notifications: "सूचनाएँ",
      searchPlaceholder: "खोजें या key:value का उपयोग करें...",
      close: "बंद करें",
      success: "सफलता",
      refresh: "रिफ्रेश करें",
      previous: "पिछला",
      next: "अगला",
      show: "दिखाएँ",
      all: "सभी",
      status: {
        active: "सक्रिय",
        inactive: "निष्क्रिय",
      },
      rename: "नाम बदलें",
      root: "मूल",
      folder: "फ़ोल्डर",
      loadMore: "और लोड करें",
      darkMode: "डार्क मोड",
      lightMode: "लाइट मोड",
      filter: "फ़िल्टर",
      textFilter: "पाठ फ़िल्टर",
      selectFilter: "चुनें फ़िल्टर",
      clearFilter: "फ़िल्टर साफ़ करें",
      columns: {
        username: "उपयोगकर्ता नाम",
        firstName: "पहला नाम",
        lastName: "अंतिम नाम",
        email: "ईमेल",
        status: "स्थिति",
        groups: "समूह",
        created: "निर्मित",
        modified: "संशोधित",
        actions: "क्रियाएँ",
      },
      noGroups: "कोई समूह नहीं",
      select: "चुनें",
      moreInfo: "अधिक जानकारी",
    },
    users: {
      title: "उपयोगकर्ता प्रबंधन",
      search: "उपयोगकर्ताओं की खोज करें",
      description: "सिस्टम उपयोगकर्ताओं और उनके एक्सेस का प्रबंधन करें",
      form: {
        fields: {
          given_name: {
            label: "पहला नाम",
            tooltip: "उपयोगकर्ता का पहला नाम दर्ज करें",
            errors: {
              required: "पहला नाम आवश्यक है",
            },
          },
          family_name: {
            label: "अंतिम नाम",
            tooltip: "उपयोगकर्ता का अंतिम नाम दर्ज करें",
            errors: {
              required: "अंतिम नाम आवश्यक है",
            },
          },
          email: {
            label: "ईमेल",
            tooltip: "उपयोगकर्ता का ईमेल पता दर्ज करें",
            errors: {
              required: "ईमेल आवश्यक है",
              invalid: "अमान्य ईमेल पता",
            },
          },
          enabled: {
            label: "सक्रिय",
            tooltip: "उपयोगकर्ता को सक्रिय या निष्क्रिय करें",
            errors: {
              required: "सक्रिय होना आवश्यक है",
            },
          },
          roles: {
            label: "भूमिकाएँ",
            tooltip: "उपयोगकर्ता के लिए भूमिकाएँ चुनें",
            errors: {
              required: "भूमिकाएँ आवश्यक हैं",
            },
          },
          email_verified: {
            label: "ईमेल सत्यापित",
            tooltip: "यह संकेत करें कि उपयोगकर्ता का ईमेल सत्यापित है",
            errors: {
              required: "ईमेल सत्यापन आवश्यक है",
            },
          },
        },
      },
    },
    roles: {
      title: "भूमिका प्रबंधन",
      description: "सिस्टम भूमिकाओं और उनके अनुमतियों का प्रबंधन करें",
      admin: "प्रशासक",
      editor: "संपादक",
      viewer: "दर्शक",
      actions: {
        addRole: "भूमिका जोड़ें",
      },
    },
    columns: {
      username: "उपयोगकर्ता नाम",
      firstName: "पहला नाम",
      lastName: "अंतिम नाम",
      email: "ईमेल",
      status: "स्थिति",
      groups: "समूह",
      created: "निर्मित",
      modified: "संशोधित",
      actions: "क्रियाएँ",
    },
    actions: {
      addUser: "उपयोगकर्ता जोड़ें",
      edit: "उपयोगकर्ता संपादित करें",
      delete: "उपयोगकर्ता हटाएँ",
      activate: "उपयोगकर्ता सक्रिय करें",
      deactivate: "उपयोगकर्ता निष्क्रिय करें",
    },
    status: {
      active: "सक्रिय",
      inactive: "निष्क्रिय",
    },
    errors: {
      loadFailed: "उपयोगकर्ता लोड करने में विफल",
      saveFailed: "उपयोगकर्ता सहेजने में विफल",
      deleteFailed: "उपयोगकर्ता हटाने में विफल",
    },
    navigation: {
      home: "होम",
      collections: "कलेक्शन",
      settings: "सेटिंग्स",
    },
    home: {
      welcome: "Media Lake में आपका स्वागत है",
      description: "आपके मीडिया, मेटाडेटा और वर्कफ़्लो के लिए मार्गदर्शन।",
      statistics: "सांख्यिकी",
      collections: "कलेक्शन",
      sharedCollections: "साझा कलेक्शन",
      favorites: "पसंदीदा",
      smartFolders: "स्मार्ट फ़ोल्डर",
      connectedStorage: "कनेक्टेड स्टोरेज",
      sharing: "शेयरिंग",
      comingSoon: "जल्द आ रहा है",
    },
    notifications: {
      "Pipeline Complete": "पाइपलाइन पूर्ण",
      "Asset processing pipeline completed successfully":
        "संपत्ति प्रसंस्करण पाइपलाइन सफलतापूर्वक पूर्ण हुई",
      "Storage Warning": "स्टोरेज चेतावनी",
      "Storage capacity reaching 80%": "स्टोरेज क्षमता 80% तक पहुँच रही है",
      "Pipeline Failed": "पाइपलाइन विफल",
      "Video processing pipeline failed": "वीडियो प्रसंस्करण पाइपलाइन विफल हुई",
    },
    modal: {
      confirmDelete: "क्या आप वाकई इस आइटम को हटाना चाहते हैं?",
      confirmAction: "क्या आप वाकई यह कार्रवाई करना चाहते हैं?",
      error: "एक त्रुटि हुई",
      success: "संचालन सफलतापूर्वक पूरा हुआ",
    },
    executions: {
      title: "पाइपलाइन निष्पादन",
      description: "अपने पाइपलाइन निष्पादनों की निगरानी और प्रबंधन करें",
      searchPlaceholder: "पाइपलाइन निष्पादन खोजें...",
      columns: {
        pipelineName: "पाइपलाइन का नाम",
        status: "स्थिति",
        startTime: "शुरू होने का समय",
        endTime: "समाप्ति समय",
        duration: "अवधि",
        actions: "क्रियाएँ",
      },
      status: {
        succeeded: "सफल",
        failed: "विफल",
        running: "चल रहा",
        timedOut: "समय समाप्त",
        aborted: "रद्द किया गया",
      },
      actions: {
        retryFromCurrent: "वर्तमान स्थिति से पुनः प्रयास करें",
        retryFromStart: "शुरू से पुनः प्रयास करें",
        viewDetails: "विवरण देखें",
      },
      pagination: {
        page: "पृष्ठ {{page}} में से {{total}}",
        showEntries: "{{count}} दिखाएँ",
      },
    },
    s3Explorer: {
      filter: {
        label: "नाम से फ़िल्टर करें",
      },
      error: {
        loading: "S3 वस्तुओं को लोड करते समय त्रुटि: {{message}}",
      },
      file: {
        info: "आकार: {{size}} • स्टोरेज वर्ग: {{storageClass}} • संशोधित: {{modified}}",
      },
      menu: {
        rename: "नाम बदलें",
        delete: "हटाएँ",
      },
    },
    assets: {
      title: "संपत्तियाँ",
      connectedStorage: "कनेक्टेड स्टोरेज",
    },
    metadata: {
      title: "जल्द ही आ रहा है",
      description:
        "हम आपके लिए मेटाडाटा प्रबंधन क्षमताएँ लाने पर काम कर रहे हैं। जुड़े रहें!",
    },
    pipelines: {
      title: "पाइपलाइन्स",
      description: "अपने मीडिया और मेटाडाटा पाइपलाइन्स का प्रबंधन करें",
      searchPlaceholder: "पाइपलाइन्स खोजें...",
      actions: {
        create: "नया पाइपलाइन जोड़ें",
        deploy: "इमेज पाइपलाइन डिप्लॉय करें",
        addNew: "नया पाइपलाइन जोड़ें",
        viewAll: "सभी पाइपलाइन्स देखें",
      },
      search: "पाइपलाइन्स खोजें",
      deploy: "इमेज पाइपलाइन डिप्लॉय करें",
      addNew: "नया पाइपलाइन जोड़ें",
      columns: {
        name: "नाम",
        creationDate: "निर्माण तिथि",
        system: "सिस्टम",
        type: "प्रकार",
        actions: "क्रियाएँ",
      },
      editor: {
        title: "पाइपलाइन संपादक",
        save: "पाइपलाइन सहेजें",
        validate: "पाइपलाइन सत्यापित करें",
        sidebar: {
          title: "नोड्स",
          dragNodes: "नोड्स को कैनवास पर खींचें",
          loading: "नोड्स लोड हो रहे हैं...",
          error: "नोड्स लोड करने में त्रुटि",
        },
        node: {
          configure: "{{type}} को कॉन्फ़िगर करें",
          delete: "नोड हटाएँ",
          edit: "नोड संपादित करें",
        },
        edge: {
          title: "एज लेबल संपादित करें",
          label: "एज लेबल",
          delete: "कनेक्शन हटाएँ",
        },
        modals: {
          error: {
            title: "त्रुटि",
            incompatibleNodes:
              "पिछले नोड का आउटपुट लक्ष्य नोड के इनपुट के अनुकूल नहीं है।",
            validation: "पाइपलाइन सत्यापन विफल",
          },
          delete: {
            title: "पाइपलाइन हटाएँ",
            message:
              "क्या आप वाकई इस पाइपलाइन को हटाना चाहते हैं? यह कार्रवाई पूर्ववत नहीं की जा सकती।",
            confirm: "हटाने की पुष्टि के लिए पाइपलाइन का नाम टाइप करें:",
          },
        },
        controls: {
          undo: "पूर्ववत करें",
          redo: "पुनः करें",
          zoomIn: "ज़ूम इन",
          zoomOut: "ज़ूम आउट",
          fitView: "दृश्य के अनुसार फिट करें",
          lockView: "दृश्य लॉक करें",
        },
        notifications: {
          saved: "पाइपलाइन सफलतापूर्वक सहेजा गया",
          validated: "पाइपलाइन सत्यापन सफल रहा",
          error: {
            save: "पाइपलाइन सहेजने में विफल",
            validation: "पाइपलाइन सत्यापन विफल",
            incompatibleNodes: "नोड कनेक्शन असंगत",
          },
        },
      },
    },
    integrations: {
      title: "एकीकरण",
      description: "अपने एकीकरण और कनेक्शनों का प्रबंधन करें",
      addIntegration: "एकीकरण जोड़ें",
      selectIntegration: "एकीकरण चुनें",
      selectProvider: "प्रदाता चुनें",
      configureIntegration: "एकीकरण कॉन्फ़िगर करें",
      form: {
        title: "एकीकरण जोड़ें",
        fields: {
          nodeId: {
            label: "एकीकरण",
            tooltip: "एक एकीकरण प्रदाता चुनें",
            errors: {
              required: "एकीकरण का चयन अनिवार्य है",
            },
          },
          description: {
            label: "विवरण",
            tooltip: "इस एकीकरण के लिए विवरण प्रदान करें",
            errors: {
              required: "विवरण आवश्यक है",
            },
          },
          environmentId: {
            label: "पर्यावरण",
            tooltip: "इस एकीकरण के लिए पर्यावरण चुनें",
            errors: {
              required: "पर्यावरण का चयन अनिवार्य है",
            },
          },
          enabled: {
            label: "सक्रिय",
            tooltip: "इस एकीकरण को सक्रिय या निष्क्रिय करें",
            errors: {
              required: "सक्रिय अनिवार्य है",
            },
          },
          auth: {
            type: {
              label: "प्रमाणीकरण प्रकार",
              tooltip: "प्रमाणीकरण विधि चुनें",
              options: {
                awsIam: "AWS IAM",
                apiKey: "API कुंजी",
              },
              errors: {
                required: "प्रमाणीकरण प्रकार अनिवार्य है",
              },
            },
            credentials: {
              apiKey: {
                label: "API कुंजी",
                tooltip: "अपनी API कुंजी दर्ज करें",
                errors: {
                  required: "API कुंजी आवश्यक है",
                },
              },
              iamRole: {
                label: "IAM भूमिका",
                tooltip: "IAM भूमिका का ARN दर्ज करें",
                errors: {
                  required: "IAM भूमिका आवश्यक है",
                },
              },
            },
          },
        },
        search: {
          placeholder: "एकीकरण खोजें",
        },
        errors: {
          required: "यह फ़ील्ड अनिवार्य है",
          nodeId: {
            unrecognized_keys: "अमान्य एकीकरण चयन",
          },
        },
      },
      columns: {
        nodeName: "नोड का नाम",
        environment: "पर्यावरण",
        createdDate: "निर्माण तिथि",
        modifiedDate: "संशोधित तिथि",
        actions: "क्रियाएँ",
      },
      settings: {
        environments: {
          title: "पर्यावरण",
        },
      },
    },
    groups: {
      actions: {
        addGroup: "समूह जोड़ें",
        editGroup: "समूह संपादित करें",
        deleteGroup: "समूह हटाएँ",
        createGroup: "समूह बनाएँ",
        manageGroups: "समूहों का प्रबंधन करें",
      },
    },
    permissionSets: {
      noAssignments: "कोई अनुमति सेट नहीं",
      actions: {
        addPermissionSet: "अनुमति सेट जोड़ें",
        editPermissionSet: "अनुमति सेट संपादित करें",
        deletePermissionSet: "अनुमति सेट हटाएँ",
      },
    },
  },
};
