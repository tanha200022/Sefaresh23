# -*- coding: utf-8 -*-
"""
اپلیکیشن مدیریت سفارشات (شرکت‌ها و کالاها) - Kivy
ذخیره‌سازی محلی روی گوشی (JSON) + خروجی عکس از لیست + پشتیبان‌گیری/بازیابی
"""
import os
import json
import time
import datetime

from kivy.app import App
from kivy.lang import Builder
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.filechooser import FileChooserListView
from kivy.metrics import dp
from kivy.utils import platform

import arabic_reshaper
from bidi.algorithm import get_display

APP_NAME = "orderapp"

# ---------- RTL helper ----------
def rtl(text):
    """Reshape + reorder Persian/Arabic text so Kivy renders it correctly (RTL)."""
    if not text:
        return ""
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception:
        return str(text)


# ---------- Jalali (Shamsi) date ----------
def to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    jy = 0 if gy <= 1600 else 979
    gy -= 621 if gy <= 1600 else 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    jm = 1 + (days // 31) if days < 186 else 7 + ((days - 186) // 30)
    jd = 1 + (days % 31 if days < 186 else (days - 186) % 30)
    return jy, jm, jd


def today_jalali():
    t = datetime.date.today()
    y, m, d = to_jalali(t.year, t.month, t.day)
    return f"{y}/{m:02d}/{d:02d}"


# ---------- number formatting ----------
def fmt_num(value):
    try:
        return "{:,}".format(int(value))
    except Exception:
        return str(value)


def unfmt(text):
    try:
        return int(str(text).replace(",", "").strip() or 0)
    except Exception:
        return 0


# ---------- data storage ----------
def data_file():
    app = App.get_running_app()
    folder = app.user_data_dir if app else "."
    return os.path.join(folder, "orders_data.json")


class DB:
    def __init__(self):
        self.companies = []
        self.products = []
        self.load()

    def load(self):
        path = data_file()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.companies = data.get("companies", [])
                    self.products = data.get("products", [])
            except Exception:
                self.companies, self.products = [], []
        else:
            self.companies, self.products = [], []

    def save(self):
        path = data_file()
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"companies": self.companies, "products": self.products}, f, ensure_ascii=False, indent=2)

    def add_company(self, name, visitor, phone):
        cid = str(int(time.time() * 1000))
        self.companies.append({"id": cid, "name": name, "visitor": visitor, "phone": phone})
        self.save()
        return cid

    def add_or_update_product(self, pid, company_id, fields):
        if pid:
            for p in self.products:
                if p["id"] == pid:
                    p.update(fields)
                    break
        else:
            pid = str(int(time.time() * 1000))
            fields["id"] = pid
            fields["companyId"] = company_id
            fields["createdAt"] = time.time()
            self.products.append(fields)
        self.save()

    def delete_product(self, pid):
        self.products = [p for p in self.products if p["id"] != pid]
        self.save()

    def products_for(self, company_id, query="", date_filter=""):
        items = [p for p in self.products if p["companyId"] == company_id]
        if query:
            q = query.lower()
            items = [p for p in items if q in p.get("name", "").lower() or q in p.get("desc", "").lower()]
        if date_filter:
            items = [p for p in items if date_filter in p.get("date", "")]
        items.sort(key=lambda p: p.get("createdAt", 0), reverse=True)
        return items

    def restore(self, data):
        self.companies = data.get("companies", [])
        self.products = data.get("products", [])
        self.save()


# ---------- UI ----------
KV = """
#:import dp kivy.metrics.dp
"""


