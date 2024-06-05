import os
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from tabulate import tabulate
from colorist import Color
import argparse
import math
from datetime import datetime, timedelta
from uniplot import plot
import numpy as np

metrics_github_repo = "https://github.com/dotnet/roslyn-analyzers.git"
homedir = os.path.expanduser("~")
internal_stuff_path = os.path.join(homedir, ".metrics_scratch")
cloned_repos = os.path.join(internal_stuff_path, "repos")
metrics_exe = os.path.join(internal_stuff_path, "roslyn-analyzers", "artifacts", "bin", "Metrics", "Release", "net472", "Metrics.exe")
main_path = os.getcwd()
remote_url = ""
shadow_repo_path = ""
verbose = False

GITIGNORED_FILES_THAT_AFFECT_THE_BUILD = []

def internal_setup(args):
    global shadow_repo_path, remote_url, verbose

    verbose = args.verbose
    remote_url = subprocess.run(["git", "remote", "get-url", args.origin], capture_output=True, check=True).stdout.decode("utf-8").replace("\n", "")
    repo_name = remote_url.split("/")[-1]
    shadow_repo_path = os.path.join(cloned_repos, repo_name)

    install_metrics_tool()

    if not os.path.isdir(cloned_repos):
        os.mkdir(cloned_repos)
    
    update_shadow_repo(args.force_update, args.main_branch)

