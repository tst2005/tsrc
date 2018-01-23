""" Entry point for tsrc sync """

import ui

import tsrc.cli


class BadBranches(tsrc.Error):
    pass


class Syncer(tsrc.executor.Task):
    def __init__(self, workspace):
        self.workspace = workspace
        self.bad_branches = list()

    def description(self):
        return "Synchronize workspace"

    def display_item(self, repo):
        return repo.src

    def process(self, repo):
        ui.info(repo.src)
        repo_path = self.workspace.joinpath(repo.src)
        self.fetch(repo_path)
        ref = None

        if repo.tag:
            ref = repo.tag
        elif repo.sha1:
            ref = repo.sha1

        if ref:
            self.sync_repo_to_ref(repo_path, ref)
        else:
            self.check_branch(repo, repo_path)
            self.sync_repo_to_branch(repo_path)

    def check_branch(self, repo, repo_path):
        current_branch = None
        try:
            current_branch = tsrc.git.get_current_branch(repo_path)
        except tsrc.Error:
            raise tsrc.Error("Not on any branch")

        if current_branch and current_branch != repo.branch:
            self.bad_branches.append((repo.src, current_branch, repo.branch))

    @staticmethod
    def fetch(repo_path):
        try:
            tsrc.git.run_git(repo_path, "fetch", "--tags", "--prune", "origin")
        except tsrc.Error:
            raise tsrc.Error("fetch failed")

    @staticmethod
    def sync_repo_to_ref(repo_path, ref):
        ui.info_2("Resetting to", ref)
        status = tsrc.git.get_status(repo_path)
        if status.dirty:
            raise tsrc.Error("%s dirty, skipping")
        try:
            tsrc.git.run_git(repo_path, "reset", "--hard", ref)
        except tsrc.Error:
            raise tsrc.Error("updating ref failed")

    @staticmethod
    def sync_repo_to_branch(repo_path):
        try:
            tsrc.git.run_git(repo_path, "merge", "--ff-only", "@{u}")
        except tsrc.Error:
            raise tsrc.Error("updating branch failed")

    def display_bad_branches(self):
        if not self.bad_branches:
            return
        ui.error("Some projects were not on the correct branch")
        headers = ("project", "actual", "expected")
        data = [
            ((ui.bold, name), (ui.red, actual), (ui.green, expected)) for
            (name, actual, expected) in self.bad_branches
        ]
        ui.info_table(data, headers=headers)
        raise BadBranches()


def main(args):
    workspace = tsrc.cli.get_workspace(args)
    workspace.update_manifest()
    workspace.load_manifest()
    active_groups = workspace.active_groups
    if active_groups:
        ui.info(ui.green, "*", ui.reset, "Using groups:", ",".join(active_groups))
    repos = workspace.get_repos()
    workspace.clone_missing()
    workspace.set_remotes()
    syncer = Syncer(workspace)
    try:
        tsrc.executor.run_sequence(repos, syncer)
    finally:
        syncer.display_bad_branches()
    workspace.copy_files()
    ui.info("Done", ui.check)