class RTLLabel(Label):
    def __init__(self, text="", **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.halign = "right"
        self.valign = "middle"
        self.markup = True
        self.text = rtl(text)
        self.bind(size=lambda *a: setattr(self, "text_size", self.size))


class RTLButton(Button):
    def __init__(self, text="", **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.text = rtl(text)


class RTLTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Vazir"
        self.halign = "right"
        self.base_direction = "rtl"


def product_card(p, on_edit, on_delete):
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(190),
                     padding=dp(10), spacing=dp(4))
    with box.canvas.before:
        from kivy.graphics import Color, RoundedRectangle
        Color(0.13, 0.15, 0.18, 1)
        rect = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(12)])
    def upd(*_):
        rect.pos = box.pos
        rect.size = box.size
    box.bind(pos=upd, size=upd)

    top = BoxLayout(size_hint_y=None, height=dp(30))
    top.add_widget(RTLLabel(text=p.get("name", ""), bold=True, font_size="18sp"))
    buy = p.get("buy", 0) or 0
    use = p.get("use", 0) or 0
    pct = ((use - buy) / buy * 100) if buy else 0
    pct_lbl = RTLLabel(text=f"{pct:+.1f}٪", size_hint_x=0.3,
                        color=(0.24, 0.86, 0.52, 1) if pct >= 0 else (1, 0.36, 0.42, 1))
    top.add_widget(pct_lbl)
    box.add_widget(top)

    box.add_widget(RTLLabel(text=f"تاریخ تحویل: {p.get('date','-')}", font_size="14sp",
                             color=(0.6, 0.65, 0.7, 1), size_hint_y=None, height=dp(20)))
    grid = GridLayout(cols=2, size_hint_y=None, height=dp(60))
    grid.add_widget(RTLLabel(text=f"قیمت خرید: {fmt_num(buy)}", font_size="15sp"))
    grid.add_widget(RTLLabel(text=f"قیمت مصرف: {fmt_num(use)}", font_size="15sp"))
    grid.add_widget(RTLLabel(text=f"مدت تسویه: {p.get('settle',0)} روز", font_size="15sp"))
    grid.add_widget(RTLLabel(text=f"تعداد کارتن: {p.get('carton',0)}", font_size="15sp"))
    box.add_widget(grid)

    actions = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(8))
    edit_btn = RTLButton(text="ویرایش")
    edit_btn.bind(on_release=lambda *_: on_edit(p))
    del_btn = RTLButton(text="حذف", background_color=(0.9, 0.3, 0.35, 1))
    del_btn.bind(on_release=lambda *_: on_delete(p))
    actions.add_widget(edit_btn)
    actions.add_widget(del_btn)
    box.add_widget(actions)
    return box


