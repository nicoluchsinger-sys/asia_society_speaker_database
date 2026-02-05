---
trigger: always_on
---

# 40_git.md - Version Control with Git

## Philosophy
Git is your time machine and safety net. Use it from day one, commit often, and never be afraid to experiment.

---

## Setting Up a New Project

### Step 1: Initialize Git
```bash
# Navigate to your project folder
cd my-project

# Initialize Git repository
git init

# Create initial commit
git add .
git commit -m "Initial commit"
```

### Step 2: Create GitHub Repository
```bash
# Create a new repository on GitHub (via web interface)
# Then connect your local repository

git remote add origin https://github.com/yourusername/your-repo.git
git branch -M main
git push -u origin main
```

### Step 3: Essential Files

Create `.gitignore` before your first commit:
```
# .gitignore

# Dependencies
node_modules/
.pnp
.pnp.js

# Testing
coverage/

# Next.js
.next/
out/
build
dist

# Environment variables
.env
.env*.local

# Debug logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Misc
*.log
.vercel
```

---

## Commit Standards

### Commit Message Format
Use clear, descriptive commit messages following this pattern:

```
type: brief description

Optional longer description explaining what and why
```

### Commit Types
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, no logic change)
- `refactor:` Code restructuring (no functional change)
- `test:` Adding or updating tests
- `chore:` Maintenance tasks (dependencies, config)

### Examples
```bash
# ✅ Good commit messages
git commit -m "feat: add user authentication with NextAuth"
git commit -m "fix: resolve database connection timeout issue"
git commit -m "docs: update README with setup instructions"
git commit -m "refactor: simplify user profile component logic"

# ❌ Bad commit messages (too vague)
git commit -m "updates"
git commit -m "fix stuff"
git commit -m "wip"
```

### When to Commit
Commit when you've completed a **small, logical unit of work**:
- ✅ Added a new component
- ✅ Fixed a bug
- ✅ Completed a feature
- ✅ Updated documentation
- ✅ Refactored a function

**Commit often** - better to have many small commits than one giant commit.

---

## Branching Strategy

### Main Branch
- `main` - always stable, deployable code
- Never commit directly to `main` for features (though okay when working solo)

### Feature Branches
For any new feature or significant change:

```bash
# Create a new branch for your feature
git checkout -b feature/user-authentication

# Work on your feature, commit regularly
git add .
git commit -m "feat: add login form component"

# When done, merge back to main
git checkout main
git merge feature/user-authentication

# Delete the feature branch
git branch -d feature/user-authentication
```

### Branch Naming
- `feature/description` - new features
- `fix/description` - bug fixes
- `refactor/description` - code improvements
- `docs/description` - documentation

Examples:
- `feature/user-profile`
- `fix/login-redirect`
- `refactor/database-queries`
- `docs/api-documentation`

---

## Daily Workflow

### Starting Work
```bash
# Make sure you're on main branch
git checkout main

# Get latest changes
git pull origin main

# Create feature branch (or continue existing one)
git checkout -b feature/my-feature
```

### During Work
```bash
# See what's changed
git status

# See detailed changes
git diff

# Add specific files
git add src/components/NewComponent.tsx

# Or add all changes
git add .

# Commit with message
git commit -m "feat: add new component"

# Push to GitHub
git push origin feature/my-feature
```

### Ending Work Session
```bash
# Make sure everything is committed
git status

# Push to GitHub (backup!)
git push origin feature/my-feature
```

---

## Common Git Commands

### Checking Status
```bash
# See what files have changed
git status

# See actual code changes
git diff

# See commit history
git log

# See pretty commit history
git log --oneline --graph
```

### Undoing Changes

```bash
# Discard changes in a specific file (not staged)
git checkout -- filename.ts

# Discard all unstaged changes
git checkout -- .

# Unstage a file (keep changes)
git reset HEAD filename.ts

# Undo last commit (keep changes)
git reset --soft HEAD~1

# ⚠️ Undo last commit (DISCARD changes)
git reset --hard HEAD~1  # DANGEROUS - you'll lose work!
```

### Stashing Work
```bash
# Save current changes without committing
git stash

# List stashed changes
git stash list

# Restore most recent stash
git stash pop

# Restore specific stash
git stash apply stash@{0}
```

---

## Working with GitHub

### Pushing Changes
```bash
# First time pushing a new branch
git push -u origin feature/my-feature

# Subsequent pushes
git push
```

### Pulling Changes
```bash
# Get latest changes from GitHub
git pull origin main
```

### Merge Conflicts
When Git can't automatically merge changes:

```bash
# After pulling or merging, if you see conflicts:
# 1. Open the conflicting files in your editor
# 2. Look for conflict markers:

<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> branch-name

# 3. Manually resolve by choosing what to keep
# 4. Remove conflict markers
# 5. Add and commit

git add .
git commit -m "fix: resolve merge conflicts"
```

