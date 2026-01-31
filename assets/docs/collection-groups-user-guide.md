# Collection Groups User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Creating Collection Groups](#creating-collection-groups)
4. [Managing Collections in Groups](#managing-collections-in-groups)
5. [Using Groups in Dashboard Widgets](#using-groups-in-dashboard-widgets)
6. [Filtering Collections by Groups](#filtering-collections-by-groups)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [FAQs](#faqs)

---

## Introduction

### What are Collection Groups?

Collection Groups are a powerful organizational feature in MediaLake that allows you to group related collections together for easier management and filtering. Think of them as folders or labels for your collections.

### Key Benefits

- **Better Organization**: Group collections by project, team, client, or any other criteria
- **Focused Views**: Filter dashboard widgets to show only collections from specific groups
- **Easier Management**: Manage related collections as a logical unit
- **Flexible Membership**: Collections can belong to multiple groups simultaneously

### Use Cases

- **Project-Based Organization**: Group all collections related to a specific project
- **Team Collaboration**: Create groups for different teams or departments
- **Client Management**: Organize collections by client or customer
- **Workflow Stages**: Group collections by their stage in your workflow (e.g., "In Review", "Approved", "Published")
- **Campaign Management**: Group collections for marketing campaigns or initiatives

---

## Getting Started

### Prerequisites

- Active MediaLake account with appropriate permissions
- Access to the MediaLake web interface
- At least one collection created in your account

### Accessing Collection Groups

1. Log in to MediaLake
2. Navigate to the **Collection Groups** page from the main menu
3. You'll see a list of all your collection groups

---

## Creating Collection Groups

### Step-by-Step Guide

#### 1. Navigate to Collection Groups

Click on **Collection Groups** in the main navigation menu.

#### 2. Click "Create Group"

Click the **"Create New Group"** or **"+"** button at the top of the page.

#### 3. Fill in Group Details

A form will appear with the following fields:

- **Name** (Required): Enter a descriptive name for your group

  - Example: "Q1 2025 Marketing Campaign"
  - Keep it concise but descriptive
  - Maximum 255 characters

- **Description** (Optional): Add additional context about the group

  - Example: "All collections related to our Q1 marketing initiatives"
  - Maximum 1000 characters
  - Helps team members understand the group's purpose

- **Visibility** (Optional): Choose whether the group is public
  - **Public** (default): Visible to all users (future feature)
  - **Private**: Only visible to you (current implementation)

#### 4. Save the Group

Click **"Create"** or **"Save"** to create your new collection group.

### Quick Tips

- Use consistent naming conventions across your groups
- Add descriptions to help others understand the group's purpose
- Start with broad categories and refine as needed

---

## Managing Collections in Groups

### Adding Collections to a Group

#### Method 1: From the Group Page

1. Open the collection group you want to modify
2. Click **"Add Collections"** button
3. Select collections from the list or search for specific collections
4. Click **"Add Selected"** to add them to the group

#### Method 2: From the Collections Page

1. Navigate to the **Collections** page
2. Select one or more collections using checkboxes
3. Click **"Add to Group"** in the actions menu
4. Select the target group from the dropdown
5. Click **"Add"** to confirm

### Removing Collections from a Group

1. Open the collection group
2. Find the collection you want to remove
3. Click the **"Remove"** or **"×"** button next to the collection
4. Confirm the removal when prompted

**Note**: Removing a collection from a group does NOT delete the collection itself. It only removes the group membership.

### Viewing Collections in a Group

1. Open the collection group
2. You'll see a list of all collections in the group
3. Click on any collection to view its details
4. Use the search box to find specific collections within the group

---

## Using Groups in Dashboard Widgets

### Adding Group Filters to Widgets

Dashboard widgets can be configured to show only collections from specific groups.

#### Step-by-Step

1. Navigate to your **Dashboard**
2. Click **"Edit Dashboard"** or **"Add Widget"**
3. Select or create a **Collections Widget**
4. In the widget configuration panel:
   - Find the **"Filter by Groups"** section
   - Select one or more groups from the dropdown
   - The widget will now show only collections from the selected groups
5. Click **"Save"** to apply the changes

### Multiple Group Filtering

You can select multiple groups for a single widget:

- Collections that belong to **ANY** of the selected groups will be displayed (OR logic)
- This allows you to create combined views across related groups

### Combining with Other Filters

Group filters work alongside other widget filters:

- **View Type** (All, Favorites, Recent): Applied with AND logic
- **Example**: "Show favorites from Project Alpha group"

### Widget Examples

#### Example 1: Project Dashboard

```
Widget: "Project Alpha Collections"
Groups: ["Project Alpha - Assets", "Project Alpha - Deliverables"]
View Type: All
```

#### Example 2: Team Dashboard

```
Widget: "Design Team Favorites"
Groups: ["Design Team"]
View Type: Favorites
```

#### Example 3: Multi-Project View

```
Widget: "Active Projects"
Groups: ["Project Alpha", "Project Beta", "Project Gamma"]
View Type: Recent
```

---

## Filtering Collections by Groups

### Using the Collections Page Filter

1. Navigate to the **Collections** page
2. Look for the **"Filter by Groups"** dropdown in the toolbar
3. Select one or more groups to filter by
4. The collections list will update to show only collections from the selected groups

### Search and Filter Combinations

You can combine group filtering with other filters:

- **Search**: Filter by group AND search term
- **View Type**: Filter by group AND view type (all, favorites, recent)
- **Sort**: Apply sorting to filtered results

### Clearing Filters

- Click the **"×"** next to a selected group to remove it from the filter
- Click **"Clear All Filters"** to reset all filters

---

## Best Practices

### Naming Conventions

#### Good Examples

- "2025 Q1 Marketing Campaign"
- "Client: Acme Corp"
- "Team: Design - Active Projects"
- "Workflow: In Review"

#### Avoid

- "Group 1", "Group 2" (not descriptive)
- "asdfgh" (meaningless)
- "All my stuff" (too vague)

### Organization Strategies

#### Strategy 1: Project-Based

```
- Project Alpha - Assets
- Project Alpha - Deliverables
- Project Beta - Assets
- Project Beta - Deliverables
```

#### Strategy 2: Client-Based

```
- Client: Acme Corp
- Client: TechStart Inc
- Client: Global Media
```

#### Strategy 3: Workflow-Based

```
- Workflow: Draft
- Workflow: In Review
- Workflow: Approved
- Workflow: Published
```

#### Strategy 4: Hybrid

```
- Q1 2025: Client Acme
- Q1 2025: Client TechStart
- Q2 2025: Client Acme
```

### Group Maintenance

- **Regular Review**: Periodically review your groups and remove unused ones
- **Consistent Updates**: Keep group memberships up to date as collections change
- **Documentation**: Use descriptions to document group purposes
- **Archiving**: Consider creating "Archive" groups for completed projects

### Performance Tips

- Limit the number of groups to what you actively use
- Use descriptive names to avoid confusion
- Leverage dashboard widgets for quick access to grouped collections

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: Can't Create a Group

**Symptoms**: Create button is disabled or error message appears

**Solutions**:

1. Check that you're logged in with a valid account
2. Verify you have permission to create groups
3. Ensure the group name is not empty
4. Try refreshing the page and attempting again

#### Issue: Can't Add Collections to a Group

**Symptoms**: Collections don't appear in the group after adding

**Solutions**:

1. Verify you're the owner of the group
2. Check that the collections exist and you have access to them
3. Refresh the page to see if the collections appear
4. Try adding collections one at a time to identify problematic ones

#### Issue: Group Filter Not Working

**Symptoms**: Collections don't filter when selecting a group

**Solutions**:

1. Clear your browser cache and refresh
2. Verify the group contains collections
3. Check that the collections in the group are accessible to you
4. Try selecting a different group to see if the issue persists

#### Issue: Can't Delete a Group

**Symptoms**: Delete button doesn't work or error appears

**Solutions**:

1. Verify you're the owner of the group
2. Check your internet connection
3. Try refreshing the page and attempting again
4. Contact support if the issue persists

#### Issue: Collections Appear in Wrong Group

**Symptoms**: Collections show up in unexpected groups

**Solutions**:

1. Remember that collections can belong to multiple groups
2. Check all groups the collection belongs to
3. Remove the collection from unwanted groups
4. Verify you're looking at the correct group

---

## FAQs

### General Questions

**Q: How many groups can I create?**
A: There's no hard limit, but we recommend keeping it manageable (under 50 groups for optimal performance).

**Q: Can a collection belong to multiple groups?**
A: Yes! Collections can be members of as many groups as needed.

**Q: What happens to collections when I delete a group?**
A: The collections themselves are NOT deleted. Only the group and its memberships are removed.

**Q: Can I share groups with other users?**
A: Currently, groups are private to the owner. Public groups will be available in a future release.

**Q: Can I rename a group after creating it?**
A: Yes, you can edit the group name and description at any time.

### Permissions Questions

**Q: Who can create collection groups?**
A: Any authenticated user can create collection groups.

**Q: Who can add collections to my group?**
A: Only you (the group owner) can add or remove collections. Pipeline automation may also add collections in future releases.

**Q: Can I transfer ownership of a group?**
A: Currently, ownership cannot be transferred. This feature may be added in the future.

**Q: What happens to my groups if my account is deleted?**
A: Your groups will be deleted along with your account. The collections themselves will remain.

### Technical Questions

**Q: How are groups stored?**
A: Groups are stored in DynamoDB using a single-table design pattern for optimal performance.

**Q: Is there an API for managing groups?**
A: Yes! See the [Collection Groups API Documentation](collection-groups-api.md) for details.

**Q: Can I use groups in automation workflows?**
A: Yes, pipelines can add/remove collections from groups programmatically (future feature).

**Q: How does group filtering affect performance?**
A: Group filtering is optimized using DynamoDB queries and should have minimal performance impact.

### Dashboard Questions

**Q: Can I use multiple groups in a single widget?**
A: Yes, you can select multiple groups. Collections from ANY of the selected groups will be displayed.

**Q: What happens if I delete a group that's used in a widget?**
A: The widget will gracefully handle the missing group and show collections from remaining groups.

**Q: Can I save widget configurations with group filters?**
A: Yes, group filters are saved as part of the widget configuration.

**Q: How do group filters combine with other filters?**
A: Group filters use OR logic (any selected group), and combine with other filters using AND logic.

---

## Getting Help

### Support Resources

- **Documentation**: [MediaLake Documentation](https://docs.medialake.example.com)
- **API Reference**: [Collection Groups API](collection-groups-api.md)
- **Email Support**: api-support@medialake.example.com
- **Community Forum**: https://community.medialake.example.com

### Reporting Issues

If you encounter a bug or issue:

1. Note the exact steps to reproduce the problem
2. Take screenshots if applicable
3. Check the browser console for error messages
4. Contact support with the above information

### Feature Requests

Have an idea for improving Collection Groups?

1. Check if the feature is already planned in our roadmap
2. Submit a feature request through our support portal
3. Provide detailed use cases and examples
4. Vote on existing feature requests from other users

---

## Appendix

### Keyboard Shortcuts

- `Ctrl/Cmd + K`: Quick search for groups
- `Ctrl/Cmd + N`: Create new group (when on groups page)
- `Esc`: Close dialogs and modals

### Browser Compatibility

Collection Groups are supported on:

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

### Mobile Support

Collection Groups are fully supported on mobile devices through the responsive web interface.

---

## Changelog

### Version 1.0.0 (January 30, 2025)

- Initial release of Collection Groups feature
- Create, update, and delete groups
- Add and remove collections from groups
- Filter collections by groups
- Dashboard widget integration
- Owner-based permissions

---

_Last Updated: January 30, 2025_
_Version: 1.0.0_