class OrderApp(App):
    def build(self):
        LabelBase.register(name="Vazir", fn_regular="assets/fonts/Vazirmatn-Regular.ttf")
        Window.clearcolor = (0.06, 0.08, 0.09, 1)
        self.db = DB()
        self.current_company = None

        root = BoxLayout(orientation="vertical")

        header = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(140),
                            padding=dp(10), spacing=dp(8))
        header.add_widget(RTLLabel(text="مدیریت سفارشات", bold=True, font_size="22sp",
                                    size_hint_y=None, height=dp(30), halign="center"))

        row1 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.company_spinner = Spinner(text=rtl("— انتخاب شرکت —"), font_name="Vazir")
        self.company_spinner.bind(text=self.on_company_change)
        row1.add_widget(self.company_spinner)
        add_company_btn = RTLButton(text="افزودن شرکت", size_hint_x=0.5)
        add_company_btn.bind(on_release=lambda *_: self.open_company_popup())
        row1.add_widget(add_company_btn)
        header.add_widget(row1)

        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.search_input = RTLTextInput(hint_text=rtl("جستجوی کالا..."), multiline=False)
        self.search_input.bind(text=lambda *_: self.render_list())
        self.date_filter_input = RTLTextInput(hint_text=rtl("فیلتر تاریخ"), multiline=False, size_hint_x=0.5)
        self.date_filter_input.bind(text=lambda *_: self.render_list())
        settings_btn = RTLButton(text="⚙", size_hint_x=0.2)
        settings_btn.bind(on_release=lambda *_: self.open_backup_popup())
        row2.add_widget(self.search_input)
        row2.add_widget(self.date_filter_input)
        row2.add_widget(settings_btn)
        header.add_widget(row2)

        root.add_widget(header)

        self.scroll = ScrollView()
        self.list_box = GridLayout(cols=1, size_hint_y=None, spacing=dp(10), padding=dp(10))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        footer = BoxLayout(size_hint_y=None, height=dp(56), padding=dp(8), spacing=dp(8))
        add_product_btn = RTLButton(text="افزودن کالا")
        add_product_btn.bind(on_release=lambda *_: self.open_product_popup())
        export_btn = RTLButton(text="خروجی عکس", size_hint_x=0.6)
        export_btn.bind(on_release=lambda *_: self.export_image())
        footer.add_widget(add_product_btn)
        footer.add_widget(export_btn)
        root.add_widget(footer)

        self.refresh_company_spinner()
        self.render_list()
        return root

    # ---- companies ----
    def refresh_company_spinner(self):
        self.company_spinner.values = [rtl(c["name"]) for c in self.db.companies]

    def on_company_change(self, spinner, text):
        for c in self.db.companies:
            if rtl(c["name"]) == text:
                self.current_company = c["id"]
                break
        self.render_list()

    def open_company_popup(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        name_in = RTLTextInput(hint_text=rtl("نام شرکت"), multiline=False, size_hint_y=None, height=dp(44))
        visitor_in = RTLTextInput(hint_text=rtl("نام ویزیتور"), multiline=False, size_hint_y=None, height=dp(44))
        phone_in = RTLTextInput(hint_text=rtl("شماره تلفن ویزیتور"), multiline=False, size_hint_y=None, height=dp(44))
        box.add_widget(RTLLabel(text="افزودن شرکت", bold=True, size_hint_y=None, height=dp(30)))
        box.add_widget(name_in)
        box.add_widget(visitor_in)
        box.add_widget(phone_in)

        popup = Popup(title="", content=box, size_hint=(0.9, 0.55), separator_height=0)

        def save(*_):
            if not name_in.text.strip():
                return
            cid = self.db.add_company(name_in.text.strip(), visitor_in.text.strip(), phone_in.text.strip())
            self.current_company = cid
            self.refresh_company_spinner()
            self.company_spinner.text = rtl(name_in.text.strip())
            self.render_list()
            popup.dismiss()

        save_btn = RTLButton(text="ثبت", size_hint_y=None, height=dp(44))
        save_btn.bind(on_release=save)
        box.add_widget(save_btn)
        popup.open()

    # ---- products ----
    def open_product_popup(self, product=None):
        if not self.current_company:
            self._toast("ابتدا یک شرکت انتخاب کنید")
            return
        box = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        sv = ScrollView()
        inner = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_y=None)
        inner.bind(minimum_height=inner.setter("height"))

        name_in = RTLTextInput(hint_text=rtl("نام کالا"), multiline=False, size_hint_y=None, height=dp(44),
                                text=product.get("name", "") if product else "")
        buy_in = RTLTextInput(hint_text=rtl("قیمت خرید"), multiline=False, size_hint_y=None, height=dp(44),
                               input_filter="int",
                               text=str(product.get("buy", "")) if product else "")
        use_in = RTLTextInput(hint_text=rtl("قیمت مصرف"), multiline=False, size_hint_y=None, height=dp(44),
                               input_filter="int",
                               text=str(product.get("use", "")) if product else "")
        pct_lbl = RTLLabel(text="", size_hint_y=None, height=dp(24))

        def update_pct(*_):
            b, u = unfmt(buy_in.text), unfmt(use_in.text)
            pct = ((u - b) / b * 100) if b else 0
            pct_lbl.text = rtl(f"فاصله قیمت: {pct:+.1f}٪")
        buy_in.bind(text=update_pct)
        use_in.bind(text=update_pct)

        settle_in = RTLTextInput(hint_text=rtl("مدت تسویه (روز)"), multiline=False, size_hint_y=None, height=dp(44),
                                  input_filter="int", text=str(product.get("settle", "")) if product else "")
        carton_in = RTLTextInput(hint_text=rtl("تعداد سفارش (کارتن)"), multiline=False, size_hint_y=None, height=dp(44),
                                  input_filter="int", text=str(product.get("carton", "")) if product else "")
        date_in = RTLTextInput(hint_text=rtl("تاریخ تحویل (شمسی)"), multiline=False, size_hint_y=None, height=dp(44),
                                text=product.get("date", today_jalali()) if product else today_jalali())
        desc_in = RTLTextInput(hint_text=rtl("توضیحات"), multiline=True, size_hint_y=None, height=dp(90),
                                text=product.get("desc", "") if product else "")

        for w in [name_in, buy_in, use_in, pct_lbl, settle_in, carton_in, date_in, desc_in]:
            inner.add_widget(w)
        update_pct()
        sv.add_widget(inner)
        box.add_widget(RTLLabel(text="ویرایش کالا" if product else "افزودن کالا", bold=True,
                                 size_hint_y=None, height=dp(30)))
        box.add_widget(sv)

        popup = Popup(title="", content=box, size_hint=(0.92, 0.9), separator_height=0)

        def save(*_):
            if not name_in.text.strip():
                return
            fields = {
                "name": name_in.text.strip(),
                "buy": unfmt(buy_in.text),
                "use": unfmt(use_in.text),
                "settle": unfmt(settle_in.text),
                "carton": unfmt(carton_in.text),
                "date": date_in.text.strip(),
                "desc": desc_in.text.strip(),
            }
            pid = product.get("id") if product else None
            self.db.add_or_update_product(pid, self.current_company, fields)
            self.render_list()
            popup.dismiss()

        save_btn = RTLButton(text="ثبت", size_hint_y=None, height=dp(46))
        save_btn.bind(on_release=save)
        box.add_widget(save_btn)
        popup.open()

    def confirm_delete(self, product):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        box.add_widget(RTLLabel(text=f"«{product.get('name','')}» حذف شود؟"))
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        popup = Popup(title="", content=box, size_hint=(0.8, 0.3), separator_height=0)
        yes_btn = RTLButton(text="بله، حذف کن", background_color=(0.9, 0.3, 0.35, 1))
        no_btn = RTLButton(text="انصراف")

        def do_delete(*_):
            self.db.delete_product(product["id"])
            self.render_list()
            popup.dismiss()

        yes_btn.bind(on_release=do_delete)
        no_btn.bind(on_release=lambda *_: popup.dismiss())
        row.add_widget(yes_btn)
        row.add_widget(no_btn)
        box.add_widget(row)
        popup.open()

    def render_list(self):
        self.list_box.clear_widgets()
        if not self.current_company:
            self.list_box.add_widget(RTLLabel(text="شرکتی انتخاب نشده است.", size_hint_y=None, height=dp(60)))
            return
        items = self.db.products_for(self.current_company, self.search_input.text.strip(),
                                      self.date_filter_input.text.strip())
        if not items:
            self.list_box.add_widget(RTLLabel(text="کالایی ثبت نشده است.", size_hint_y=None, height=dp(60)))
            return
        for p in items:
            self.list_box.add_widget(product_card(p, self.open_product_popup, self.confirm_delete))

    # ---- backup / restore ----
    def open_backup_popup(self):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        box.add_widget(RTLLabel(text="پشتیبان‌گیری و بازیابی", bold=True, size_hint_y=None, height=dp(30)))
        backup_btn = RTLButton(text="دانلود فایل پشتیبان", size_hint_y=None, height=dp(44))
        backup_btn.bind(on_release=lambda *_: self._do_backup())
        box.add_widget(backup_btn)

        box.add_widget(RTLLabel(text="بازیابی از فایل:", size_hint_y=None, height=dp(24)))
        start_path = self.user_data_dir
        chooser = FileChooserListView(path=start_path, filters=["*.json"])
        box.add_widget(chooser)

        restore_btn = RTLButton(text="بازیابی از فایل انتخابی", size_hint_y=None, height=dp(44))
        popup = Popup(title="", content=box, size_hint=(0.95, 0.9), separator_height=0)

        def do_restore(*_):
            if not chooser.selection:
                return
            path = chooser.selection[0]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.db.restore(data)
                self.refresh_company_spinner()
                self.render_list()
                popup.dismiss()
            except Exception:
                self._toast("فایل نامعتبر است")

        restore_btn.bind(on_release=do_restore)
        box.add_widget(restore_btn)
        popup.open()

    def _do_backup(self):
        fname = f"backup-orders-{today_jalali().replace('/', '-')}.json"
        path = os.path.join(self.user_data_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"companies": self.db.companies, "products": self.db.products}, f,
                      ensure_ascii=False, indent=2)
        self._toast(f"ذخیره شد: {fname}")

    # ---- export image ----
    def export_image(self):
        if not self.current_company:
            self._toast("ابتدا یک شرکت انتخاب کنید")
            return
        fname = f"orders-{int(time.time())}.png"
        path = os.path.join(self.user_data_dir, fname)
        self.scroll.export_to_png(path)
        self._toast(f"عکس ذخیره شد: {fname}")

    def _toast(self, msg):
        popup = Popup(title="", content=RTLLabel(text=msg), size_hint=(0.8, 0.2),
                       separator_height=0, auto_dismiss=True)
        popup.open()
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: popup.dismiss(), 1.6)


if __name__ == "__main__":
    OrderApp().run()