---

## AI Assistant Git Integration

### When AI Should Commit
The AI assistant will help with commits when:
1. A logical unit of work is complete
2. You explicitly request a commit
3. After successfully implementing a feature
4. Before switching to a different task

### What AI Will Do
1. **Review changes**: Check what files were modified
2. **Check git status**: See what's staged and unstaged
3. **Suggest commit message**: Following the commit standards above
4. **Stage files**: Add relevant changes
5. **Create commit**: With descriptive message
6. **Suggest push**: Recommend pushing to GitHub

### Commit Message Template
The AI will use this format:
```
type: brief description

- Detail about what changed
- Why this change was made
- Any important notes

Co-authored-by: AI Assistant
```

---

## Safety Rules

### ⚠️ Dangerous Commands (Always Confirm First)
```bash
# These can cause data loss - AI must warn before running:

git reset --hard          # Discards all uncommitted changes
git clean -fd             # Deletes untracked files
git push --force          # Overwrites remote history
git branch -D branch      # Force deletes branch
git checkout .            # Discards all changes
```

**The AI will always**:
1. Explain what the command will do
2. Explain what you'll lose
3. Ask for explicit confirmation
4. Suggest safer alternatives

### Safe Commands (No Warning Needed)
```bash
git status                # Just shows status
git log                   # Shows history
git diff                  # Shows changes
git add                   # Stages changes
git commit                # Creates commit
git push                  # Uploads to GitHub
git pull                  # Downloads from GitHub
git branch                # Lists branches
git checkout -b           # Creates new branch
```

---

## .gitignore Best Practices

### What to Ignore
Always add these to `.gitignore`:
1. **Dependencies**: `node_modules/`, `vendor/`
2. **Environment files**: `.env`, `.env.local`, `.env*.local`
3. **Build outputs**: `.next/`, `dist/`, `build/`, `out/`
4. **IDE files**: `.vscode/`, `.idea/`
5. **OS files**: `.DS_Store`, `Thumbs.db`
6. **Logs**: `*.log`, `npm-debug.log*`
7. **Temporary files**: `*.tmp`, `*.temp`

### What NOT to Ignore
These should be committed:
1. **Source code**: All `.ts`, `.tsx`, `.js`, `.jsx` files
2. **Configuration**: `package.json`, `tsconfig.json`, `next.config.js`
3. **Documentation**: `README.md`, `CHANGELOG.md`
4. **Templates**: `.env.example` (without real secrets)
5. **Public assets**: Images, fonts in `public/`

---

## Collaborative Git (When Working with Others)

Even though you're working alone now, here are good practices for future collaboration:

### Pull Before Push
```bash
# Always get latest changes before pushing
git pull origin main
git push origin main
```

### Descriptive Commit Messages
Others need to understand your changes without asking you.

### Small, Focused Commits
Easier to review and understand.

### Branch Protection
On GitHub, protect `main` branch:
- Require pull request reviews
- Require status checks to pass
- No force pushes

---

## Emergency: "I Messed Up Git!"

### "I committed to the wrong branch"
```bash
# Don't panic! Create a new branch from current position
git branch feature/my-feature

# Go back to main
git checkout main

# Reset main to before your commits
git reset --hard origin/main

# Go to your new branch
git checkout feature/my-feature
# Your commits are safe here!
```

### "I need to undo my last commit"
```bash
# Keep the changes, just undo commit
git reset --soft HEAD~1

# Edit and recommit
git add .
git commit -m "Better commit message"
```

### "I accidentally deleted important code"
```bash
# If you committed it before, you can get it back
git reflog  # Find the commit hash
git checkout <commit-hash> -- path/to/file
```

### "My working directory is a mess"
```bash
# Start fresh from last commit
git stash  # Save current work (just in case)
git checkout .  # Discard all changes
git clean -fd  # Remove untracked files

# If you want your work back:
git stash pop
```

---

## Git Workflow Checklist

### Starting a New Project
- [ ] `git init`
- [ ] Create `.gitignore`
- [ ] Initial commit
- [ ] Create GitHub repository
- [ ] Push to GitHub

### Daily Development
- [ ] Pull latest changes
- [ ] Create/checkout feature branch
- [ ] Make changes
- [ ] Test changes work
- [ ] Stage changes (`git add`)
- [ ] Commit with clear message
- [ ] Push to GitHub

### Finishing a Feature
- [ ] All changes committed
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Merge to main
- [ ] Delete feature branch
- [ ] Push to GitHub

---

## Getting Help

If you're stuck with Git:
1. **Check status**: `git status` shows what state you're in
2. **Ask AI assistant**: Explain what you were trying to do
3. **Don't panic**: Git is very hard to break permanently
4. **Git documentation**: [git-scm.com/doc](https://git-scm.com/doc)

Remember: Git saves everything, so it's almost always possible to recover from mistakes!
