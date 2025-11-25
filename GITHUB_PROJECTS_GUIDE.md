# GitHub Projects Setup & Usage Guide

This guide will help your team set up and use GitHub Projects for task tracking and project management.

## Quick Setup (5 Minutes)

### Step 1: Create Your Project Board

1. Go to your repository on GitHub: https://github.com/Bright-Smile-Smart/Bright-Smile-BE
2. Click the **"Projects"** tab at the top
3. Click **"New project"**
4. Choose **"Board"** view (or Table view if you prefer)
5. Name it: **"Bright Smile Development"**
6. Click **"Create"**

### Step 2: Set Up Columns

Your project board should have these columns (drag and drop to create):

1. **📋 Backlog** - Ideas and future work
2. **📝 To Do** - Ready to be worked on
3. **🚧 In Progress** - Currently being worked on
4. **👀 In Review** - PR submitted, awaiting review
5. **✅ Done** - Completed work

To add columns:
- Click **"+ New column"** or the **"+"** button
- Name the column
- Repeat for all columns

### Step 3: Configure Automation

GitHub Projects can automatically move cards based on issue/PR status:

1. Click the **"⋯"** (three dots) on each column
2. Select **"Manage automation"**
3. Configure:
   - **To Do**: Auto-add newly created issues
   - **In Progress**: Auto-move when issue is assigned
   - **In Review**: Auto-move when PR is opened
   - **Done**: Auto-move when PR is merged or issue is closed

## Using Issue Templates

We've created three issue templates for your team:

### 🐛 Bug Report
Use this when you find a bug or issue.

**To create:**
1. Go to **Issues** → **New Issue**
2. Select **"Bug Report"**
3. Fill out:
   - Bug description
   - Steps to reproduce
   - Expected vs actual behavior
   - Severity level
   - Environment details
   - Relevant logs

### ✨ Feature Request
Use this to propose new features or enhancements.

**To create:**
1. Go to **Issues** → **New Issue**
2. Select **"Feature Request"**
3. Fill out:
   - Problem statement
   - Proposed solution
   - Alternatives considered
   - Priority level
   - Technical details

### 📋 Task
Use this for general work items.

**To create:**
1. Go to **Issues** → **New Issue**
2. Select **"Task"**
3. Fill out:
   - Task description
   - Acceptance criteria (checklist)
   - Category (Development, Testing, etc.)
   - Priority
   - Time estimate
   - Dependencies

## Team Workflow

### 1. Creating Work Items

**Anyone on the team can:**
- Create an issue using templates
- Add labels (bug, enhancement, task, etc.)
- Assign to team members
- Add to project board
- Set priority

### 2. Starting Work

When you start working on an issue:
1. **Assign yourself** to the issue
2. **Move to "In Progress"** column
3. **Create a branch**: `git checkout -b feature/issue-123-description`
4. **Update the issue** with progress notes

### 3. Submitting Work

When ready for review:
1. **Push your branch**: `git push origin feature/issue-123-description`
2. **Create a Pull Request** (use the PR template)
3. **Link the issue**: Use `Closes #123` in PR description
4. **Request reviews** from team members
5. **PR automatically moves to "In Review"**

### 4. Code Review

Reviewers should:
- Check code quality and logic
- Test the changes locally
- Provide constructive feedback
- Approve or request changes

### 5. Merging

After approval:
1. **Merge the PR** (squash and merge recommended)
2. **Issue automatically moves to "Done"**
3. **Delete the branch**

## Best Practices

### For Issue Creation
- ✅ Use clear, descriptive titles
- ✅ Fill out all required fields in templates
- ✅ Add relevant labels
- ✅ Link related issues
- ✅ Break large tasks into smaller issues
- ❌ Don't create duplicate issues (search first)

### For Task Management
- ✅ Keep issues up to date
- ✅ Use comments to communicate progress
- ✅ Close issues when done
- ✅ Reference issues in commits: `git commit -m "Fix login bug #123"`
- ❌ Don't let issues go stale