def main():
    parser = argparse.ArgumentParser(description="CodeMetrics CLI helper for dotnet projects")
    parser.add_argument('-p', '--project', help="Project to analyze")
    parser.add_argument('-s', '--solution', help="Solution to analyze")
    parser.add_argument('-n', '--namespace', help="Show metrics for all types within a namespace")
    parser.add_argument('-c', '--commit', help="git commit hash to use for metrics")
    parser.add_argument('-dc', '--diff_commits', help="fromHash:untilHash, compare metrics at these two states of the repo")
    parser.add_argument('-dd', '--diff_dates', help="fromDate:untilDate, compare metrics at these two points in time")
    parser.add_argument('-st', '--step_days', help="When running diff_dates, take measurements at a specified day interval")
    parser.add_argument('-pl', '--plot', help="Plot results of diffing over time. Specify which metric to plot")
    parser.add_argument('-b', '--baseline', help="git commit hash to set as a baseline for metrics comparisons")
    parser.add_argument('-o', '--origin', default="origin", help="Name of upstream git remote")
    parser.add_argument('-f', '--force_update', action='store_true', help="Update shadow repo and always recalculate metrics regarding of cache state")
    parser.add_argument('-m', '--main_branch', default="master", help="Name of the main integration branch")
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help="Print out in detail of what's going on")
    args = parser.parse_args()

    internal_setup(args)
    
    if args.diff_dates is not None or args.diff_commits is not None or args.baseline is not None or args.commit is not None:
        code_path = shadow_repo_path
    else:
        code_path = main_path
    
    if args.solution is not None:
        is_solution = True
        target = (is_solution, os.path.join(code_path, args.solution))
    elif args.project is not None:
        is_solution = False
        target = (is_solution, os.path.join(code_path, args.project))
    else:
        parser.print_usage()
        exit(1)

    if args.commit is not None:
        metrics_xml = gather_metrics(target, args.force_update, args.commit)
        headers, rows = process_metrics(metrics_xml, is_solution, args.namespace)
        print_metrics(headers, rows)

    elif args.diff_dates is not None and args.step_days is None:
        dates = args.diff_dates.split(":")
        date_from, date_until = dates[0], dates[1]
        hash_before = run_cmd(["git", "log", f"--until={date_from}", "-n", "1", "--format=oneline"], capture_output=True).stdout.decode("utf-8").split(" ")[0]
        hash_after = run_cmd(["git", "log", f"--until={date_until}", "-n", "1", "--format=oneline"], capture_output=True).stdout.decode("utf-8").split(" ")[0]
        print(f"{Color.GREEN}Diff between {date_from} and {date_until}{Color.OFF}")
        print(f"{Color.GREEN}Dates resolved to commit range {hash_before}..{hash_after}{Color.OFF}")
        do_diff(target, args, is_solution, hash_before, hash_after)
    
    elif args.diff_dates is not None and args.step_days is not None:
        dates = args.diff_dates.split(":")
        date_from = datetime.strptime(dates[0], "%Y-%m-%d")
        date_until = datetime.strptime(dates[1], "%Y-%m-%d")
        step = args.step_days
        
        plot_rows = []
        calc_date = date_until
        check_dates = []
        while calc_date >= date_from:
            check_dates.append(calc_date.strftime("%Y-%m-%d"))
            calc_date = calc_date - timedelta(days=int(step))
        
        for check_date in check_dates:
            check_hash = run_cmd(["git", "log", f"--until={check_date}", "-n", "1", "--format=oneline"], capture_output=True).stdout.decode("utf-8").split(" ")[0]
            check_xml = gather_metrics(target, args.force_update, check_hash)
            headers, rows = process_metrics(check_xml, is_solution, args.namespace)
            total_row = rows[-1:]
            total_row[0][0] = check_date
            plot_rows.extend(total_row)
            
        headers[0] = f"{Color.MAGENTA}Date{Color.OFF}"
        print_metrics(headers, plot_rows)
        
        if args.plot is not None:
            a = np.array(plot_rows)
            t = np.transpose(a)
            
            if args.plot == "all":
                metrics = ["MaintainabilityIndex", "CyclomaticComplexity", "ClassCoupling", "DepthOfInheritance", "SourceLines", "ExecutableLines"]
            else:
                metrics = args.plot.split(",")

            for metric in metrics:
                if metric == "MaintainabilityIndex":
                    di = 1
                elif metric == "CyclomaticComplexity":
                    di = 2
                elif metric == "ClassCoupling":
                    di = 3
                elif metric == "DepthOfInheritance":
                    di = 4
                elif metric == "SourceLines":
                    di = 5
                elif metric == "ExecutableLines":
                    di = 6
                
                print()
                plot(xs=[t[0]], ys=[t[di]], lines=True, title=metric)
                print()
    
    elif args.diff_commits is not None:
        hashes = args.diff_commits.split(":")
        hash_before, hash_after = hashes[0], hashes[1]
        do_diff(target, args, is_solution, hash_before, hash_after)
        
    elif args.baseline is not None:
        baseline_xml = gather_metrics(target, args.force_update, args.baseline)
        headers_0, rows_0 = process_metrics(baseline_xml, is_solution, args.namespace)

        current_xml = gather_metrics(target, args.force_update, None)
        headers_1, rows_1 = process_metrics(current_xml, is_solution, args.namespace)
        
        headers, rows = diff_metrics(headers_0, rows_0, headers_1, rows_1)
        print_metrics(headers, rows)

    else:
        metrics_xml = gather_metrics(target, args.force_update, None)
        headers, rows = process_metrics(metrics_xml, is_solution, args.namespace)
        print_metrics(headers, rows)

def do_diff(target, args, is_solution, hash_before, hash_after):
    before_xml = gather_metrics(target, args.force_update, hash_before)
    headers_0, rows_0 = process_metrics(before_xml, is_solution, args.namespace)

    after_xml = gather_metrics(target, args.force_update, hash_after)
    headers_1, rows_1 = process_metrics(after_xml, is_solution, args.namespace)
    
    headers, rows = diff_metrics(headers_0, rows_0, headers_1, rows_1)
    print_metrics(headers, rows)
    
def gather_metrics(target, force_update, commit_hash):
    is_solution, target_path = target
    if is_solution:
        metrics_cmd = "s"
    else:
        metrics_cmd = "p"

    if commit_hash is not None:
        chdir(shadow_repo_path)
        run_cmd(["git", "checkout", commit_hash])
    else:
        chdir(main_path)

    repo_hash = current_repo_hash(target)
    metrics_out = os.path.join(internal_stuff_path, f"{repo_hash}.xml")
    if force_update or not os.path.isfile(metrics_out):
        run_cmd([metrics_exe, f"/{metrics_cmd}:{target_path}", f"/o:{metrics_out}"], check=True)
    
    return metrics_out

