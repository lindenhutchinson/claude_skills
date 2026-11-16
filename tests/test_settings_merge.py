from settings_merge import merge

MACHINE = {"model": "opus", "permissions": {"allow": ["Bash(ls)"]}, "enabledPlugins": {"a@b": True}}


def test_first_merge_adds_without_dropping_machine_state():
    fragment = {"attribution": False, "permissions": {"allow": ["Bash(git status)"]}}
    merged = merge(MACHINE, fragment)
    assert merged["attribution"] is False
    assert merged["permissions"]["allow"] == ["Bash(ls)", "Bash(git status)"]
    assert merged["model"] == "opus" and merged["enabledPlugins"] == {"a@b": True}


def test_merge_does_not_mutate_its_input():
    before = repr(MACHINE)
    merge(MACHINE, {"permissions": {"allow": ["x"]}})
    assert repr(MACHINE) == before


def test_rerun_is_idempotent():
    fragment = {"attribution": False, "permissions": {"allow": ["Bash(git status)"]}}
    once = merge(MACHINE, fragment)
    assert merge(once, fragment, fragment) == once


def test_entries_removed_from_the_repo_are_retracted():
    old = {"attribution": False, "permissions": {"allow": ["Bash(a)", "Bash(b)"]}}
    new = {"permissions": {"allow": ["Bash(b)"]}}
    machine = merge(MACHINE, old)
    merged = merge(machine, new, old)
    assert "attribution" not in merged
    assert merged["permissions"]["allow"] == ["Bash(ls)", "Bash(b)"]


def test_retraction_keeps_what_the_machine_changed_since():
    old = {"effortLevel": "high"}
    machine = {**merge(MACHINE, old), "effortLevel": "low"}  # changed with /config after the merge
    assert merge(machine, {}, old)["effortLevel"] == "low"


def test_retraction_drops_containers_it_emptied():
    old = {"hooks": {"Stop": ["x"]}}
    assert "hooks" not in merge(merge({}, old), {}, old)


def test_repo_scalars_win():
    assert merge({"attribution": True}, {"attribution": False})["attribution"] is False
