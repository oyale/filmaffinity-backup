# GitHub Projects Setup Guide for Maintainers

This guide will help you set up the GitHub Projects board for the filmaffinity-backup repository.

## Quick Setup (5-10 minutes)

### Step 1: Create a New Project

1. Go to https://github.com/oyale/filmaffinity-backup
2. Click on the **"Projects"** tab
3. Click **"New project"**
4. Choose **"Board"** template
5. Name it: **"FilmAffinity Backup Roadmap"**
6. Click **"Create project"**

### Step 2: Configure Custom Fields

Once the project is created, add these custom fields:

1. Click the **"+"** button next to the column headers
2. Add **"New field"** for each of the following:

| Field Name | Type | Options |
|------------|------|---------|
| **Priority** | Single select | 🔴 High, 🟡 Medium, 🟢 Low |
| **Version** | Single select | v1.1.0, v1.2.0, v1.3.0, v1.4.0, v2.0.0, Future |
| **Component** | Single select | FA Backup, IMDb Upload, Documentation, CI/CD, Testing, Other |
| **Size** | Single select | Small (< 1 day), Medium (1-3 days), Large (> 3 days) |

### Step 3: Create Custom Views

Create additional views for better tracking:

#### View 1: By Version
1. Click **"+ New view"**
2. Name: **"By Version"**
3. Layout: **"Board"**
4. Group by: **"Version"**
5. Sort by: **"Priority"** (descending)

#### View 2: By Priority
1. Click **"+ New view"**
2. Name: **"By Priority"**
3. Layout: **"Board"**
4. Group by: **"Priority"**
5. Sort by: **"Created"** (newest first)

#### View 3: Current Sprint
1. Click **"+ New view"**
2. Name: **"Current Sprint"**
3. Layout: **"Table"**
4. Filter: `Status is "In Progress" OR Status is "TODO"`
5. Sort by: **"Priority"** (descending)

### Step 4: Configure Project Automation

The repository already includes a workflow (`.github/workflows/project-automation.yml`) that automatically adds issues to the project.

To enable it:

#### Option A: Using PROJECT_TOKEN (Recommended)

1. Create a Personal Access Token (PAT):
   - Go to https://github.com/settings/tokens
   - Click **"Generate new token (classic)"**
   - Give it a name: "filmaffinity-backup-project"
   - Select scopes:
     - ✅ `public_repo` (or `repo` for private repos)
     - ✅ `project` (to manage projects)
   - Click **"Generate token"**
   - **Copy the token** (you won't see it again!)

2. Add the token to repository secrets:
   - Go to https://github.com/oyale/filmaffinity-backup/settings/secrets/actions
   - Click **"New repository secret"**
   - Name: `PROJECT_TOKEN`
   - Value: (paste the token)
   - Click **"Add secret"**

3. Add the project URL as a variable:
   - Go to https://github.com/oyale/filmaffinity-backup/settings/variables/actions
   - Click **"New repository variable"**
   - Name: `PROJECT_URL`
   - Value: Your project URL (e.g., `https://github.com/users/oyale/projects/1`)
   - Click **"Add variable"**

#### Option B: Using GITHUB_TOKEN (Simpler, but may require permissions)

If you don't want to create a PAT, you can use the built-in `GITHUB_TOKEN`:

1. Just add the `PROJECT_URL` variable as described above
2. Make sure the workflow has the right permissions (already configured)
3. Note: This may not work for user projects, only organization projects

### Step 5: Enable Built-in Project Automations

In your project settings, enable these automations:

1. Click the **"⋯"** menu in the project → **"Settings"**
2. Go to **"Workflows"**
3. Enable these built-in workflows:
   - ✅ **Auto-add to project**: When items have labels: `roadmap`, `bug`, `enhancement`
   - ✅ **Auto-archive items**: When item status is "Done" → Archive after 7 days
   - ✅ **Item closed**: Set status to "Done"
   - ✅ **Pull request merged**: Set status to "Done"

### Step 6: Populate Initial Issues from Roadmap

Now that the project is set up, you can create issues for roadmap items:

1. Go to https://github.com/oyale/filmaffinity-backup/issues/new/choose
2. Select **"🗺️ Roadmap Item"** template
3. Fill in the details from ROADMAP.md
4. The issue will automatically be added to the project (if automation is working)
5. Set the **Version**, **Priority**, and **Component** fields in the project

**Tip**: Start with high-priority items from v1.1.0 and v1.2.0.

## Testing the Integration

To test if everything is working:

1. Create a test issue with the `roadmap` label
2. Check if it appears in the project board
3. Move it to "In Progress" → "Done"
4. Verify it archives after 7 days (or test with shorter time)

## Troubleshooting

### Issues not automatically added to project

- Check that the `PROJECT_URL` variable is set correctly
- Verify the `PROJECT_TOKEN` has the right permissions
- Check the workflow run logs: https://github.com/oyale/filmaffinity-backup/actions

### Workflow permission errors

- Make sure the PAT has `project` scope
- For organization projects, ensure the PAT user has write access to the project

### Can't see the project

- User projects: Only visible to the user who created them
- Organization projects: Check visibility settings in project settings

## Recommended Workflow

Once set up, here's how to use the project:

1. **Weekly**: Review "Current Sprint" view, plan work for the week
2. **Daily**: Check "In Progress" items, move completed items to "Done"
3. **Monthly**: Review "By Version" view, assess progress on roadmap
4. **Quarterly**: Review "By Priority" view, re-prioritize as needed

## Next Steps

After setup:

1. Create issues for v1.1.0 high-priority items
2. Label them with `roadmap`, `bug`, or `enhancement`
3. Set appropriate fields (Version, Priority, Component)
4. Start working on items and move them through the board
5. Share the project URL with contributors

## Resources

- [GitHub Projects Documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub Actions: Add to Project](https://github.com/marketplace/actions/add-to-github-projects)
- [Project Automation Examples](https://github.com/actions/add-to-project#examples)

---

Need help? Open an issue or reach out to the community!
