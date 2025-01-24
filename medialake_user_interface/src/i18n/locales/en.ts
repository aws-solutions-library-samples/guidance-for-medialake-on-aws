export default {
    translation: {
        common: {
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
            actions: 'Actions',
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
                metadata: 'Metadata',
                pipelines: 'Pipelines',
                pipelineExecutions: 'Pipeline Executions',
                reviewQueue: 'Review Queue',
                tags: 'Tags',
                settings: 'Settings'
            },
            submenu: {
                integrations: 'Integrations',
                connectors: 'Connectors',
                userManagement: 'User Management',
                roles: 'Roles',
                system: 'System',
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
                environment: 'Environment',
                description: 'Description',
                selectNode: 'Select an integration to configure'
            },
            actions: {
                edit: 'Edit Integration',
                delete: 'Delete Integration'
            },
            search: 'Search integrations...',
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
                        active: "Active",
                        disabled: "Disabled"
                    }
                }
            }
        }
    }
}
