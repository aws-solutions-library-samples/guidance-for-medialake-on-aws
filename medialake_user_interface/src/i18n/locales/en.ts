export default {
    integrations: {
        selectProvider: 'Select Integration',
        selectIntegration: 'Select Integration',
        configureIntegration: 'Configure Integration',
        form: {
            title: 'Add Integration',
            fields: {
                nodeId: {
                    label: 'Integration',
                    tooltip: 'Select an integration provider',
                    errors: {
                        required: 'Integration selection is required'
                    }
                },
                description: {
                    label: 'Description',
                    tooltip: 'Provide a description for this integration',
                    errors: {
                        required: 'Description is required'
                    }
                },
                environmentId: {
                    label: 'Environment',
                    tooltip: 'Select the environment for this integration',
                    errors: {
                        required: 'Environment selection is required'
                    }
                },
                enabled: {
                    label: 'Enabled',
                    tooltip: 'Enable or disable this integration',
                    errors: {
                        required: 'Enabled is required'
                    }
                },
                auth: {
                    type: {
                        label: 'Authentication Type',
                        tooltip: 'Select the authentication method',
                        options: {
                            awsIam: 'AWS IAM',
                            apiKey: 'API Key'
                        },
                        errors: {
                            required: 'Authentication type is required'
                        }
                    },
                    credentials: {
                        apiKey: {
                            label: 'API Key',
                            tooltip: 'Enter your API key',
                            errors: {
                                required: 'API Key is required'
                            }
                        },
                        iamRole: {
                            label: 'IAM Role',
                            tooltip: 'Enter the IAM role ARN',
                            errors: {
                                required: 'IAM Role is required'
                            }
                        }
                    }
                }
            },
            errors: {
                required: 'This field is required',
                nodeId: {
                    unrecognized_keys: 'Invalid integration selection'
                }
            },
        },
    },
    common: {
        select: 'Select',
        back: 'Back',
        actions: {
            add: 'Add'
        }
    },
    translation: {
        common: {
            actions: {
                add: 'Add',
                edit: 'Edit',
                delete: 'Delete',
                activate: 'Activate',
                deactivate: 'Deactivate'
            },
            tableDensity: "Table Density",
            theme: "Theme",
            back: 'Back',
            loading: 'Loading...',
            error: 'Something went wrong',
            save: 'Save',
            cancel: 'Cancel',
            delete: 'Delete',
            edit: 'Edit',
            search: 'Search',
            profile: 'Profile',
            filterColumn: 'Filter',
            searchValue: 'Search',
            logout: 'Logout',
            language: 'Language',
            alerts: 'Alerts',
            warnings: 'Warnings',
            notifications: 'Notifications',
            searchPlaceholder: 'Search or use key:value...',
            close: 'Close',
            success: 'Success',
            refresh: 'Refresh',
            previous: 'Previous',
            next: 'Next',
            show: 'Show',
            all: 'All',
            status: 'Status',
            rename: 'Rename',
            root: 'Root',
            folder: 'Folder',
            loadMore: 'Load More',
            darkMode: 'Dark Mode',
            lightMode: 'Light Mode',
            filter: 'Filter',
            textFilter: 'Text Filter',
            selectFilter: 'Select Filter',
            clearFilter: 'Clear Filter',
            columns: 'Columns',
            noGroups: 'No Groups',
            create: 'Create'
        },
        users: {
            title: 'User Management',
            search: 'Search users',
            description: 'Manage system users and their access',
            form: {
                fields: {
                    given_name: {
                        label: 'First Name',
                        tooltip: 'Enter the user\'s first name',
                        errors: {
                            required: 'First name is required'
                        }
                    },
                    family_name: {
                        label: 'Last Name',
                        tooltip: 'Enter the user\'s last name',
                        errors: {
                            required: 'Last name is required'
                        }
                    },
                    email: {
                        label: 'Email',
                        tooltip: 'Enter the user\'s email address',
                        errors: {
                            required: 'Email is required',
                            invalid: 'Invalid email address'
                        },
                    email_verified: {
                        label: 'Email Verified',
                        tooltip: 'Indicate if the user\'s email has been verified',
                        errors: {
                            required: 'Email verification is required'
                        }
                    },
                    enabled: {
                        label: 'Enabled',
                        tooltip: 'Enable or disable the user',
                        errors: {
                            required: 'Enabled is required'
                        }
                    }
                }
            }
            },
            columns: {
                username: 'Username',
                firstName: 'First Name',
                lastName: 'Last Name',
                email: 'Email',
                status: 'Status',
                groups: 'Groups',
                created: 'Created',
                modified: 'Modified',
                actions: 'Actions',
            },
            actions: {
                addUser: 'Add User',
                edit: 'Edit User',
                delete: 'Delete User',
                activate: 'Activate User',
                deactivate: 'Deactivate User'
            },
            status: {
                active: 'Active',
                inactive: 'Inactive'
            },
            errors: {
                loadFailed: 'Failed to load users',
                saveFailed: 'Failed to save user',
                deleteFailed: 'Failed to delete user'
            }
        },
        navigation: {
            home: 'Home',
            collections: 'Collections',
            settings: 'Settings'
        },
        home: {
            welcome: 'Welcome to MediaLake',
            description: 'Manage and organize your media files efficiently',
            statistics: 'Statistics',
            collections: 'Collections',
            sharedCollections: 'Shared Collections',
            favorites: 'Favorites',
            smartFolders: 'Smart Folders',
            connectedStorage: 'Connected Storage'
        },
        notifications: {
            'Pipeline Complete': 'Pipeline Complete',
            'Asset processing pipeline completed successfully': 'Asset processing pipeline completed successfully',
            'Storage Warning': 'Storage Warning',
            'Storage capacity reaching 80%': 'Storage capacity reaching 80%',
            'Pipeline Failed': 'Pipeline Failed',
            'Video processing pipeline failed': 'Video processing pipeline failed'
        },
        modal: {
            confirmDelete: 'Are you sure you want to delete this item?',
            confirmAction: 'Are you sure you want to perform this action?',
            error: 'An error occurred',
            success: 'Operation completed successfully'
        },
        executions: {
            title: 'Pipeline Executions',
            searchPlaceholder: 'Search pipeline executions...',
            description: 'Monitor and manage your pipeline executions',
            columns: {
                pipelineName: 'Pipeline Name',
                status: 'Status',
                startTime: 'Start Time',
                duration: 'Duration',
                actions: 'Actions'
            },
            status: {
                succeeded: 'Succeeded',
                failed: 'Failed',
                running: 'Running',
                timedOut: 'Timed Out',
                aborted: 'Aborted'
            },
            actions: {
                retryFromCurrent: 'Retry from current position',
                retryFromStart: 'Retry from start',
                viewDetails: 'View Details'
            },
            pagination: {
                page: 'Page {{page}} of {{total}}',
                showEntries: 'Show {{count}}'
            }
        },
        sidebar: {
            menu: {
                home: 'Home',
                assets: 'Assets',
                pipelines: 'Pipelines',
                pipelineExecutions: 'Pipeline Executions',
                settings: 'Settings'
            },
            submenu: {
                system: 'System Settings',
                connectors: 'Connectors',
                userManagement: 'User Management',
                roles: 'Roles',
                integrations: 'Integrations',
                environments: 'Environments'
            }
        },
        s3Explorer: {
            filter: {
                label: 'Filter by name'
            },
            error: {
                loading: 'Error loading S3 objects: {{message}}'
            },
            file: {
                info: 'Size: {{size}} • Storage Class: {{storageClass}} • Modified: {{modified}}'
            },
            menu: {
                rename: 'Rename',
                delete: 'Delete'
            }
        },
        assets: {
            title: 'Assets',
            connectedStorage: 'Connected Storage'
        },
        metadata: {
            title: 'Coming Soon',
            description: "We're working to bring you metadata management capabilities. Stay tuned!"
        },
        pipelines: {
            title: 'Pipelines',
            searchPlaceholder: 'Search pipelines...',
            actions: {
                create: 'Add New Pipeline',
                deploy: 'Deploy Image Pipeline',
                addNew: 'Add New Pipeline',
            },
            description: 'Manage your media and metadata pipelines',
            search: 'Search pipelines',
            deploy: 'Deploy Image Pipeline',
            addNew: 'Add New Pipeline',
            columns: {
                name: 'Name',
                creationDate: 'Creation Date',
                system: 'System',
                type: 'Type',
                actions: 'Actions'
            },
            editor: {
                title: 'Pipeline Editor',
                save: 'Save Pipeline',
                validate: 'Validate Pipeline',
                sidebar: {
                    title: 'Nodes',
                    dragNodes: 'Drag nodes to the canvas',
                    loading: 'Loading nodes...',
                    error: 'Error loading nodes'
                },
                node: {
                    configure: 'Configure {{type}}',
                    delete: 'Delete Node',
                    edit: 'Edit Node'
                },
                edge: {
                    title: 'Edit Edge Label',
                    label: 'Edge Label',
                    delete: 'Delete Connection'
                },
                modals: {
                    error: {
                        title: 'Error',
                        incompatibleNodes: 'The output of the previous node is not compatible with the input of the destination node.',
                        validation: 'Pipeline validation failed'
                    },
                    delete: {
                        title: 'Delete Pipeline',
                        message: 'Are you sure you want to delete this pipeline? This action cannot be undone.',
                        confirm: 'Type the pipeline name to confirm deletion:'
                    }
                },
                controls: {
                    undo: 'Undo',
                    redo: 'Redo',
                    zoomIn: 'Zoom In',
                    zoomOut: 'Zoom Out',
                    fitView: 'Fit View',
                    lockView: 'Lock View'
                },
                notifications: {
                    saved: 'Pipeline saved successfully',
                    validated: 'Pipeline validation successful',
                    error: {
                        save: 'Failed to save pipeline',
                        validation: 'Pipeline validation failed',
                        incompatibleNodes: 'Incompatible node connection'
                    }
                }
            }
        },
        integrations: {
            title: 'Integrations',
            description: 'Manage your integrations and connections',
            addIntegration: 'Add Integration',
            selectIntegration: 'Select Integration',
            configureIntegration: 'Configure Integration',
            columns: {
                nodeName: 'Node Name',
                environment: 'Environment',
                createdDate: 'Created Date',
                modifiedDate: 'Modified Date',
                actions: 'Actions'
            },
            form: {
                title: 'Add Integration',
                fields: {
                    enabled: {
                        label: 'Enabled',
                        tooltip: 'Enable or disable this integration',
                        errors: {
                            required: 'Enabled is required'
                        }
                    },
                    nodeId: {
                        label: 'Integration',
                        tooltip: 'Select an integration provider',
                        errors: {
                            required: 'Integration selection is required'
                        }
                    },
                    description: {
                        label: 'Description',
                        tooltip: 'Provide a description for this integration',
                        errors: {
                            required: 'Description is required'
                        }
                    },
                    environmentId: {
                        label: 'Environment',
                        tooltip: 'Select the environment for this integration',
                        errors: {
                            required: 'Environment selection is required'
                        }
                    },
                    auth: {
                        type: {
                            label: 'Authentication Type',
                            tooltip: 'Select the authentication method',
                            options: {
                                awsIam: 'AWS IAM',
                                apiKey: 'API Key'
                            },
                            errors: {
                                required: 'Authentication type is required'
                            }
                        },
                        credentials: {
                            apiKey: {
                                label: 'API Key',
                                tooltip: 'Enter your API key',
                                errors: {
                                    required: 'API Key is required'
                                }
                            },
                            iamRole: {
                                label: 'IAM Role',
                                tooltip: 'Enter the IAM role ARN',
                                errors: {
                                    required: 'IAM Role is required'
                                }
                            }
                        }
                    }
                },
                search: {
                    placeholder: 'Search integrations...'
                },
                errors: {
                    required: 'This field is required',
                    nodeId: {
                        unrecognized_keys: 'Invalid integration selection'
                    }
                }
            },
            actions: {
                edit: 'Edit Integration',
                delete: 'Delete Integration'
            },
            search: 'Search integrations...',
            selectProvider: 'Select Provider',
            status: {
                creating: 'Creating integration...',
                created: 'Integration Created',
                createFailed: 'Integration Creation Failed',
                deleting: 'Deleting integration...',
                deleted: 'Integration Deleted',
                deleteFailed: 'Integration Deletion Failed'
            }
        },
        settings: {
            environments: {
                title: 'Environments',
                description: 'Manage system environments and their configurations',
                search: 'Search environments',
                searchPlaceholder: 'Search environments...',
                addButton: 'Add Environment',
                createTitle: 'Create Environment',
                editTitle: 'Edit Environment',
                deleteSuccess: 'Environment deleted successfully',
                deleteError: 'Failed to delete environment',
                createSuccess: 'Environment created successfully',
                updateSuccess: 'Environment updated successfully',
                submitError: 'Failed to save environment',
                columns: {
                    name: 'Name',
                    region: 'Region',
                    status: 'Status',
                    team: 'Team',
                    costCenter: 'Cost Center',
                    createdAt: 'Created At',
                    updatedAt: 'Updated At',
                    actions: 'Actions'
                },
                status: {
                    active: 'Active',
                    disabled: 'Disabled'
                },
                actions: {
                    edit: 'Edit Environment',
                    delete: 'Delete Environment'
                },
                form: {
                    name: 'Environment Name',
                    region: 'Region',
                    costCenter: 'Cost Center',
                    team: 'Team',
                    status: {
                        name: "Status",
                        active: "Active",
                        disabled: "Disabled"
                    }
                }
            },
            systemSettings: {
                title: 'System Settings',
                tabs: {
                    search: 'Search',
                    notifications: 'Notifications',
                    security: 'Security',
                    performance: 'Performance'
                },
                search: {
                    title: 'Search Configuration',
                    description: 'Configure the search provider for enhanced search capabilities across your media assets.',
                    provider: 'Search Provider:',
                    configureProvider: 'Configure Provider',
                    editProvider: 'Edit Provider',
                    resetProvider: 'Reset Provider',
                    providerDetails: 'Provider Details',
                    providerName: 'Provider Name',
                    providerType: 'Provider Type',
                    apiKey: 'API Key',
                    endpoint: 'Endpoint URL',
                    enabled: 'Search Enabled',
                    noProvider: 'No search provider configured.',
                    configurePrompt: 'Configure Twelve Labs to enable search capabilities.',
                    errorLoading: 'Error loading search provider configuration'
                },
                notifications: {
                    title: 'Notifications Settings',
                    comingSoon: 'Notification settings coming soon.'
                },
                security: {
                    title: 'Security Settings',
                    comingSoon: 'Security settings coming soon.'
                },
                performance: {
                    title: 'Performance Settings',
                    comingSoon: 'Performance settings coming soon.'
                }
            }
        }
    }
}
