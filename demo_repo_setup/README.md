# Demo Target Repository Setup Instructions

This directory contains prop files used to create a throwaway public GitHub repository (`demo-target-repo`) to generate live GitHub Actions build failures and live OSV.dev vulnerability scan results.

---

## 🛠️ Step-by-Step GitHub Setup

### Step 1: Create GitHub Repository
1. Log in to your personal GitHub account.
2. Create a new **Public** repository named `demo-target-repo` (e.g., `ps-tanish-sethiya/demo-target-repo`).
3. Leave it empty (without initializing README or license).

### Step 2: Copy Files into Repo Root
In your local workspace or temporary directory:
```bash
mkdir demo-target-repo
cd demo-target-repo
git init
git branch -M main

# Copy files from DevSentinel's demo_repo_setup/
cp /path/to/devsentinel/demo_repo_setup/sample_app.py ./sample_app.py
cp /path/to/devsentinel/demo_repo_setup/sample_test.py ./sample_test.py
cp /path/to/devsentinel/demo_repo_setup/sample_requirements.txt ./requirements.txt

# Create GitHub Actions workflow folder
mkdir -p .github/workflows
cp /path/to/devsentinel/demo_repo_setup/sample_workflow.yml .github/workflows/ci.yml
```

### Step 3: Push to GitHub
```bash
git add .
git commit -m "initial commit with intentional build failure and outdated pyyaml"
git remote add origin https://github.com/YOUR_USERNAME/demo-target-repo.git
git push -u origin main
```

### Step 4: Configure DevSentinel `.env`
Update your DevSentinel `.env` file with the newly created repository:
```env
GITHUB_DEMO_REPO=YOUR_USERNAME/demo-target-repo
```

Upon pushing, GitHub Actions will trigger `ci.yml` and fail on `sample_test.py`, giving DevSentinel a live failed workflow run ID to query!
