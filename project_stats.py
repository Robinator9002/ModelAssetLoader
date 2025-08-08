import os
import re
import subprocess
from collections import Counter
from datetime import datetime

# ========== CONFIG ==========
INCLUDE_EXTS = {".tsx", ".css", ".py"}
EXCLUDE_DIRS = {".venv", "node_modules", "__pycache__", ".git"}
EXCLUDE_FILES = {"pyproject.toml", "__init__.py"}
# ============================

def is_code_file(path):
    return (
        os.path.splitext(path)[1] in INCLUDE_EXTS
        and os.path.basename(path) not in EXCLUDE_FILES
    )

def count_file_stats(filepath):
    stats = {
        "lines": 0,
        "tokens": 0,
        "letters": 0,
        "functions": 0,
        "classes": 0
    }
    token_pattern = re.compile(r"\w+")
    func_pattern = re.compile(r"^\s*(?:def|function)\s+\w+", re.IGNORECASE)
    class_pattern = re.compile(r"^\s*class\s+\w+")

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                stats["lines"] += 1
                tokens = token_pattern.findall(line)
                stats["tokens"] += len(tokens)
                stats["letters"] += sum(len(t) for t in tokens)
                if func_pattern.search(line):
                    stats["functions"] += 1
                if class_pattern.search(line):
                    stats["classes"] += 1
    except Exception as e:
        print(f"⚠️ Could not read {filepath}: {e}")
    return stats

def walk_project():
    total_stats = Counter()
    file_count = 0

    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if is_code_file(file):
                path = os.path.join(root, file)
                file_stats = count_file_stats(path)
                total_stats.update(file_stats)
                file_count += 1
    total_stats["files"] = file_count
    return total_stats

def get_git_info():
    def run_git(cmd):
        try:
            return subprocess.check_output(cmd, shell=True, text=True).strip()
        except subprocess.CalledProcessError:
            return None

    git_info = {
        "repo_name": run_git("basename `git rev-parse --show-toplevel`"),
        "total_commits": run_git("git rev-list --all --count"),
        "latest_commit_date": run_git("git log -1 --format=%cd"),
        "latest_commit_author": run_git("git log -1 --format=%an"),
        "current_branch": run_git("git rev-parse --abbrev-ref HEAD"),
        "top_contributor": run_git(
            "git shortlog -sn --all | head -n 1 | awk '{print $2, $3}'"
        )
    }
    return git_info

def print_report(stats, git_info):
    print("\n📊 PROJECT CODE STATS")
    print("=" * 40)
    for key in ["files", "lines", "tokens", "letters", "functions", "classes"]:
        print(f"{key.capitalize():<12}: {stats[key]:>10}")

    print("\n📂 GIT REPOSITORY INFO")
    print("=" * 40)
    for k, v in git_info.items():
        print(f"{k.replace('_', ' ').capitalize():<20}: {v}")

    print("\n💡 EXTRA INSIGHTS")
    print("=" * 40)
    avg_tokens_per_line = stats["tokens"] / stats["lines"] if stats["lines"] else 0
    avg_letters_per_token = stats["letters"] / stats["tokens"] if stats["tokens"] else 0
    print(f"Average tokens per line   : {avg_tokens_per_line:.2f}")
    print(f"Average letters per token : {avg_letters_per_token:.2f}")

if __name__ == "__main__":
    stats = walk_project()
    git_info = get_git_info()
    print_report(stats, git_info)
