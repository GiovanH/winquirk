import keyboard
import tkinter as tk
from tkinter import ttk
import yaml
import glob
import re
import logging
from contextlib import contextmanager

NONSHIFT_MODIFIERS = set(filter(lambda s: "shift" not in s.lower(), keyboard.all_modifiers))
SHIFT_MODIFIERS = set(filter(lambda s: "shift" in s.lower(), keyboard.all_modifiers))


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

loghandler_file = logging.FileHandler(f'quirk_debug_latest.log')
loghandler_file.setLevel(logging.DEBUG)
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
loghandler_file.setFormatter(f_format)
logger.addHandler(loghandler_file)


def makeDemoYaml():
    with open("example.yaml", "w") as fp:
        fp.write('Kankri:\n    "[bB]": "6"\n    "[oO]": "9"')


class KeyListener(object):
    def __init__(self, toggle_hotkey="ctrl+space", onUpdate=None, postProcess=None):
        self.toggle_hotkey = toggle_hotkey
        self.postProcess = (postProcess if postProcess else (lambda string: string))
        self.onUpdate = (onUpdate if onUpdate else (lambda a, b: None))

        self.toggle_hotkey_hook = None
        self.text_buffer = []
        self.hooks = []
        self.hookEvents()

        self.active = False

    def setHotkey(self, new_hotkey):
        self.cleanup()
        self.toggle_hotkey = new_hotkey

    def cleanup(self):
        if self.active:
            keyboard.unhook(self.hook)
            self.text_buffer.clear()
            self.active = False

    def close(self):
        self.cleanup()
        keyboard.unhook(self.toggle_hotkey_hook)

    def getPreviewStr(self):
        return self.postProcess(self.getBufferStr())

    def getBufferStr(self):
        return "".join(self.text_buffer)

    def hookEvents(self):
        self.toggle_hotkey_hook = keyboard.add_hotkey(self.toggle_hotkey, self.onActiveToggle, suppress=True)

    def onActiveToggle(self):
        logger.debug("Toggle")
        if self.active:
            keyboard.unhook(self.hook)
            self.onFinish()
            self.active = False
        else:
            self.hook = keyboard.on_press(self.onKeyboardEvent, suppress=True)
            self.active = True
        logger.debug("==============")
        return

    def onFinish(self):
        logger.debug("WRITE " + self.getBufferStr() + " as " + self.getPreviewStr())
        keyboard.write(self.getPreviewStr(), restore_state_after=False)
        self.text_buffer.clear()
        self.onUpdate()

    def onKeyboardEvent(self, event):
        assert self.active

        if keyboard.is_pressed(self.toggle_hotkey) or event.name == self.toggle_hotkey or event.name == "esc":
            self.onActiveToggle()
            return

        if event.name == "enter":
            self.onActiveToggle()
            keyboard.press("enter")
            return

        if event.name in keyboard.all_modifiers:
            return

        new_char = event.name
        if new_char == "backspace":
            if self.text_buffer:
                self.text_buffer.pop()
                self.onUpdate()
            return

        if new_char == "space":
            new_char = " "
        else:
            if len(new_char) != 1:
                logger.warn("Bad char", new_char)
                return

        if any([keyboard.is_pressed(hotkey) for hotkey in SHIFT_MODIFIERS]):
            self.text_buffer.append(new_char.upper())
        else:
            self.text_buffer.append(new_char)

        self.onUpdate()
        return


class QuirkSettingsMgr(object):

    def __init__(self):
        super().__init__()
        self.quirks = dict()
        self.refresh()

    def refresh(self):
        if not glob.glob("*.yaml"):
            makeDemoYaml()
        for yamlfile in glob.glob("*.yaml"):
            name = yamlfile.replace(".yaml", "")
            with open(yamlfile, "r", encoding="utf-8") as fp:
                try:
                    obj = yaml.safe_load(fp.read())
                    assert obj
                except Exception:
                    logger.error("Bad yaml file %s", yamlfile, exc_info=True)
                    continue
                for name, rules in obj.items():
                    self.addRules(name, rules, yamlfile)

    def addRules(self, name, rules, yamlfile="?"):
        self.quirks[name] = rules
        try:
            for (pattern, repl) in self.getRuleList(name):
                re.sub(pattern, repl, "")
        except (re.error, KeyError):
            logger.error("Error compiling rules for %s:%s", yamlfile, name, exc_info=True)
            logger.error("Removing name %s", name)
            self.quirks.pop(name)

    def getQuirkNames(self):
        return list(self.quirks.keys())

    def getRuleList(self, name):
        rule_list = self.quirks.get(name)
        return [(a, b) for a, b in rule_list.items()]

    def makeRulesStr(self, name):
        rulestrs = []
        for i, rule in enumerate(self.getRuleList(name)):
            rulestrs.append("{}. '{}' -> '{}'".format(i + 1, rule[0], rule[1]))
        return "\n".join(rulestrs)

    def getPostProcessor(self, name):
        def _pp(string):
            what = string
            for (pattern, repl) in self.getRuleList(name):
                what = re.sub(pattern, repl, what)
            return what
        return _pp


