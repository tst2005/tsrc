import argparse
import copy
from typing import Any, List

from path import Path
import mock

import pytest

import tsrc.git
from tsrc.gitlab import GitLabHelper
import tsrc.gitlab
from tsrc.test.helpers.cli import CLI
from tsrc.cli.push import RepositoryInfo
from tsrc.cli.push_gitlab import PushAction


GITLAB_URL = "http://gitlab.example.com"
TIMOTHEE = {"name": "timothee", "id": 1}
THEO = {"name": "theo", "id": 2}
JOHN = {"name": "john", "id": 3}
BART = {"name": "bart", "id": 4}

MR_STUB = {
    "id": "3978",
    "iid": "42",
    "web_url": "http://mr/42",
    "title": "Boring title",
    "target_branch": "master"
}

PROJECT_IDS = {
    "owner/project": "42"
}


@pytest.fixture
def gitlab_mock() -> Any:
    # FIXME: a type that contains GitLabHelper plus other methods ?
    all_users = [JOHN, BART, TIMOTHEE, THEO]

    def get_project_members(project_id: str, query: str) -> List[str]:
        assert project_id in PROJECT_IDS.values()
        return [user for user in all_users if query in user["name"]]  # type: ignore

    def get_group_members(group_name: str, query: str) -> List[str]:
        return [user for user in all_users if query in user["name"]]  # type: ignore

    gl_mock = mock.create_autospec(tsrc.gitlab.GitLabHelper, instance=True)
    gl_mock.get_project_members = get_project_members
    gl_mock.get_group_members = get_group_members
    gl_mock.get_project_id = lambda x: PROJECT_IDS[x]
    # Define a few helper methods to make tests nicer to read:
    new_defs = {
        "assert_mr_created": gl_mock.create_merge_request.assert_called_with,
        "assert_mr_not_created": gl_mock.create_merge_request.assert_not_called,
        "assert_mr_updated": gl_mock.update_merge_request.assert_called_with,
        "assert_mr_accepted": gl_mock.accept_merge_request.assert_called_with,
    }
    for name, func in new_defs.items():
        setattr(gl_mock, name, func)
    return gl_mock


def execute_push(repo_path: Path, push_args: argparse.Namespace,
                 gitlab_mock: GitLabHelper) -> None:
    repository_info = RepositoryInfo()
    repository_info.read_working_path(repo_path)
    push_action = PushAction(repository_info, push_args, gl_helper=gitlab_mock)
    push_action.execute()


def test_creating_merge_request_explicit_target_branch(
        repo_path: Path, tsrc_cli: CLI, gitlab_mock: Any, push_args: argparse.Namespace) -> None:
    tsrc.git.run_git(repo_path, "checkout", "-b", "new-feature")
    tsrc.git.run_git(repo_path, "commit", "--message", "new feature", "--allow-empty")

    gitlab_mock.find_opened_merge_request.return_value = []
    gitlab_mock.create_merge_request.return_value = MR_STUB

    push_args.assignee = "john"
    push_args.target_branch = "next"
    push_args.title = "Best feature ever"

    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_created(
        "42", "new-feature",
        target_branch="next",
        title="new-feature"
    )
    gitlab_mock.assert_mr_updated(
        MR_STUB,
        assignee_id=JOHN["id"],
        remove_source_branch=True,
        target_branch="next",
        title="Best feature ever"
    )


def test_creating_merge_request_uses_default_branch(
        repo_path: Path, tsrc_cli: CLI, gitlab_mock: Any, push_args: argparse.Namespace) -> None:
    gitlab_mock.get_default_branch.return_value = "devel"
    tsrc.git.run_git(repo_path, "checkout", "-b", "new-feature")
    tsrc.git.run_git(repo_path, "commit", "--message", "new feature", "--allow-empty")

    gitlab_mock.find_opened_merge_request.return_value = []
    gitlab_mock.create_merge_request.return_value = MR_STUB

    push_args.assignee = "john"

    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_created(
        "42", "new-feature",
        target_branch="devel",
        title="new-feature"
    )


def test_existing_merge_request(repo_path: Path, tsrc_cli: CLI, gitlab_mock:
                                Any, push_args: argparse.Namespace) -> None:
    tsrc.git.run_git(repo_path, "checkout", "-b", "new-feature")
    tsrc.git.run_git(repo_path, "commit", "--message", "new feature", "--allow-empty")

    gitlab_mock.find_opened_merge_request.return_value = MR_STUB

    push_args.target_branch = "next"
    push_args.title = "Best feature ever"
    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_not_created()
    gitlab_mock.assert_mr_updated(
        MR_STUB,
        remove_source_branch=True,
        target_branch="next",
        title="Best feature ever"
    )


def test_close_merge_request(repo_path: Path, tsrc_cli: CLI,
                             gitlab_mock: Any, push_args: argparse.Namespace) -> None:
    tsrc.git.run_git(repo_path, "checkout", "-b", "new-feature")
    tsrc.git.run_git(repo_path, "commit", "--message", "new feature", "--allow-empty")

    gitlab_mock.find_opened_merge_request.return_value = MR_STUB

    push_args.close = True
    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_updated(
        MR_STUB,
        state_event="close"
    )


def test_do_not_change_mr_target(repo_path: Path, tsrc_cli: CLI,
                                 gitlab_mock: Any, push_args: argparse.Namespace) -> None:
    mr_stub = copy.copy(MR_STUB)
    mr_stub["target_branch"] = "release/1.6.0"
    gitlab_mock.find_opened_merge_request.return_value = mr_stub

    execute_push(repo_path, push_args, gitlab_mock)
    gitlab_mock.assert_mr_updated(
        mr_stub,
        remove_source_branch=True,
        title="Boring title",
    )


def test_accept_merge_request(repo_path: Path, tsrc_cli: CLI,
                              gitlab_mock: Any, push_args: argparse.Namespace) -> None:
    tsrc.git.run_git(repo_path, "checkout", "-b", "new-feature")
    tsrc.git.run_git(repo_path, "commit", "--message", "new feature", "--allow-empty")

    gitlab_mock.find_opened_merge_request.return_value = MR_STUB

    push_args.accept = True
    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_accepted(MR_STUB)


def test_unwipify_existing_merge_request(repo_path: Path, tsrc_cli: CLI,
                                         gitlab_mock: Any,
                                         push_args: argparse.Namespace) -> None:
    existing_mr = {
        "title": "WIP: nice title",
        "web_url": "http://example.com/42",
        "iid": "42",
    }
    gitlab_mock.find_opened_merge_request.return_value = existing_mr

    push_args.ready = True
    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_not_created()
    gitlab_mock.assert_mr_updated(
        existing_mr,
        remove_source_branch=True,
        title="nice title"
    )


def test_wipify_existing_merge_request(repo_path: Path, tsrc_cli: CLI,
                                       gitlab_mock: Any,
                                       push_args: argparse.Namespace) -> None:
    existing_mr = {
        "title": "not ready",
        "web_url": "http://example.com/42",
        "iid": "42",
    }
    gitlab_mock.find_opened_merge_request.return_value = existing_mr

    push_args.wip = True
    execute_push(repo_path, push_args, gitlab_mock)

    gitlab_mock.assert_mr_not_created()
    gitlab_mock.assert_mr_updated(
        existing_mr,
        remove_source_branch=True,
        title="WIP: not ready"
    )
