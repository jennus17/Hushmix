"""Cross-module consistency checks.

The GUI and the controllers talk to each other through ``self.app.<attribute>``
references.  A rename that misses one call site is not a syntax error, so it
only shows up when the user clicks that button.  This script parses the source
without importing (the Windows-only dependencies are not needed) and verifies:

* every ``self.app.X`` / ``app.X`` attribute exists on ``HushmixApp``;
* every method called on a ``ConfigManager`` / ``SettingsManager`` /
  ``VolumeManager`` / ``ButtonActions`` / ``ProfileManager`` instance exists;
* ``ConfigManager.PROFILE_SETTINGS`` covers every field the GUI reads or writes.

Run with::

    python tests/check_consistency.py
"""

import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

#: Attributes HushmixApp assigns in __init__/setup_variables, detected as
#: ``self.<name> = ...`` plus the helper methods it defines.
APP_EXTRA_ATTRIBUTES = {
    "settings_manager",
    "audio_controller",
    "serial_controller",
    "profile_manager",
    "volume_manager",
    "button_actions",
    "gui_components",
    "window_manager",
    "version_manager",
    "deferred_actions",
    "settings_window",
    "buttonSettings_window",
    "help_window",
    "root",
    "accent_color",
    "accent_hover",
    "running",
    "current_apps",
    "volumes",
    "previous_volumes",
    "mute",
    "muted_state",
    "current_mute_state",
    "last_button_states",
}


def read(path):
    with open(path, "r", encoding="utf-8") as stream:
        return stream.read()


def parse(path):
    return ast.parse(read(path), filename=path)


def class_node(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def public_names(class_def):
    """Attribute and method names available on a class."""
    names = set()
    for node in class_def.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "property":
                    names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def assigned_attributes(class_def):
    """``self.X = ...`` assignments inside a class."""
    names = set()
    for node in ast.walk(class_def):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                names.add(target.attr)
    return names


def app_attribute_uses(path):
    """Collect ``self.app.X`` and ``<alias>.X`` uses in a file.

    ``<alias>`` covers the common pattern ``app = self.app`` (and the
    ``app_instance`` parameter name), which is used all over the controllers.

    Returns a list of ``(attribute, lineno)``.
    """
    tree = parse(path)
    uses = []

    def walk(node, aliases):
        """Recurse, threading the "is an alias of self.app" set downwards.

        The aliases must be recomputed at every level so ``app = self.app``
        inside nested functions (``_handle_press``, ``_list`` ...) is seen by
        the statements that follow it.
        """
        aliases = set(aliases)

        # Pass 1: discover aliases assigned directly in this block.
        for child in ast.iter_child_nodes(node):
            targets = []
            value = None
            if isinstance(child, ast.Assign) and len(child.targets) == 1:
                targets = child.targets
                value = child.value
            elif isinstance(child, ast.AnnAssign):
                targets = [child.target]
                value = child.value

            for target in targets:
                if isinstance(target, ast.Name) and value is not None:
                    if (
                        isinstance(value, ast.Attribute)
                        and value.attr == "app"
                        and isinstance(value.value, ast.Name)
                        and value.value.id == "self"
                    ) or (isinstance(value, ast.Name) and value.id in aliases):
                        aliases.add(target.id)
                elif (
                    isinstance(target, ast.Attribute)
                    and target.attr == "app"
                    and isinstance(target.value, ast.Name)
                    and target.value.id in aliases
                ):
                    aliases.add(target.value.id)

        # Pass 2: record attribute uses, then recurse into the children.
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Attribute):
                if (
                    isinstance(child.value, ast.Attribute)
                    and child.value.attr == "app"
                    and isinstance(child.value.value, ast.Name)
                    and child.value.value.id == "self"
                ):
                    uses.append((child.attr, child.lineno))
                elif isinstance(child.value, ast.Name) and child.value.id in aliases:
                    uses.append((child.attr, child.lineno))

            walk(child, aliases)

    walk(tree, set())
    return uses


def python_files(*relative):
    paths = []
    for entry in relative:
        full = os.path.join(SRC, entry)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                if name.endswith(".py"):
                    paths.append(os.path.join(full, name))
        else:
            paths.append(full)
    return paths


def dynamic_attributes(tree):
    """Attribute names created by ``for key in FIELD_MAP: setattr(self, key, ...)``.

    ``HushmixApp.setup_variables`` builds the per-button Tk variable lists from
    :data:`gui.app.VAR_FIELDS`; the keys of that map are attributes even though
    they never appear as a literal ``self.X = ...`` assignment.
    """
    field_maps = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Dict):
                keys = {
                    key.value
                    for key in node.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
                if keys:
                    field_maps[target.id] = keys

    dynamic = set()
    for node in ast.walk(tree):
        # for loop over one of the field maps, containing a setattr call
        if isinstance(node, (ast.For, ast.comprehension)):
            iterable = node.iter
            name = None
            if isinstance(iterable, ast.Name):
                name = iterable.id
            elif isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name):
                if iterable.func.id in ("list", "tuple") and iterable.args:
                    argument = iterable.args[0]
                    if isinstance(argument, ast.Name):
                        name = argument.id
            if name in field_maps:
                dynamic |= field_maps[name]
    return dynamic


