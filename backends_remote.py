"""
romforge.backends_remote
==========================
Docker and GitHub Actions build backends. Both generate the artifact
needed to run the build elsewhere rather than silently assuming infinite
resources -- Docker still needs the host to have disk/RAM; GitHub Actions
free runners (~14GB disk, ~6hr job limit) realistically can only complete
small device trees or partial pipeline steps, which is stated rather than
hidden.

A Cloud VM / QEMU-based service is NOT a separate backend: it's the local
backend, run over SSH on a box you provisioned yourself (e.g. `ssh myvm
'cd romforge && python3 romforge.py build ...'`). Faking a fourth
implementation here would just be the same shell commands with extra
indirection.
"""

import subprocess
from pathlib import Path

from builder import BuildBackend


DOCKERFILE_TEMPLATE = """\
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \\
    git-core gnupg flex bison build-essential zip curl zlib1g-dev \\
    libc6-dev-i386 lib32ncurses5-dev x11proto-core-dev libx11-dev \\
    lib32z1-dev libgl1-mesa-dev libxml2-utils xsltproc unzip fontconfig \\
    python3 python-is-python3 openjdk-17-jdk-headless rsync bc \\
    && rm -rf /var/lib/apt/lists/*
RUN curl -s https://storage.googleapis.com/git-repo-downloads/repo > /usr/local/bin/repo \\
    && chmod +x /usr/local/bin/repo
WORKDIR /workspace
# Source is expected to be bind-mounted at /workspace at `docker run` time,
# not baked into the image -- AOSP trees are far too large for an image layer.
CMD ["bash"]
"""

GH_ACTIONS_TEMPLATE = """\
name: romforge-build
on: workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    # NOTE: free GitHub-hosted runners have ~14GB disk and a 6hr job limit.
    # This is realistically only enough for small device trees, partial
    # syncs, or build steps you've already split down -- not a full
    # from-scratch AOSP build for most devices. Use a self-hosted runner
    # with adequate disk/RAM for anything beyond a quick test.
    steps:
      - name: Free up disk space
        run: |
          sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc
      - name: Install deps
        run: |
          sudo apt-get update && sudo apt-get install -y \\
            git-core gnupg flex bison build-essential zip curl zlib1g-dev \\
            libc6-dev-i386 lib32ncurses5-dev x11proto-core-dev libx11-dev \\
            lib32z1-dev libgl1-mesa-dev libxml2-utils xsltproc unzip \\
            fontconfig openjdk-17-jdk-headless rsync bc
      - name: Install repo tool
        run: |
          curl -s https://storage.googleapis.com/git-repo-downloads/repo > repo
          chmod +x repo && sudo mv repo /usr/local/bin/repo
      - name: repo init
        run: repo init -u {manifest_url} -b {branch}
      - name: repo sync
        run: repo sync -c -j4 --force-sync
      - name: Build
        run: |
          source build/envsetup.sh
          lunch {lunch_target}
          mka bacon -j4
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: rom-output
          path: out/target/product/*/*.zip
"""


class DockerBuildBackend(BuildBackend):
    name = "docker"

    def write_dockerfile(self, workdir: Path, dry_run: bool = False) -> Path:
        path = workdir / "Dockerfile.romforge"
        if dry_run:
            print(f"  [dry-run] would write {path}")
            return path
        path.write_text(DOCKERFILE_TEMPLATE)
        return path

    def run_build(self, workdir: Path, lunch_target: str, jobs: int,
                   dry_run: bool = False) -> bool:
        dockerfile = self.write_dockerfile(workdir, dry_run=dry_run)
        image_tag = "romforge-builder:latest"
        build_cmd = ["docker", "build", "-t", image_tag, "-f", str(dockerfile), str(workdir)]
        run_cmd = [
            "docker", "run", "--rm", "-v", f"{workdir}:/workspace",
            image_tag, "bash", "-c",
            f"source build/envsetup.sh && lunch {lunch_target} && mka bacon -j{jobs}",
        ]
        print(f"  [docker backend] image: {image_tag}, lunch target: {lunch_target}")
        if dry_run:
            print(f"  [dry-run] would run: {' '.join(build_cmd)}")
            print(f"  [dry-run] would run: {' '.join(run_cmd)}")
            return True
        try:
            subprocess.run(build_cmd, check=True)
            subprocess.run(run_cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"  Docker build/run failed (exit {e.returncode}). Make "
                  f"sure Docker has enough resources allocated (Settings > "
                  f"Resources): {150}GB+ disk, 16GB+ RAM recommended.")
            return False
        return True


class GithubActionsBuildBackend(BuildBackend):
    name = "github-actions"

    def write_workflow(self, workdir: Path, manifest_url: str, branch: str,
                        lunch_target: str, dry_run: bool = False) -> Path:
        out = workdir / ".github" / "workflows"
        path = out / "romforge-build.yml"
        if dry_run:
            print(f"  [dry-run] would write workflow to {path}")
            return path
        out.mkdir(parents=True, exist_ok=True)
        path.write_text(GH_ACTIONS_TEMPLATE.format(
            manifest_url=manifest_url, branch=branch, lunch_target=lunch_target))
        return path

    def run_build(self, workdir: Path, lunch_target: str, jobs: int,
                   dry_run: bool = False) -> bool:
        # This backend doesn't execute anything locally -- it generates the
        # workflow file and tells the user how to trigger it, since the
        # actual execution happens on GitHub's infrastructure after a push.
        print("  [github-actions backend] This backend generates a workflow "
              "file rather than running a build now.")
        print("  Commit the generated .github/workflows/romforge-build.yml "
              "to your repo, push it, then trigger it from the Actions tab "
              "(workflow_dispatch) or via `gh workflow run romforge-build.yml`.")
        if dry_run:
            print("  [dry-run] would write .github/workflows/romforge-build.yml")
        return True
