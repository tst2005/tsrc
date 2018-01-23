""" Entry point for tsrc log """

import sys

import ui

import tsrc.cli
import tsrc.git


def main(args):
    workspace = tsrc.cli.get_workspace(args)
    workspace.load_manifest()
    all_ok = True
    repos = workspace.get_repos()
    for repo in repos:
        repo_path = workspace.joinpath(repo.src)
        colors = ["green", "reset", "yellow", "reset", "bold blue", "reset"]
        log_format = "%m {}%h{} - {}%d{} %s {}<%an>{}"
        log_format = log_format.format(*("%C({})".format(x) for x in colors))
        cmd = ["log",
               "--color=always",
               "--pretty=format:%s" % log_format,
               "%s...%s" % (args.from_, args.to)]
        rc, out = tsrc.git.run_git(repo_path, *cmd, raises=False)
        if rc != 0:
            all_ok = False
        if out:
            ui.info(ui.bold, repo.src)
            ui.info(ui.bold, "-" * len(repo.src))
            ui.info(out)
    if not all_ok:
        sys.exit(1)
