"""Put the reference validator in the wheel at build time.

The point of this package is that a LangGraph user can go from nothing to a
checked record without cloning anything. Emitting a record they cannot then
validate would leave them holding a file and a claim, which is the situation
the specification exists to end.

So `pip install testimony-langgraph` ships `testimony-validate` as well. The
validator is one standard-library file with no network access, and it is the
same file the repository uses, copied at build time rather than committed
twice. A second copy is a second copy to drift, and a validator that disagrees
with itself is worse than no validator.

When the source tree is absent and the copy is already here, that is the sdist
case: a wheel built from an sdist has no ../../scripts to read, and the file it
carries is the right one.
"""
import os
import shutil

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# The same tuple shape the other four adapters use. This one carried a single
# SOURCE/DEST pair until the anchored path needed shipping, and one adapter
# bundling differently from four is a divergence that costs more than it saves.
#
# testimony_emit is deliberately NOT here: this adapter does not import it, and
# shipping a module a package has no use for is a file to keep in step for
# nothing. testimony_anchor is here because an example that cannot show the
# anchored path leaves a reader believing TR-4 means anchored.
BUNDLE = ("testimony_validate.py", "testimony_anchor.py")


class BundleValidator(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        here = os.path.dirname(os.path.abspath(__file__))
        for name in BUNDLE:
            src = os.path.normpath(os.path.join(here, "..", "..", "spec", name))
            dst = os.path.join(here, name)
            if not os.path.exists(src):
                if os.path.exists(dst):
                    continue    # building from an sdist; the copy is correct
                raise RuntimeError(
                    "cannot find %s and no bundled copy is present. The wheel "
                    "would install a command that does not exist." % src)
            shutil.copyfile(src, dst)

        dst = os.path.join(here, "testimony_validate.py")
        # Belt and braces: a wheel whose validator does not import is worse than
        # one without it, because the failure appears in the user's terminal
        # rather than in this build.
        with open(dst, encoding="utf-8") as fh:
            text = fh.read()
        if "def main(" not in text or "def validate(" not in text:
            raise RuntimeError(
                "the bundled validator has no main() or validate(); the console "
                "script would be dead on arrival")