### For Pull Requests
- ✅ Use the PR template
- ✅ Write clear descriptions
- ✅ Keep PRs focused and small
- ✅ Request reviews from specific people
- ✅ Respond to review comments
- ❌ Don't merge your own PRs without review

## Labels Guide

Use these labels to categorize issues:

### Type
- `bug` - Something isn't working
- `enhancement` - New feature or improvement
- `task` - General work item
- `documentation` - Documentation updates
- `refactoring` - Code refactoring

### Priority
- `priority: critical` - Urgent, blocking work
- `priority: high` - Important for near-term
- `priority: medium` - Should be done soon
- `priority: low` - Nice to have

### Status
- `needs-triage` - New issue, needs review
- `needs-discussion` - Requires team discussion
- `blocked` - Waiting on something
- `good first issue` - Good for new contributors

### Area
- `backend` - Backend/API work
- `database` - Database changes
- `devops` - Infrastructure/deployment
- `testing` - Testing improvements
- `celery` - Background tasks

## GitHub CLI (Optional but Recommended)

Install GitHub CLI for faster workflows:

### Installation
```bash
# macOS
brew install gh

# Or download from: https://cli.github.com/
```

### Authentication
```bash
gh auth login
```

### Quick Commands
```bash
# Create an issue
gh issue create --title "Fix login bug" --body "Description here"

# List issues
gh issue list

# View issue
gh issue view 123

# Create a PR
gh pr create --title "Fix login" --body "Fixes #123"

# Review a PR
gh pr review 456 --approve

# Merge a PR
gh pr merge 456 --squash
```

## Keyboard Shortcuts

Speed up your workflow with GitHub shortcuts:

- `c` - Create new issue/PR
- `g` + `i` - Go to Issues
- `g` + `p` - Go to Pull Requests
- `/` - Focus search bar
- `?` - Show all keyboard shortcuts

## Team Collaboration Tips

### Daily Standup
Use the project board during standups:
- What did you work on? (check In Progress)
- What are you working on today? (assign yourself)
- Any blockers? (mark issues as blocked)

### Sprint Planning
1. Review Backlog column
2. Move items to To Do for current sprint
3. Assign team members
4. Estimate effort
5. Set milestones

### Weekly Review
1. Review Done column
2. Close completed issues
3. Update project documentation
4. Celebrate wins! 🎉

## Example Workflows

### Workflow 1: Fixing a Bug
```bash
# 1. Someone reports a bug (creates issue)
# Issue #123 created: "Login fails with Gmail accounts"

# 2. You assign yourself and move to In Progress
gh issue edit 123 --add-assignee @me

# 3. Create branch and fix
git checkout -b fix/login-gmail-123
# ... make changes ...
git commit -m "Fix Gmail login issue #123"
git push origin fix/login-gmail-123

# 4. Create PR
gh pr create --title "Fix Gmail login issue" --body "Closes #123"

# 5. After review, merge (issue auto-closes and moves to Done)
```

### Workflow 2: Adding a Feature
```bash
# 1. Create feature request issue
gh issue create --title "Add user profile pictures" --label enhancement

# 2. Team discusses in issue comments
# 3. Once approved, assign and start work
# 4. Follow same PR workflow as above
```

## Troubleshooting

### Issue not appearing in project board?
- Make sure the issue is added to the project
- Check project filters
- Refresh the page

### PR not auto-moving columns?
- Check automation settings
- Ensure PR is linked to an issue
- Verify PR is in the project

### Can't create issues?
- Check repository permissions
- Ensure you're logged in
- Try refreshing the page

## Additional Resources

- [GitHub Projects Documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub Issues Documentation](https://docs.github.com/en/issues)
- [GitHub Pull Requests](https://docs.github.com/en/pull-requests)
- [GitHub CLI Documentation](https://cli.github.com/manual/)

## Questions?

If you have questions about using GitHub Projects:
1. Check this guide
2. Ask in team chat
3. Check [GitHub Docs](https://docs.github.com/)
4. Create a discussion in the repository

---

**Now go create your project board and start tracking your work!** 🚀
