"""Put the reference validator and the emitter in the wheel at build time.

The point of this package is that a Pydantic AI user can go from nothing to a checked
record without cloning anything. Emitting a record they cannot then validate
would leave them holding a file and a claim, which is the situation the
specification exists to end.

So `pip install testimony-pydantic-ai` ships `testimony-validate` as well. Both bundled files
are the repository's own, copied at build time rather than committed twice. A
second copy is a second copy to drift, and a validator that disagrees with
itself is worse than no validator.

The adapter imports testimony_emit, so that travels too. A wheel carrying the
adapter but not the module it imports installs an ImportError.

When the source tree is absent and the copies are already here, that is the
sdist case: a wheel built from an sdist has no ../../spec to read, and the
files it carries are the right ones.
"""
import os
import shutil

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BUNDLE = ("testimony_validate.py", "testimony_emit.py")


class BundleSpec(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        here = os.path.dirname(os.path.abspath(__file__))
        for name in BUNDLE:
            src = os.path.normpath(os.path.join(here, "..", "..", "spec", name))
            dst = os.path.join(here, name)
            if not os.path.exists(src):
                if os.path.exists(dst):
                    continue        # building from an sdist; the copy is right
                raise RuntimeError(
                    "cannot find %s and no bundled copy is present. The wheel "
                    "would install an import that does not resolve." % src)
            shutil.copyfile(src, dst)

        # Belt and braces: a wheel whose validator does not import is worse than
        # one without it, because the failure appears in the user's terminal
        # rather than in this build.
        with open(os.path.join(here, "testimony_validate.py"),
                  encoding="utf-8") as fh:
            text = fh.read()
        if "def main(" not in text or "def validate(" not in text:
            raise RuntimeError(
                "the bundled validator has no main() or validate(); the console "
                "script would be dead on arrival")
        with open(os.path.join(here, "testimony_emit.py"),
                  encoding="utf-8") as fh:
            if "class Record" not in fh.read():
                raise RuntimeError(
                    "the bundled emitter has no Record class; the adapter would "
                    "fail on import")
