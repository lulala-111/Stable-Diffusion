import glob
import os.path
import urllib.parse
from pathlib import Path
from PIL import PngImagePlugin

from modules import shared
from modules.images import read_info_from_image
import gradio as gr
import json
import html

from modules.generation_parameters_copypaste import image_from_url_text

extra_pages = []
allowed_dirs = set()


def register_page(page):
    """registers extra networks page for the UI; recommend doing it in on_before_ui() callback for extensions"""

    extra_pages.append(page)
    allowed_dirs.clear()
    allowed_dirs.update(set(sum([x.allowed_directories_for_previews() for x in extra_pages], [])))


def fetch_file(filename: str = ""):
    from starlette.responses import FileResponse

    if not any([Path(x).absolute() in Path(filename).absolute().parents for x in allowed_dirs]):
        raise ValueError(f"File cannot be fetched: {filename}. Must be in one of directories registered by extra pages.")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".png", ".jpg", ".webp"):
        raise ValueError(f"File cannot be fetched: {filename}. Only png and jpg and webp.")

    # would profit from returning 304
    return FileResponse(filename, headers={"Accept-Ranges": "bytes"})


def get_metadata(page: str = "", item: str = ""):
    from starlette.responses import JSONResponse

    page = next(iter([x for x in extra_pages if x.name == page]), None)
    if page is None:
        return JSONResponse({})

    metadata = page.metadata.get(item)
    if metadata is None:
        return JSONResponse({})

    return JSONResponse({"metadata": metadata})


def add_pages_to_demo(app):
    app.add_api_route("/sd_extra_networks/thumb", fetch_file, methods=["GET"])
    app.add_api_route("/sd_extra_networks/metadata", get_metadata, methods=["GET"])


