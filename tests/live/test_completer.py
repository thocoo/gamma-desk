import pytest

from gdesk.live.completer import Completer


@pytest.fixture
def completer():
    # Set up some objects to auto-complete.
    without_dir = ClassWithoutDir(a=10, b=20)
    with_super_dir = ClassWithSuperDir(a=10, b=20)
    with_dir = ClassWithCustomDir(a=10, b=20)
    with_dir_and_hide_class = ClassWithCustomDirAndHiddenClassAttributes(a=10, b=20)

    # Return a completer.
    completer = Completer(namespace=locals())
    return completer


class ParentClass:

    # Expose a class-level constant.
    CLASS_LEVEL_CONSTANT = 100

    def __init__(self, **kwargs):
        # Set an attribute at the class level.
        self.class_level_attribute = "value"

        # Set attributes at the instance level.
        for name, value in kwargs.items():
            setattr(self, name, value)


class ClassWithoutDir(ParentClass):
    """Normal class, inheriting from ParentClass."""


class ClassWithSuperDir(ParentClass):
    """Override __dir__ but simply call parent's __dir__."""

    def __dir__(self):
        return super().__dir__()


class ClassWithCustomDir(ParentClass):
    """Provide custom __dir__ to limit exposure of instance-level attributes."""

    def __dir__(self):
        # Hide attribute 'b'.
        return ["a"]


class ClassWithCustomDirAndHiddenClassAttributes(ParentClass):
    """Provide custom __dir__ *and* configure 'hide class attributes' OFF."""

    _AUTO_COMPLETE_HIDE_CLASS_ATTRIBUTES = True

    def __dir__(self):
        # Hide attribute 'b'.
        return ["a"]


def _get_all_completions(completer, text):
    """Return all possible completions in a list."""
    completions = []

    for i in range(100):
        completion = completer.complete(text, i)
        if completion is None:
            break

        completions.append(completion)

    return completions


def test_completer_on_object_without_dir_returns_all_attributes(completer):
    completed_attributes = _get_all_completions(completer, "without_dir.")
    assert set(completed_attributes) == set([
        "without_dir.CLASS_LEVEL_CONSTANT",
        "without_dir.a",
        "without_dir.b",
        "without_dir.class_level_attribute"
    ])


def test_completer_on_object_with_super_dir_returns_all_attributes(completer):
    completed_attributes = _get_all_completions(completer, "with_super_dir.")
    assert set(completed_attributes) == set([
        "with_super_dir.CLASS_LEVEL_CONSTANT",
        "with_super_dir.a",
        "with_super_dir.b",
        "with_super_dir.class_level_attribute"
    ])


def test_completer_on_object_with_custom_dir_returns_dir_attributes_plus_class_level_constants(completer):
    completed_attributes = _get_all_completions(completer, "with_dir.")
    assert set(completed_attributes) == set([
        "with_dir.CLASS_LEVEL_CONSTANT",
        "with_dir.a",
    ])


def test_completer_on_object_with_custom_dir_and_hidden_class_level_attributes_returns_only_dir_attributes(completer):
    completed_attributes = _get_all_completions(completer, "with_dir_and_hide_class.")
    assert set(completed_attributes) == set([
        "with_dir_and_hide_class.a",
    ])
