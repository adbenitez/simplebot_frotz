"""Setup module installation."""

import os
import subprocess
from tempfile import TemporaryDirectory

from setuptools import find_packages, setup
from setuptools.command.install import install


class CustomInstall(install):
    """Custom handler for the 'install' command."""

    def run(self) -> None:
        install_frotz()
        super().run()


def install_frotz() -> None:
    """Compile and install frotz if needed."""
    dest_path = os.path.expanduser("~/.simplebot/")
    if os.path.exists(dest_path + "dfrotz"):
        return  # binary exists no need to build it
    if not os.path.exists(dest_path + "frotz-games"):
        os.makedirs(dest_path + "frotz-games")

    frotz_repo = "https://gitlab.com/DavidGriffith/frotz.git"
    with TemporaryDirectory(prefix="frotz-") as temp_dir:
        subprocess.check_call(["git", "clone", "--depth=1", frotz_repo, temp_dir])
        subprocess.check_call(["make", "dumb"], cwd=temp_dir)
        subprocess.check_call(["cp", f"{temp_dir}/dfrotz", dest_path])


def load_requirements(path: str) -> list:
    """Load requirements from the given relative path."""
    with open(path, encoding="utf-8") as file:  # noqa
        requirements = []
        for line in file.read().split("\n"):
            if line.startswith("-r"):
                dirname = os.path.dirname(path)
                filename = line.split(maxsplit=1)[1]
                requirements.extend(load_requirements(os.path.join(dirname, filename)))
            elif line and not line.startswith("#"):
                requirements.append(line.replace("==", ">="))
        return requirements


if __name__ == "__main__":
    MODULE_NAME = "simplebot_frotz"
    DESC = (
        "Z-machine interpreter plugin for SimpleBot,"
        " play interactive fiction games in Delta Chat!"
    )

    with open("README.rst") as fh:
        long_description = fh.read()

    setup(
        name=MODULE_NAME,
        setup_requires=["setuptools_scm"],
        use_scm_version={
            "root": ".",
            "relative_to": __file__,
            "tag_regex": r"^(?P<prefix>v)?(?P<version>[^\+]+)(?P<suffix>.*)?$",
            "git_describe_command": "git describe --dirty --tags --long --match v*.*.*",
        },
        description=DESC,
        long_description=long_description,
        long_description_content_type="text/x-rst",
        author="The SimpleBot Contributors",
        author_email="adbenitez@nauta.cu",
        url=f"https://github.com/simplebot-org/{MODULE_NAME}",
        keywords="simplebot plugin deltachat game interactive-fiction",
        license="Apache2.0",
        classifiers=[
            "Development Status :: 4 - Beta",
            "Environment :: Plugins",
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
            "Operating System :: OS Independent",
            "Topic :: Utilities",
        ],
        zip_safe=False,
        include_package_data=True,
        packages=find_packages(),
        install_requires=load_requirements("requirements/requirements.txt"),
        extras_require={
            "test": load_requirements("requirements/requirements-test.txt"),
            "dev": load_requirements("requirements/requirements-dev.txt"),
        },
        entry_points={
            "simplebot.plugins": "{0} = {0}".format(MODULE_NAME),
        },
        cmdclass={"install": CustomInstall},
    )
