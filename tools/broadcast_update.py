import os
import sys
import shutil
import subprocess
import argparse
import json
import concurrent.futures
import threading
from datetime import datetime

# Configuration
GRADING_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE_TMP_DIR = os.path.join(GRADING_ROOT, "tmp", "broadcast_workers")

# Thread-safe printing lock
print_lock = threading.Lock()

def safe_print(msg):
    with print_lock:
        print(msg)

def run_cmd(cmd, cwd=None, capture_output=True):
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, check=True, 
                                capture_output=capture_output, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = f"Error: Command failed: {cmd}\n"
        if e.stderr:
            error_msg += f"Stderr: {e.stderr}"
        raise RuntimeError(error_msg)

def process_repo(repo_url, target_branch, public_dir, mp_id, message, dry_run, worker_id):
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    
    if repo_url.startswith('/'):
        # Local absolute path (e.g., for testing)
        pass
    elif 'github.com' not in repo_url:
        repo_url = f"https://github.com/{repo_url}.git"
    elif not repo_url.endswith('.git'):
        repo_url = f"{repo_url}.git"
        
    tmp_repo_dir = os.path.join(BASE_TMP_DIR, f"worker_{worker_id}_{repo_name}")
    
    try:
        # 1. Setup Repo Space
        if os.path.exists(tmp_repo_dir):
            shutil.rmtree(tmp_repo_dir)
            
        run_cmd(f"git clone {repo_url} {tmp_repo_dir}")
        
        # Switch to assignment branch (prefix/mpX)
        run_command(f"git checkout {target_branch}", cwd=tmp_repo_dir)

        # 2. Sync Files (Public assets only)
        changed = False
        for root, dirs, files in os.walk(public_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, public_dir)
                
                dst_path = os.path.join(tmp_repo_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                
                if os.path.exists(dst_path):
                    with open(src_path, "rb") as fsrc, open(dst_path, "rb") as fdst:
                        if fsrc.read() == fdst.read():
                            continue
                
                shutil.copy2(src_path, dst_path)
                changed = True

        if not changed:
            return True, repo_url, "No changes needed (Already up-to-date)."

        # 3. Commit and Verification
        full_message = f"docs({mp_id}): {message}\n\nBroadcast-Source: {mp_id}/public\nTimestamp: {datetime.now().isoformat()}"
        run_cmd("git add .", cwd=tmp_repo_dir)
        run_cmd(f"git commit -m \"{full_message}\" --no-verify", cwd=tmp_repo_dir)
        
        if dry_run:
            return True, repo_url, f"Local commit created in {tmp_repo_dir} (Dry-run)."

        # Push to remote
        run_cmd(f"git push origin {target_branch}", cwd=tmp_repo_dir)
        
        # Cleanup on success if not dry run
        shutil.rmtree(tmp_repo_dir, ignore_errors=True)
        return True, repo_url, "Successfully pushed updates."

    except Exception as e:
        return False, repo_url, str(e)

def main():
    parser = argparse.ArgumentParser(
        description="Broadcast specific updates (Hot-Sync) to student template repositories.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--mp", required=True)
    parser.add_argument("--message", required=True)
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="Target URL of a single repository")
    group.add_argument("--repos-list", help="Path to JSON file containing array of repository URLs")
    
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prefix", default="ntuos2026", help="Course prefix for branch")
    
    args = parser.parse_args()

    public_dir = os.path.join(GRADING_ROOT, args.mp, "public")
    if not os.path.exists(public_dir):
        print(f"Error: Public assets directory not found: {public_dir}")
        sys.exit(1)

    repos = []
    if args.repo:
        repos = [args.repo]
    elif args.repos_list:
        try:
            with open(args.repos_list, 'r') as f:
                repos = json.load(f)
            if not isinstance(repos, list):
                raise ValueError("JSON file must contain a list of repositories")
        except Exception as e:
            print(f"Error reading repos-list: {e}")
            sys.exit(1)

    print(f"[*] [HOT-SYNC BROADCAST] Starting for {args.mp}...")
    print(f"[*] Total Targets: {len(repos)} repo(s)")
    if args.dry_run:
        print("[*] MODE: DRY-RUN (Changes will be committed locally, but NOT pushed)")
    
    os.makedirs(BASE_TMP_DIR, exist_ok=True)
    target_branch = f"{args.prefix}/{args.mp}"
    
    results = {"success": [], "failed": [], "skipped": []}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_repo = {
            executor.submit(process_repo, repo, target_branch, public_dir, args.mp, args.message, args.dry_run, i): repo 
            for i, repo in enumerate(repos)
        }
        
        for future in concurrent.futures.as_completed(future_to_repo):
            success, repo_url, msg = future.result()
            
            if success:
                if "up-to-date" in msg:
                    safe_print(f"[-] SKIPPED: {repo_url} - {msg}")
                    results["skipped"].append(repo_url)
                else:
                    safe_print(f"[+] SUCCESS: {repo_url} - {msg}")
                    results["success"].append(repo_url)
            else:
                safe_print(f"[x] FAILED : {repo_url} - {msg}")
                results["failed"].append(repo_url)
                
    # Summary
    print("\n" + "="*50)
    print("📈 BROADCAST SUMMARY")
    print("="*50)
    print(f"Total Repositories : {len(repos)}")
    print(f"✅ Successfully Pushed: {len(results['success'])}")
    print(f"⏭️  Skipped (No diff) : {len(results['skipped'])}")
    print(f"❌ Failed             : {len(results['failed'])}")
    
    if len(results['failed']) > 0:
        print("\nFailed Repositories Details:")
        for r in results['failed']:
            print(f"  - {r}")
        sys.exit(1)
        
    if args.dry_run:
        print("\n[DRY-RUN COMPLETE] Check temporary directories in:")
        print(f"  {BASE_TMP_DIR}")
    else:
        # Cleanup base tmp completely on sweeping success
        shutil.rmtree(BASE_TMP_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()