class ExtraNetworksPage:
    def __init__(self, title):
        self.title = title
        self.name = title.lower()
        self.card_page = shared.html("extra-networks-card.html")
        self.card_page_advanced = shared.html("extra-networks-card-advanced.html")
        self.allow_negative_prompt = False
        self.metadata = {}

    def refresh(self):
        pass

    def link_preview(self, filename):
        return "./sd_extra_networks/thumb?filename=" + urllib.parse.quote(filename.replace('\\', '/')) + "&mtime=" + str(os.path.getmtime(filename))

    def search_terms_from_path(self, filename, possible_directories=None):
        abspath = os.path.abspath(filename)

        for parentdir in (possible_directories if possible_directories is not None else self.allowed_directories_for_previews()):
            parentdir = os.path.abspath(parentdir)
            if abspath.startswith(parentdir):
                return abspath[len(parentdir):].replace('\\', '/')

        return ""

    def create_html(self, tabname):
        view = shared.opts.extra_networks_default_view
        items_html = ''

        self.metadata = {}

        subdirs = {}
        for parentdir in [os.path.abspath(x) for x in self.allowed_directories_for_previews()]:
            for x in glob.glob(os.path.join(parentdir, '**/*'), recursive=True):
                if not os.path.isdir(x):
                    continue

                subdir = os.path.abspath(x)[len(parentdir):].replace("\\", "/")
                while subdir.startswith("/"):
                    subdir = subdir[1:]

                is_empty = len(os.listdir(x)) == 0
                if not is_empty and not subdir.endswith("/"):
                    subdir = subdir + "/"

                subdirs[subdir] = 1

        if subdirs:
            subdirs = {"": 1, **subdirs}

        subdirs_html = "".join([f"""
<button class='lg secondary gradio-button custom-button{" search-all" if subdir=="" else ""}' onclick='extraNetworksSearchButton("{tabname}_extra_tabs", event)'>
{html.escape(subdir if subdir!="" else "all")}
</button>
""" for subdir in subdirs])

        for item in self.list_items():
            metadata = item.get("metadata")
            if metadata:
                self.metadata[item["name"]] = metadata

            items_html += self.create_html_for_item(item, tabname)

        if items_html == '':
            dirs = "".join([f"<li>{x}</li>" for x in self.allowed_directories_for_previews()])
            items_html = shared.html("extra-networks-no-cards.html").format(dirs=dirs)

        self_name_id = self.name.replace(" ", "_")

        res = f"""
<div id='{tabname}_{self_name_id}_subdirs' class='extra-network-subdirs extra-network-subdirs-{view}'>
{subdirs_html}
</div>
<div id='{tabname}_{self_name_id}_cards' class='extra-network-{view}'>
{items_html}
</div>
"""
 
        return res

    def list_items(self):
        raise NotImplementedError()

    def allowed_directories_for_previews(self):
        return []

    def create_html_for_item(self, item, tabname):
        preview = item.get("preview", None)

        onclick = item.get("onclick", None)
        if onclick is None:
            onclick = '"' + html.escape(f"""return cardClicked({json.dumps(tabname)}, {item["prompt"]}, {"true" if self.allow_negative_prompt else "false"})""") + '"'

        height = f"height: {shared.opts.extra_networks_card_height}px;" if shared.opts.extra_networks_card_height else ''
        width = f"width: {shared.opts.extra_networks_card_width}px;" if shared.opts.extra_networks_card_width else ''
        height_advanced_view = f"height: {shared.opts.extra_networks_advanced_card_height}px;" if shared.opts.extra_networks_advanced_card_height else ''
        width_advanced_view = f"width: {shared.opts.extra_networks_advanced_card_width}px;" if shared.opts.extra_networks_advanced_card_width else ''
        image_w_advanced_view = f"flex-basis: {shared.opts.extra_networks_advanced_card_image_width}px;" if shared.opts.extra_networks_advanced_card_image_width else ''
        current_view = shared.opts.extra_networks_default_view 

        background_image = f"background-image: url(\"{html.escape(preview)}\");" if preview else ''
        metadata_button = ""
        metadata = item.get("metadata")
        if metadata:
            metadata_button = f"<div class='metadata-button' title='Show metadata' onclick='extraNetworksRequestMetadata(event, {json.dumps(self.name)}, {json.dumps(item['name'])})'></div>"

        args = {
            "style": f"'{height}{width}{background_image}'",
            "style_advanced_size": f"'{height_advanced_view}{width_advanced_view}'",
            "style_advanced_image_w": f"'{image_w_advanced_view}{background_image}'",
            "prompt": item.get("prompt", None),
            "tabname": json.dumps(tabname),
            "local_preview": json.dumps(item["local_preview"]),
            "name": item["name"],
            "description": (item.get("description") or ""),
            "card_clicked": onclick,
            "current_view": current_view,
            "save_card_preview": '"' + html.escape(f"""return saveCardPreview(event, {json.dumps(tabname)}, {json.dumps(item["local_preview"])})""") + '"',
            "save_card_description": '"' + html.escape(f"""return saveCardDescription(event, {json.dumps(tabname)}, {json.dumps(item["local_preview"])}, {json.dumps(current_view)}, {json.dumps(item["name"])}, {json.dumps(item["description"])})""") + '"',
            "read_card_description": '"' + html.escape(f"""return readCardDescription(event, {json.dumps(tabname)}, {json.dumps(item["local_preview"])}, {json.dumps(current_view)}, {json.dumps(item["name"])}, {json.dumps(item["description"])})""") + '"',
            "toggle_read_edit": '"' + html.escape(f"""return toggleEditSwitch(event, {json.dumps(tabname)}, {json.dumps(current_view)}, {json.dumps(item["name"])})""") + '"',
            
            "search_term": item.get("search_term", ""),
            "metadata_button": metadata_button,

        }

        res = self.card_page.format(**args)
        if current_view == "advanced":
            res = self.card_page_advanced.format(**args)
        return res

    def find_preview(self, path):
        """
        Find a preview PNG for a given path (without extension) and call link_preview on it.
        """

        preview_extensions = ["png", "jpg", "webp"]
        if shared.opts.samples_format not in preview_extensions:
            preview_extensions.append(shared.opts.samples_format)

        potential_files = sum([[path + "." + ext, path + ".preview." + ext] for ext in preview_extensions], [])

        for file in potential_files:
            if os.path.isfile(file):
                return self.link_preview(file)

        return None

    def find_description(self, path):
        """
        Find and read a description file for a given path (without extension).
        """
        for file in [f"{path}.txt", f"{path}.description.txt"]:
            try:
                with open(file, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                pass
        return None


def intialize():
    extra_pages.clear()


class ExtraNetworksUi:
    def __init__(self):
        self.pages = None
        self.stored_extra_pages = None

        self.button_save_preview = None
        self.preview_target_filename = None

        self.button_save_description = None
        self.button_read_description = None
        self.description_target_filename = None
        self.description_input = None
        self.description_target_input = None

        self.tabname = None
        self.current_view = None
        self.view_choices_in_setting = None
        self.control_change_view = None
        self.btns_change_view = None


def pages_in_preferred_order(pages):
    tab_order = [x.lower().strip() for x in shared.opts.ui_extra_networks_tab_reorder.split(",")]

    def tab_name_score(name):
        name = name.lower()
        for i, possible_match in enumerate(tab_order):
            if possible_match in name:
                return i

        return len(pages)

    tab_scores = {page.name: (tab_name_score(page.name), original_index) for original_index, page in enumerate(pages)}

    return sorted(pages, key=lambda x: tab_scores[x.name])


def create_ui(container, button, tabname):
    ui = ExtraNetworksUi()
    ui.pages = []
    ui.stored_extra_pages = pages_in_preferred_order(extra_pages.copy())
    ui.tabname = tabname
    ui.current_view = shared.opts.extra_networks_default_view
    ui.view_choices_in_setting = shared.opts.data_labels["extra_networks_default_view"].component_args["choices"]

    with gr.Tabs(elem_id=tabname+"_extra_tabs") as tabs:
        for page in ui.stored_extra_pages:
            with gr.Tab(page.title):

                page_elem = gr.HTML(page.create_html(ui.tabname))
                ui.pages.append(page_elem)

    filter = gr.Textbox('', show_label=False, elem_id=tabname+"_extra_search", placeholder="Search...", visible=False)
    button_refresh = gr.Button('Refresh', elem_id=tabname+"_extra_refresh")

    if ui.current_view == "advanced" :
        ui.description_input = gr.TextArea('', show_label=False, elem_id=tabname+"_description_input", visible=False)
    else:
        ui.description_input = gr.TextArea('', show_label=False, elem_id=tabname+"_description_input", placeholder="Save/Replace Extra Network Description...", lines=2)

    ui.button_save_preview = gr.Button('Save preview', elem_id=tabname+"_save_preview", visible=False)
    ui.preview_target_filename = gr.Textbox('Preview save filename', elem_id=tabname+"_preview_filename", visible=False)

    ui.button_save_description = gr.Button('Save description', elem_id=tabname+"_save_description", visible=False)
    ui.button_read_description = gr.Button('Read description', elem_id=tabname+"_read_description", visible=False)
    ui.description_target_filename = gr.Textbox('Description save filename', elem_id=tabname+"_description_filename", visible=False)

    # change view control option 1 (dropdown) hide for not, doesnt fit current layout
    ui.control_change_view = gr.Dropdown(ui.view_choices_in_setting, value='Change Extra Network View (change view will force reload current page)', label="Change View (Will Force Reload Page)", show_label=False, elem_id=tabname+"_control_change_view", visible=False)
    # change view control option 2 (buttons) best for now because it fits the layout
    ui.btns_change_view = {}
    for view in ui.view_choices_in_setting:
        ui.btns_change_view[view] = gr.Button(f'{view.capitalize()} View', elem_id=f'{tabname}_extra_view_to_{view}', visible=True)
        if view == ui.current_view:
            ui.btns_change_view[view].visible = False
    
    def toggle_visibility(is_visible):
        is_visible = not is_visible
        return is_visible, gr.update(visible=is_visible), gr.update(variant=("secondary-down" if is_visible else "secondary"))

    state_visible = gr.State(value=False)
    button.click(fn=toggle_visibility, inputs=[state_visible], outputs=[state_visible, container, button])

    def refresh():
        res = []

        for pg in ui.stored_extra_pages:
            pg.refresh()
            res.append(pg.create_html(ui.tabname))

        return res

    button_refresh.click(fn=refresh, inputs=[], outputs=ui.pages)

    # view changer function
    def handle_view_change(btn):
        print(btn)
        view = btn.split(" ")[0].lower()
        if view in ui.view_choices_in_setting and view != ui.current_view:
            shared.opts.set('extra_networks_default_view', f"{view}")
            shared.state.interrupt()
            shared.state.need_restart = True
            print(f'previous view {ui.current_view}, set new view {view}, restarting')
        elif view not in ui.view_choices_in_setting:
            raise ValueError(f"Invalid view args: {view}")
        elif view == ui.current_view:
            print(f'You are trying to set: {view} = current view: {ui.current_view}, nothing changes')

    # print(ui.btns_change_view.items())
    for view, btn in ui.btns_change_view.items():
        btn.click(
            fn=handle_view_change,
            _js='function(x){restart_by_press_btn(); return x}',
            inputs=[btn],
            outputs=[]
        )
    return ui


def path_is_parent(parent_path, child_path):
    parent_path = os.path.abspath(parent_path)
    child_path = os.path.abspath(child_path)

    return child_path.startswith(parent_path)


def setup_ui(ui, gallery):
    def save_preview(index, images, filename):
        if len(images) == 0:
            print("There is no image in gallery to save as a preview.")
            return [page.create_html(ui.tabname) for page in ui.stored_extra_pages]

        index = int(index)
        index = 0 if index < 0 else index
        index = len(images) - 1 if index >= len(images) else index

        img_info = images[index if index >= 0 else 0]
        image = image_from_url_text(img_info)
        geninfo, items = read_info_from_image(image)

        is_allowed = False
        for extra_page in ui.stored_extra_pages:
            if any([path_is_parent(x, filename) for x in extra_page.allowed_directories_for_previews()]):
                is_allowed = True
                break

        assert is_allowed, f'writing to {filename} is not allowed'

        if geninfo:
            pnginfo_data = PngImagePlugin.PngInfo()
            pnginfo_data.add_text('parameters', geninfo)
            image.save(filename, pnginfo=pnginfo_data)
        else:
            image.save(filename)

        return [page.create_html(ui.tabname) for page in ui.stored_extra_pages]

    ui.button_save_preview.click(
        fn=save_preview,
        _js="function(x, y, z){return [selected_gallery_index(), y, z]}",
        inputs=[ui.preview_target_filename, gallery, ui.preview_target_filename],
        outputs=[*ui.pages]
    )
    
    # write description to a file
    def save_description(filename,descrip):
        lastDotIndex = filename.rindex('.')
        filename = filename[0:lastDotIndex]
        if filename.endswith(".preview"):
            filename = filename[:-8] + ".description.txt"
        else:
            filename = filename + ".description.txt"

        if descrip != "":
            try: 
                f = open(filename,'w')
            except OSError:
                print ("Could not open file to write: " + filename)
            with f:
                f.write(descrip)
                f.close()
        return [page.create_html(ui.tabname) for page in ui.stored_extra_pages]
    
    ui.button_save_description.click(
        fn=save_description,
        _js="function(x,y){return [x,y]}",
        inputs=[ui.description_target_filename, ui.description_input],
        outputs=[*ui.pages]
    )