def main():
    failures = []

    app_tree = parse(os.path.join(SRC, "gui", "app.py"))
    app_class = class_node(app_tree, "HushmixApp")
    if app_class is None:
        print("FAIL: HushmixApp not found in gui/app.py")
        return 1

    app_members = (
        public_names(app_class)
        | assigned_attributes(app_class)
        | dynamic_attributes(app_tree)
        | APP_EXTRA_ATTRIBUTES
    )

    # ---------------------------------------------------------- app.X references
    consumers = python_files(
        "gui/gui_components.py",
        "gui/window_manager.py",
        "gui/settings_window.py",
        "gui/help_window.py",
        "gui/buttonSettings_window.py",
        "controllers/volume_manager.py",
        "controllers/button_actions.py",
        "controllers/profile_manager.py",
    )

    for path in consumers:
        for attribute, lineno in app_attribute_uses(path):
            if attribute not in app_members:
                failures.append(
                    f"{os.path.relpath(path, ROOT)}:{lineno}: "
                    f"app.{attribute} is not defined on HushmixApp"
                )

    # --------------------------------------------------- manager method calls
    manager_files = {
        "ConfigManager": os.path.join(SRC, "utils", "config_manager.py"),
        "SettingsManager": os.path.join(SRC, "utils", "settings_manager.py"),
        "VolumeManager": os.path.join(SRC, "controllers", "volume_manager.py"),
        "ButtonActions": os.path.join(SRC, "controllers", "button_actions.py"),
        "ProfileManager": os.path.join(SRC, "controllers", "profile_manager.py"),
        "WindowManager": os.path.join(SRC, "gui", "window_manager.py"),
        "AudioController": os.path.join(SRC, "controllers", "audio_controller.py"),
        "SerialController": os.path.join(SRC, "controllers", "serial_controller.py"),
        "EnhancedVersionManager": os.path.join(
            SRC, "utils", "enhanced_version_manager.py"
        ),
        "IconManager": os.path.join(SRC, "utils", "icon_manager.py"),
        "GUIComponents": os.path.join(SRC, "gui", "gui_components.py"),
    }

    # Drop entries whose module no longer exists, so a deletion does not leave the
    # check referring to a file that is gone.
    manager_files = {
        name: path for name, path in manager_files.items() if os.path.exists(path)
    }

    manager_members = {}
    for name, path in manager_files.items():
        node = class_node(parse(path), name)
        if node is None:
            failures.append(f"{name} not found in {os.path.relpath(path, ROOT)}")
            continue
        manager_members[name] = public_names(node) | assigned_attributes(node)

    # Variable name -> class name, from obvious assignments in every file.
    variable_types = {}
    for path in python_files("gui", "controllers", "utils"):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                    # self.profile_manager = ProfileManager(self)
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        variable_types[target.attr] = node.value.func.id

    for path in python_files("gui", "controllers", "utils"):
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Attribute):
                continue
            if not isinstance(node.value, ast.Name):
                continue
            class_name = variable_types.get(node.value.id)
            if class_name not in manager_members:
                continue
            if node.attr in manager_members[class_name]:
                continue
            if node.attr.startswith("__"):
                continue
            failures.append(
                f"{os.path.relpath(path, ROOT)}:{node.lineno}: "
                f"{node.value.id}.{node.attr} is not defined on {class_name}"
            )

    # ---------------------------------------- profile schema completeness
    config_tree = parse(os.path.join(SRC, "utils", "config_manager.py"))
    schema = None
    for node in ast.walk(config_tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PROFILE_SETTINGS" for t in node.targets
        ):
            schema = {key.value for key in node.value.keys}

    if schema is None:
        failures.append("ConfigManager.PROFILE_SETTINGS not found")
    else:
        referenced = set()
        for path in python_files("gui", "controllers", "utils"):
            for match in re.finditer(r'"(applications|mute_settings|mute_state|'
                                     r'app_launch_enabled|app_launch_paths|'
                                     r'keyboard_shortcut_enabled|keyboard_shortcuts|'
                                     r'mute_button_modes|app_button_modes|'
                                     r'shortcut_button_modes|media_control_enabled|'
                                     r'media_control_actions|media_control_button_modes)"',
                                     read(path)):
                referenced.add(match.group(1))

        missing = referenced - schema
        for field in sorted(missing):
            failures.append(f"field {field!r} is used but missing from PROFILE_SETTINGS")

    # ---------------------------------------------------------------- report
    print("=" * 60)
    if failures:
        print(f"consistency failures: {len(failures)}")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("consistency checks passed")
    print(f"  app members checked: {len(app_members)}")
    print(f"  manager classes checked: {len(manager_members)}")
    if schema:
        print(f"  profile fields: {len(schema)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
