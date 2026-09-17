import os, stat

from pathlib import Path



MARKERS = {'.git', 'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',

           'requirements.txt', 'pyproject.toml', 'venv', '.venv', 'src', 'cargo.toml',

           'go.mod', 'pom.xml', 'build.gradle', 'platformio.ini', '.project', 'node_modules'}

RISK_DIRS = {'windows', 'program files', 'program files (x86)', 'programdata', 'windowsapps',

             'system32', 'recovery', 'boot', 'appdata', 'node_modules', '.git', 'venv', '.venv',

             '__pycache__', '$recycle.bin', 'system volume information', 'drivers', 'driverstore',
             'config.msi', 'msocache', 'perflogs', 'packages', '.npm', '.nuget', '.cargo',
             '.cache', 'cache', 'caches', 'browser profiles', 'profiles', 'databases',
             'steamapps', 'epic games', 'logs', 'application support', 'application', 'applications'}

RISK_EXT = {'.dll', '.sys', '.lnk', '.url', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.py',

            '.ini', '.cfg', '.db', '.sqlite', '.dat', '.reg', '.com', '.scr'}

TEMP_EXT = {'.crdownload', '.part', '.tmp', '.download'}



def under(path, root):

    try: return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]).casefold() == os.path.abspath(root).casefold()

    except ValueError: return False



def linked(path):

    p = Path(path)

    for node in (p, *p.parents):

        try:

            s = node.lstat()

            if stat.S_ISLNK(s.st_mode) or getattr(s, 'st_file_attributes', 0) & 0x400: return True

        except FileNotFoundError: continue

        except OSError: return True

    return False



class SafetyPolicy:

    def __init__(self, settings, state_dir=None):

        self.settings = settings

        self.state_dir = state_dir

        self.clear_cache()

    def clear_cache(self):

        self._projects = {}

        self._applications = {}

    def project_root(self, path):

        key = str(Path(path).parent)

        if key not in self._projects: self._projects[key] = self._project_root(path)

        return self._projects[key]

    def _project_root(self, path):

        p = Path(path)

        for parent in (p.parent, *p.parent.parents):

            try:

                with os.scandir(parent) as entries:
                    names = {child.name.lower() for child in entries}

                if names & MARKERS or any(n.endswith(('.sln', '.csproj', '.ino', '.prj')) for n in names):

                    return str(parent)

            except FileNotFoundError: continue

            except OSError: return str(parent)

        return None

    def directory_veto(self, path):

        p = Path(path)

        if linked(p): return "Symlink or Windows reparse point protected"

        if any(part.lower() in RISK_DIRS for part in p.parts): return "System or application directory protected"

        roots = self.settings["protected"] + self.settings["ignored"]

        if self.state_dir: roots = roots + [str(self.state_dir)]

        if any(under(p, root) for root in roots): return "User or application protected path"

        return ""



    def veto(self, path, destination=False):

        p = Path(path)

        if not p.is_absolute(): return 'Absolute path required'

        if linked(p): return 'Symlink or Windows reparse point protected'

        if any(part.lower() in RISK_DIRS for part in p.parts): return 'System or application directory protected'

        roots = self.settings['protected'] + self.settings['ignored']

        if self.state_dir: roots = roots + [str(self.state_dir)]

        if any(under(p, root) for root in roots): return 'User or application protected path'

        if self.project_root(p): return 'Project unit protected'

        key = str(p.parent)

        if key not in self._applications:

            risk = ''

            for parent in (p.parent, *p.parent.parents):

                if parent.parent == parent: continue

                try:

                    exe_risk = parent.name.lower() not in {'downloads', 'desktop', 'documents', 'pictures'} and parent != Path.home()
                    def dependency_entry(entry):
                        name=entry.name.lower()
                        suffix=os.path.splitext(name)[1]
                        return suffix in {'.dll','.sys','.manifest','.config'} or name in {'preferences','local state','login data'} or (exe_risk and suffix=='.exe' and not any(word in name for word in ('setup','install','update')))
                    with os.scandir(parent) as entries:
                        dependency = any(dependency_entry(c) for c in entries if c.is_file(follow_symlinks=False))
                    if dependency:

                        risk = 'Application dependency directory protected'; break

                except FileNotFoundError: continue

                except OSError: risk = 'Unknown directory risk'; break

            self._applications[key] = risk

        if self._applications[key]: return self._applications[key]

        if not destination and p.suffix.lower() in RISK_EXT | TEMP_EXT: return 'Application dependency, script or incomplete download protected'

        return ''

    def valid_destination(self, path):

        if not under(path, self.settings['library']): return 'Destination must stay inside File Library'

        return self.veto(path, destination=True)
