import sublime_plugin
import sublime
import re
import os.path

SUBLIME_2_VERSION = 2221

class DjangoNoseTestCommand(sublime_plugin.TextCommand):

    def get_regions(self, selector):
        return [
            (self.view.rowcol(r.begin())[0], self.view.substr(r))
            for r in self.view.find_by_selector(selector)]

    def get_lines(self):
        return [self.view.rowcol(r.begin())[0] for r in self.view.sel()]

    def filter_selected_regions(self, regions, lines):
        rr = regions[:]
        rr.reverse()
        filtered = []
        r_end = None
        for r in rr:
            for l in lines:
                if l >= r[0] and (r_end is None or l <= r_end):
                    filtered.append(r)
                    break
            r_end = r[0] - 1
        filtered.reverse()
        return filtered

    def fixup_function_names(self, regions):
        retval = []
        for r in regions:
            m = re.match(r'^\s+def\s+([a-zA-Z0-9_]+)\(', r[1])
            if m:
                r = (r[0], m.groups()[0])
            if r[1].startswith('test_'):
                retval.append(r)
        return retval

    def merge_class_fn_regions(self, cls_regions, fn_regions):
        rr = cls_regions[:]
        rr.reverse()
        merged = []
        r_end = None
        used_fn = []
        for r in rr:
            used_cls = False
            for f in fn_regions:
                if f[0] > r[0] and (r_end is None or f[0] <= r_end) \
                    and not f[0] in used_fn:
                        merged.append('%s.%s' % (r[1], f[1]))
                        used_fn.append(f[0])
                        used_cls = True
            r_end = r[0] - 1
            if not used_cls:
                merged.append(r[1])
        return merged

    def discover_manage_py(self):
        fname = self.view.file_name()
        components = []
        dname = None
        app_name = None
        while True:
            components.append(os.path.basename(fname))
            dname = os.path.dirname(fname)
            if dname == fname:
                return (None, None)  # search was unsuccessful
            if os.path.exists(os.path.join(dname, 'manage.py')):
                break
            if (os.path.isfile(os.path.join(dname, 'models.py')) or
                    os.path.isfile(os.path.join(dname, 'models',
                        '__init__.py'))):
                app_name = os.path.basename(dname)
            fname = dname
        components.reverse()
        if components[-1].endswith('.py'):
            components[-1] = components[-1][:-3]
        return (dname, app_name, '.'.join(components))

    def run_tests(self, regions):
        root_dir, app_name, file_python_path = self.discover_manage_py()
        if not root_dir:
            return

        settings = self.view.settings().get('django-nose-test') or {}
        cmd = [settings.get('python', 'python'), 'manage.py', 'test']

        django_settings = settings.get('django-settings', '')

        if django_settings:
            cmd.append('--settings=' + django_settings)

        django_testrunner = settings.get('django_testrunner', '')

        if django_testrunner:
            cmd.append('--testrunner=' + django_testrunner)

        use_nose = settings.get('use-nose', False)

        nose_options = settings.get('nose-options', [])

        doted_notation = settings.get('doted-notation', [])

        apps_dir = settings.get('apps-dir', None)

        if regions != []:
            for r in regions:
                if use_nose:
                    cmd.append('%s:%s' % (file_python_path, r))
                elif doted_notation:
                    if apps_dir:
                        file_python_path = self.file_path_without_apps_dir(file_python_path,
                                                                           apps_dir)
                    cmd.append('%s.%s' % (file_python_path, r))
                else:
                    cmd.append('%s.%s' % (app_name, r))
        else:
            if use_nose:
                cmd.append(file_python_path)
            elif doted_notation:
                if apps_dir:
                    file_python_path = self.file_path_without_apps_dir(file_python_path,
                                                                       apps_dir)
                cmd.append(file_python_path)
            else:
                cmd.append(app_name)

        if use_nose:
            for option in nose_options:
                cmd.append(option)

        self.view.window().run_command('exec', {
            'cmd': cmd,
            'working_dir': root_dir
        })

    def file_path_without_apps_dir(self, file_python_path, apps_dir):
        apps_dir_dot_path = apps_dir + '.'
        if file_python_path.startswith(apps_dir_dot_path):
            file_python_path = file_python_path[len(apps_dir_dot_path):]
        return file_python_path

    def save_before_run(self):
        if self.view.file_name() and self.view.is_dirty():
            # ensure that deleted files won't be resurrected
            if os.path.exists(self.view.file_name()):
                self.view.run_command('save')

    def run(self, edit):
        if 'Python' not in self.view.settings().get('syntax'):
            return

        self.save_before_run()

        lines = self.get_lines()

        region_class_name = 'entity.name.type.class'
        if int(sublime.version()) > SUBLIME_2_VERSION:
            region_class_name = 'entity.name.class'

        cls_regions = self.filter_selected_regions(
            self.get_regions(region_class_name), lines)

        fn_regions = self.filter_selected_regions(
            self.get_regions('meta.function'), lines)
        fn_regions = self.fixup_function_names(fn_regions)

        regions = self.merge_class_fn_regions(cls_regions, fn_regions)

        self.run_tests(regions)
