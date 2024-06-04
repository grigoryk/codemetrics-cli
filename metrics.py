import os
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from tabulate import tabulate
from colorist import Color
import argparse
import math

metrics_github_repo = "https://github.com/dotnet/roslyn-analyzers.git"
homedir = os.path.expanduser("~")
internal_stuff_path = f"{homedir}/.metrics_scratch"
cloned_repos = f"{internal_stuff_path}/repos"
metrics_path = f"{internal_stuff_path}/roslyn-analyzers/artifacts/bin/Metrics/Release/net472/Metrics.exe"
main_path = os.path.dirname(os.path.realpath(__file__))
remote_url = ""
shadow_repo_path = ""

GITIGNORED_FILES_THAT_AFFECT_THE_BUILD = []

def internal_setup(args):
    global shadow_repo_path, remote_url

    remote_url = subprocess.run(["git", "remote", "get-url", args.origin], capture_output=True, check=True).stdout.decode("utf-8").replace("\n", "")
    repo_name = remote_url.split("/")[-1]
    shadow_repo_path = f"{cloned_repos}/{repo_name}"

    install_metrics_tool()

    if not os.path.isdir(cloned_repos):
        os.mkdir(cloned_repos)
    
    update_shadow_repo(args.update_shadow, args.main_branch)

def main():
    parser = argparse.ArgumentParser(description="CodeMetrics CLI helper for dotnet projects")
    parser.add_argument('-p', '--project', help="Which project to generate metrics for", required=True)
    parser.add_argument('-n', '--namespace', help="Show metrics for all types within a namespace")
    parser.add_argument('-c', '--commit', help="git commit hash to use for metrics")
    parser.add_argument('-b', '--baseline', help="git commit hash to set as a baseline for metrics comparisons")
    parser.add_argument('-o', '--origin', default="origin", help="Name of upstream git remote")
    parser.add_argument('-u', '--update_shadow', action='store_true', help="Update shadow repo used for comparisons and historical analysis")
    parser.add_argument('-m', '--main_branch', default="master", help="Name of the main integration branch")
    args = parser.parse_args()

    internal_setup(args)

    if args.commit is not None:
        metrics_xml = calculate_metrics(args.project, args.commit)
        headers, rows = gather_metrics(metrics_xml, args.namespace)
        print_metrics(headers, rows)
        
    elif args.baseline is not None:
        current_xml = calculate_metrics(args.project, None)
        headers_1, rows_1 = gather_metrics(current_xml, args.namespace)

        baseline_xml = calculate_metrics(args.project, args.baseline)
        headers_0, rows_0 = gather_metrics(baseline_xml, args.namespace)
        
        headers, rows = diff_metrics(headers_0, rows_0, headers_1, rows_1)
        print_metrics(headers, rows)

    else:
        metrics_xml = calculate_metrics(args.project, None)
        headers, rows = gather_metrics(metrics_xml, args.namespace)
        print_metrics(headers, rows)
    
def calculate_metrics(project_path, commit_hash):
    if commit_hash is not None:
        print("chdir", shadow_repo_path)
        os.chdir(shadow_repo_path)
        subprocess.run(["git", "checkout", commit_hash])
    else:
        os.chdir(main_path)

    repo_hash = current_repo_hash(project_path)
    print(f"current repo hash: {repo_hash}")

    metrics_out = f"{internal_stuff_path}/{repo_hash}.xml"
    if not os.path.isfile(metrics_out):
        print([metrics_path, f"/p:{project_path}", f"/o:{metrics_out}"])
        subprocess.run([metrics_path, f"/p:{project_path}", f"/o:{metrics_out}"], check=True)
        print("ran metrics")
    
    return metrics_out

def gather_metrics(metrics_xml, namespace_filter):
    tree = ET.parse(metrics_xml)
    root = tree.getroot()

    # for all namespaces...
    namespace_root = root[0][0][0][1]
    if namespace_filter is None:
        headers, rows = parse_metrics_from_root(namespace_root)
    else:
        for ns in namespace_root:
            if ns.get('Name') != namespace_filter:
                continue
            headers, rows = parse_metrics_from_root(ns.find('Types'))
    return headers, rows

def diff_metrics(headers_0, rows_0, headers_1, rows_1):
    if headers_0 != headers_1:
        raise SystemExit("Metric dimensions do not match")
    metric_count = len(headers_0) - 1 # -1 to account for 'Namespace' being part of headers, while it's not a metric
    
    delta = []
    metrics_0 = {}
    metrics_1 = {}
    for row in rows_0:
        metrics_0[row[0]] = row[1:]

    for row in rows_1:
        metrics_1[row[0]] = row[1:]
    
    for m in metrics_1.keys():
        delta_row = [m]
        if m in metrics_0:
            for i in range(metric_count):
                if float(metrics_0[m][i]) == 0:
                    delta_row.append("∞")
                else:
                    perc_delta = 100 * (float(metrics_1[m][i]) - float(metrics_0[m][i])) / float(metrics_0[m][i])
                    rounded = math.ceil(perc_delta * 100) / 100
                    delta_row.append(f"{rounded}%")
        else:
            for i in range(metric_count):
                delta_row.append("∞")
        delta.append(delta_row)
    
    return headers_0, delta