class QuirkGui(tk.Tk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.str_buffer = tk.StringVar()
        self.str_preview = tk.StringVar()
        self.str_rules = tk.StringVar()
        self.str_demo = tk.StringVar()

        self.opt_mdescape = tk.BooleanVar()
        self.opt_mdcodeblock = tk.BooleanVar()

        self.postProcessor = lambda s: s

        self.settings = QuirkSettingsMgr()
        self.listener = KeyListener(onUpdate=self.onUpdate, postProcess=self.doPostProcess)

        self.initwindow()

        self.mainloop()

    def initwindow(self):
        """Initialize widgets for the window
        """
        # self.geometry("400x200")

        cur_row = 0

        def nextRow():
            nonlocal cur_row
            cur_row += 1
            return cur_row

        @contextmanager
        def frameRow():
            thisframe = tk.Frame(self)
            try:
                yield thisframe
            finally:
                thisframe.grid(row=nextRow(), sticky="w")

        self.frame_preview = tk.Frame(self)

        with frameRow() as frame:

            tk.Label(frame, text="Input: ").grid(row=0, column=0)
            self.lab_buffer = tk.Label(frame, textvariable=self.str_buffer, font=("Default", 24))
            self.lab_buffer.grid(row=0, column=1)

            tk.Label(frame, text="Output: ").grid(row=1, column=0)
            self.lab_preview = tk.Label(frame, textvariable=self.str_preview, font=("Default", 24))
            self.lab_preview.grid(row=1, column=1)

        with frameRow() as frame:
            tk.Label(frame, text="Start typing: '{}'".format(self.listener.toggle_hotkey)).grid(row=0)
            tk.Label(frame, text="Stop typing: 'enter', 'esc'").grid(row=1)

        with frameRow() as frame:

            self.cb_quirkpicker = ttk.Combobox(frame, state="readonly", takefocus=False)
            self.cb_quirkpicker.configure(values=self.settings.getQuirkNames())
            self.cb_quirkpicker.bind("<<ComboboxSelected>>", self.onQuirkChange)
            self.cb_quirkpicker.grid(row=2, column=0, sticky="ew")

        with frameRow() as frame:

            settings_popup = tk.Menu(self, tearoff=0)

            settings_popup.add_checkbutton(label="Markdown escape", variable=self.opt_mdescape, command=self.onQuirkChange)
            settings_popup.add_checkbutton(label="Markdown fences", variable=self.opt_mdcodeblock, command=self.onQuirkChange)

            settings_popup.add_separator()
            settings_popup.add_command(label="Refresh", command=self.refresh)

            btn_settings = ttk.Button(frame, text="Settings", takefocus=False)
            btn_settings.bind("<Button-1>", lambda event: settings_popup.tk_popup(event.x_root, event.y_root, 0))
            btn_settings.grid(row=3)

        with frameRow() as frame:
            
            tk.Label(frame, text="Demo Input: ").grid(row=0, column=0)
            self.lab_buffer = tk.Label(frame, text="The quick brown fox jumped over the angry dog")
            self.lab_buffer.grid(row=0, column=1)

            tk.Label(frame, text="Demo Output: ").grid(row=1, column=0)
            self.lab_preview = tk.Label(frame, textvariable=self.str_demo)
            self.lab_preview.grid(row=1, column=1)

            tk.Label(frame, text="Active Rules: ").grid(row=2, column=0, sticky="n")
            tk.Label(frame, textvariable=self.str_rules, justify="left").grid(row=2, column=1)

        self.attributes("-topmost", True)

    def refresh(self):
        self.settings.refresh()
        self.cb_quirkpicker.configure(values=self.settings.getQuirkNames())

    def onUpdate(self):
        buffer = self.listener.getBufferStr()
        preview = self.listener.getPreviewStr()
        self.str_buffer.set(buffer)
        self.str_preview.set(preview)

    def onQuirkChange(self, event=None):
        new_quirk_name = self.cb_quirkpicker.get()
        self.postProcessor = self.settings.getPostProcessor(new_quirk_name)
        self.str_rules.set(self.settings.makeRulesStr(new_quirk_name))
        self.onUpdate()
        self.makeDemoStr()

    def makeDemoStr(self, in_="The quick brown fox jumped over the angry dog"):
        out = self.doPostProcess(in_)
        self.str_demo.set(out)

    def doPostProcess(self, string):
        str = self.postProcessor(string)
        if self.opt_mdcodeblock.get():
            str = "`" + str + "`"
        elif self.opt_mdescape.get():
            str = re.sub(r"([|*>])", r"\\\g<1>", str)
        return str


if __name__ == "__main__":
    QuirkGui()
