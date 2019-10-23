import os
import re
import base64
import os.path
import sublime
import sublime_plugin
from . import emmet
from . import utils

mime_types = {
    '.gif' : 'image/gif',
    '.png' : 'image/png',
    '.jpg' : 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg' : 'image/svg+xml',
    '.webp' : 'image/webp',
}

class ConvertDataUrl(sublime_plugin.TextCommand):
    def run(self, edit):
        caret = utils.get_caret(self.view)
        tag = emmet.tag(utils.get_content(self.view), caret)

        if tag and tag['name'].lower() == 'img' and 'attributes' in tag:
            src_attr = next((a for a in tag['attributes'] if a['name'] == 'src'), None)
            src = src_attr and utils.attribute_value(src_attr)
            if not src:
                return

            if src.startswith('data:'):
                on_done = lambda text: convert_from_data_url(self.view, src_attr, src, text)
                self.view.window().show_input_panel('Enter file name', 'image%s' % get_ext(src), on_done, None, None)
            else:
                convert_to_data_url(self.view, edit, src_attr, src)


class ConvertDataUrlReplace(sublime_plugin.TextCommand):
    "Internal command for async text replace"
    def run(self, edit, region, text):
        region = sublime.Region(*region)
        self.view.replace(edit, region, text)


def convert_to_data_url(view: sublime.View, edit: sublime.Edit, attr: dict, src: str):
    max_size = view.settings().get('emmet_max_data_url', 0)

    if utils.is_url(src):
        abs_file = src
    elif view.file_name():
        abs_file = utils.locate_file(view.file_name(), src)
        if abs_file and max_size and os.path.getsize(abs_file) > max_size:
            print('Size of %s file is too large. Check "emmet_max_data_url" setting to increase this limit' % abs_file)
            return

    if abs_file:
        data = utils.read_file(abs_file)
        if data and (not max_size or len(data) <= max_size):
            base, ext = os.path.splitext(abs_file)
            if ext in mime_types:
                new_src = 'data:%s;base64,%s' % (mime_types[ext], base64.urlsafe_b64encode(data).decode('utf8'))
                r = utils.attribute_region(attr)
                view.replace(edit, r, utils.patch_attribute(attr, new_src))


def convert_from_data_url(view: sublime.View, attr: dict, src: str, dest: str):
    m = re.match(r'^data\:.+?;base64,(.+)', src)
    if m:
        base_dir = os.path.dirname(view.file_name())
        abs_dest = utils.create_path(base_dir, dest)
        file_url = os.path.relpath(abs_dest, base_dir).replace('\\', '/')

        dest_dir = os.path.dirname(abs_dest)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        with open(abs_dest, 'wb') as fd:
            fd.write(base64.urlsafe_b64decode(m.group(1)))

        r = utils.attribute_region(attr)
        view.run_command('convert_data_url_replace', {
            'region': [r.begin(), r.end()],
            'text': utils.patch_attribute(attr, file_url)
        })


def get_ext(data_url: str):
    m = re.match(r'data:(.+?);', data_url)
    if m:
        for k, v in mime_types.items():
            if v == m.group(1):
                return k
    return '.jpg'