def print_metrics(headers, rows):
    print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))

def parse_metrics_from_root(metrics_root):
    rows = []
    headers = [f"{Color.MAGENTA}Namespace{Color.OFF}"]
    for obj in metrics_root:
        row = []
        row.append(f"{Color.CYAN}{obj.get('Name')}{Color.OFF}")
        for child in obj.find('Metrics'):
            colored_header = f"{Color.MAGENTA}{child.get('Name')}{Color.OFF}"
            if colored_header not in headers:
                headers.append(colored_header)
            row.append(float(child.get('Value')))
        rows.append(row)
    
    total_row = [f"{Color.MAGENTA}Total{Color.OFF}"]
    for row in rows:
        for i, v in enumerate(row[1:]):
            try:
                total_row[i+1] = total_row[i+1] + v
            except IndexError:
                total_row.append(v)
                
    rows.append(total_row)
    return (headers, rows)

def update_shadow_repo(update, main_branch):
    if os.path.isdir(shadow_repo_path):
        if update:
            print("Updating shadow repo...")
            os.chdir(shadow_repo_path)
            subprocess.run(["git", "checkout", main_branch])
            subprocess.run(["git", "pull"])
            os.chdir(main_path)
    else:
        print("Cloning shadow repo...")
        os.chdir(cloned_repos)
        subprocess.run(["git", "clone", remote_url])
        os.chdir(main_path)

def install_metrics_tool():
    if os.path.isfile(metrics_path):
        return
    
    print(f"Metrics.exe not found in {metrics_path}, installing...")
    
    subprocess.run(["winget", "install", "Microsoft.DotNet.SDK.Preview"])

    if not os.path.isdir(internal_stuff_path):
        os.mkdir(internal_stuff_path)

    os.chdir(internal_stuff_path)
    subprocess.run(["git", "clone", metrics_github_repo])
    os.chdir("roslyn-analyzers")
    subprocess.run(["Restore.cmd"])
    os.chdir("src\Tools\Metrics")
    subprocess.run(["msbuild", "/m", "/v:m", "/p:Configuration=Release", "Metrics.csproj"])
    os.chdir(main_path)

def current_repo_hash(project):
    # Calculate a hash reflecting the current state of the repo.
    contents_hash = hashlib.sha256()

    contents_hash.update(str.encode(project))

    contents_hash.update(
        run_cmd_checked(["git", "rev-parse", "HEAD"], capture_output=True).stdout
    )
    contents_hash.update(b"\x00")

    # Git can efficiently tell us about changes to tracked files, including
    # the diff of their contents, if you give it enough "-v"s.

    changes = run_cmd_checked(["git", "status", "-v", "-v"], capture_output=True).stdout
    contents_hash.update(changes)
    contents_hash.update(b"\x00")

    # But unfortunately it can only tell us the names of untracked
    # files, and it won't tell us anything about files that are in
    # .gitignore but can still affect the build.

    untracked_files = []

    # First, get a list of all untracked files sans standard exclusions.

    # -o is for getting other (i.e. untracked) files
    # --exclude-standard is to handle standard Git exclusions: .git/info/exclude, .gitignore in each directory,
    # and the user's global exclusion file.
    changes_others = run_cmd_checked(["git", "ls-files", "-o", "--exclude-standard"], capture_output=True).stdout
    changes_lines = iter(ln.strip() for ln in changes_others.split(b"\n"))

    try:
        ln = next(changes_lines)
        while ln:
            untracked_files.append(ln)
            ln = next(changes_lines)
    except StopIteration:
        pass

    # Then, account for some excluded files that we care about.
    untracked_files.extend(GITIGNORED_FILES_THAT_AFFECT_THE_BUILD)

    # Finally, get hashes of everything.
    # Skip files that don't exist, e.g. missing GITIGNORED_FILES_THAT_AFFECT_THE_BUILD. `hash-object` errors out if it gets
    # a non-existent file, so we hope that disk won't change between this filter and the cmd run just below.
    filtered_untracked = [nm for nm in untracked_files if os.path.isfile(nm)]
    # Reading contents of the files is quite slow when there are lots of them, so delegate to `git hash-object`.
    git_hash_object_cmd = ["git", "hash-object"]
    git_hash_object_cmd.extend(filtered_untracked)
    changes_untracked = run_cmd_checked(git_hash_object_cmd, capture_output=True).stdout
    contents_hash.update(changes_untracked)
    contents_hash.update(b"\x00")

    return contents_hash.hexdigest()

def run_cmd_checked(*args, **kwargs):
    """Run a command, throwing an exception if it exits with non-zero status."""
    kwargs["check"] = True
    return subprocess.run(*args, **kwargs)

if __name__ == "__main__":
    main()