def process_metrics(metrics_xml, is_solution, namespace_filter):
    tree = ET.parse(metrics_xml)
    root = tree.getroot()

    # ugh this is horrible and solution part doesn't work
    if not is_solution:
        target_root = root[0][0][0][1]
        if namespace_filter is None:
            headers, rows = parse_metrics_from_root(target_root)
        else:
            for ns in target_root:
                if ns.get('Name') != namespace_filter:
                    continue
                headers, rows = parse_metrics_from_root(ns.find('Types'))
        
        total_row = get_total_row(rows)
        rows.append(total_row)
        return headers, rows

    else:
        headers = []
        all_rows = []

        for project in root[0]:
            target_root = project
            if namespace_filter is None:
                headers, rows = parse_metrics_from_root(target_root)
            else:
                for ns in target_root:
                    if ns.get('Name') != namespace_filter:
                        continue
                    headers, rows = parse_metrics_from_root(ns.find('Types'))
            all_rows.extend(rows)

        total_row = get_total_row(all_rows)
        all_rows.append(total_row)
        return headers, all_rows


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
                    set_color = True
                    if m == "MaintainabilityIndex":
                        if rounded > 0:
                            color = Color.GREEN
                        elif rounded < 0:
                            color = Color.RED
                        else:
                            set_color = False
                    else:
                        if rounded > 0:
                            color = Color.RED
                        elif rounded < 0:
                            color = Color.GREEN
                        else:
                            set_color = False
                    if set_color:
                        delta_row.append(f"{color}{rounded}%{Color.OFF}")
                    else:
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
    
    return (headers, rows)

def get_total_row(rows):
    total_row = [f"{Color.MAGENTA}Total{Color.OFF}"]
    for row in rows:
        for i, v in enumerate(row[1:]):
            try:
                total_row[i+1] = total_row[i+1] + v
            except IndexError:
                total_row.append(v)
    
    # first column is maintainability index, we take an average of that instead of a sum
    # to match what CodeAnalysis.Metrics package does when aggregating.
    total_row[1] = math.ceil((total_row[1]) / len(rows) * 100) / 100
                
    return total_row

def update_shadow_repo(update, main_branch):
    if os.path.isdir(shadow_repo_path):
        if update:
            print("Updating shadow repo...")
            chdir(shadow_repo_path)
            run_cmd(["git", "checkout", main_branch])
            run_cmd(["git", "pull"])
            chdir(main_path)
    else:
        print("Cloning shadow repo...")
        chdir(cloned_repos)
        run_cmd(["git", "clone", remote_url])
        chdir(main_path)

def install_metrics_tool():
    if os.path.isfile(metrics_exe):
        return
    
    print(f"Metrics.exe not found in {metrics_exe}, installing...")
    
    run_cmd(["winget", "install", "Microsoft.DotNet.SDK.Preview"])

    if not os.path.isdir(internal_stuff_path):
        os.mkdir(internal_stuff_path)

    chdir(internal_stuff_path)
    run_cmd(["git", "clone", metrics_github_repo])
    chdir("roslyn-analyzers")
    run_cmd(["Restore.cmd"])
    chdir("src\Tools\Metrics")
    run_cmd(["msbuild", "/m", "/v:m", "/p:Configuration=Release", "Metrics.csproj"])
    chdir(main_path)

def current_repo_hash(target):
    is_solution, target_path = target
    if is_solution:
        target_path = f"s{target_path}"
    else:
        target_path = f"p{target_path}"

    # Calculate a hash reflecting the current state of the repo.
    contents_hash = hashlib.sha256()

    contents_hash.update(str.encode(target_path))

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
    
    hash = contents_hash.hexdigest()
    if verbose:
        print(f"Current hash: {hash}")

    return hash

def chdir(path):
    if verbose:
        print(f"chdir {path}")

    os.chdir(path)

def run_cmd(*args, **kwargs):
    if verbose:
        print(f"Running cmd: {args}")
    
    return subprocess.run(*args, **kwargs)

def run_cmd_checked(*args, **kwargs):
    """Run a command, throwing an exception if it exits with non-zero status."""
    kwargs["check"] = True

    if verbose:
        print(f"Running cmd: {args}")

    return subprocess.run(*args, **kwargs)

if __name__ == "__main__":
    main()
