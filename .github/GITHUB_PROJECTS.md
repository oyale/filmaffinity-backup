# GitHub Projects Integration Guide

This repository uses GitHub Projects to track roadmap items, bugs, and feature requests. This guide explains how to set up and use the project board.

## 🎯 Project Board Structure

The project board is organized to track the roadmap outlined in [ROADMAP.md](../ROADMAP.md).

### Recommended Views

1. **By Status** - Default view showing TODO, In Progress, Done
2. **By Version** - Group items by roadmap version (v1.1.0, v1.2.0, etc.)
3. **By Priority** - Sort by priority (High, Medium, Low)
4. **By Component** - Group by component (FilmAffinity Backup, IMDb Uploader, etc.)

## 🚀 Setting Up GitHub Projects

### For Repository Maintainers

1. **Create a new Project**
   - Go to https://github.com/oyale/filmaffinity-backup/projects
   - Click "New project"
   - Choose "Board" template
   - Name it "FilmAffinity Backup Roadmap"

2. **Configure Project Fields**
   
   Add these custom fields to your project:

   | Field Name | Type | Options |
   |------------|------|---------|
   | Status | Single select | TODO, In Progress, Blocked, Done |
   | Priority | Single select | High, Medium, Low |
   | Version | Single select | v1.1.0, v1.2.0, v1.3.0, v1.4.0, v2.0.0 |
   | Component | Single select | FA Backup, IMDb Upload, Docs, CI/CD, Other |
   | Size | Single select | Small, Medium, Large |

3. **Set up Automation**
   
   The repository includes a workflow (`.github/workflows/project-automation.yml`) that automatically adds labeled issues to the project.
   
   To enable it:
   - Create a Personal Access Token (PAT) with `project` scope
   - Add it as a repository secret named `PROJECT_TOKEN`
   - Set the `PROJECT_URL` variable to your project URL

4. **Configure Project Workflows**
   
   In your project settings, enable these built-in automations:
   - Auto-add items with labels: `roadmap`, `bug`, `enhancement`
   - Auto-archive: Items with status "Done" → Archive after 7 days
   - Auto-close: When PR is merged → Set status to "Done"

## 📝 Creating Issues from the Roadmap

To track a roadmap item as a GitHub issue:

1. Go to [Issues → New Issue](https://github.com/oyale/filmaffinity-backup/issues/new/choose)
2. Select the **"🗺️ Roadmap Item"** template
3. Fill in:
   - **Version**: Select the roadmap version (e.g., v1.1.0)
   - **Category**: Select the category (e.g., Documentation)
   - **Description**: Copy from ROADMAP.md
4. Submit the issue
5. The issue will automatically be added to the project board (if automation is configured)

## 🏷️ Label System

| Label | Purpose | Auto-added to Project |
|-------|---------|----------------------|
| `roadmap` | Items from the roadmap | ✅ Yes |
| `bug` | Bug reports | ✅ Yes |
| `enhancement` | Feature requests | ✅ Yes |
| `documentation` | Documentation changes | ✅ Yes |
| `good first issue` | Good for newcomers | ❌ No |
| `help wanted` | Extra attention needed | ❌ No |
| `wontfix` | Will not be fixed | ❌ No |

## 🔄 Workflow

### For Issues

1. **TODO** - Issue is created and ready to be worked on
2. **In Progress** - Someone is actively working on it
3. **Blocked** - Work is blocked by dependencies or questions
4. **Done** - Issue is closed

### For Pull Requests

1. **In Review** - PR is open and awaiting review
2. **Changes Requested** - Reviewer requested changes
3. **Approved** - PR is approved and ready to merge
4. **Merged** - PR is merged (auto-moves to Done)

## 📊 Using the Project Board

### For Contributors

1. Browse the project board to find issues to work on
2. Filter by:
   - **Status: TODO** - Available work
   - **Label: good first issue** - Beginner-friendly tasks
   - **Priority: High** - Important items
3. Assign yourself to an issue before starting work
4. Move the issue to "In Progress"
5. Create a PR and link it to the issue
6. The issue will automatically close when the PR is merged

### For Maintainers

1. **Triage new issues**
   - Add appropriate labels
   - Set version, priority, and component fields
   - Add to project if not auto-added

2. **Track progress**
   - Use the "By Version" view to track release progress
   - Use the "By Status" view to see what's in progress
   - Review blocked items regularly

3. **Plan releases**
   - Create milestones for each version
   - Link issues to milestones
   - Use project views to track milestone progress

## 🔗 Integration with ROADMAP.md

The ROADMAP.md file is the source of truth for planned features. When implementing items:

1. Create an issue from the roadmap item
2. Check the box in ROADMAP.md when work starts
3. Link the issue in ROADMAP.md (optional)
4. Update ROADMAP.md when the item is completed

Example:
```markdown
### v1.1.0 - Documentation
* [x] Add issue/PR templates for GitHub (#42)
* [ ] Add CONTRIBUTING.md (#43)
```

## 🛠️ Advanced Configuration

### Custom Project Views

Create custom views for specific workflows:

**1. Current Sprint**
```
Filter: Status is "In Progress" OR Status is "TODO"
Sort: Priority descending
Group by: Component
```

**2. Bugs Only**
```
Filter: Label includes "bug"
Sort: Created (newest first)
Group by: Priority
```

**3. Community Contributions**
```
Filter: Label includes "good first issue" OR Label includes "help wanted"
Sort: Created (newest first)
```

### Linking to Projects in README

Add a badge to your README:

```markdown
[![Project Board](https://img.shields.io/badge/Project-Board-blue)](https://github.com/oyale/filmaffinity-backup/projects/1)
```

## 📚 Resources

- [GitHub Projects Documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub Projects Best Practices](https://github.blog/2022-07-27-planning-next-to-your-code-github-projects-is-now-generally-available/)
- [Automating Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project)

## 💡 Tips

- **Use templates**: Issue templates ensure consistent information
- **Update regularly**: Keep project status current
- **Communicate**: Use comments to discuss progress and blockers
- **Link everything**: Connect issues, PRs, and commits
- **Review often**: Regular project reviews keep momentum
