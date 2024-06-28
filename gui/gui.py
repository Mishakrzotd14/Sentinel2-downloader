import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import geopandas as gpd
import tkcalendar as tkc
from shapely.geometry import box

from api.dataspace_api import download_sentinel_images
from gui.gui_utils import ConsoleRedirect


class MainGUI:
    def __init__(self, root):
        self.root = root
        self.create_widgets()

    def create_widgets(self):
        # Title label
        self.frame = ctk.CTkScrollableFrame(master=self.root, scrollbar_button_color="#1f6aa5", orientation="vertical")
        self.frame.pack(pady=10, padx=60, fill="both", expand=True)

        self.label = ctk.CTkLabel(
            master=self.frame, text="Модуль загрузки снимков Sentinel-2", font=ctk.CTkFont(family="Roboto", size=18)
        )
        self.label.pack(pady=25, padx=5)

        self.login_frame = LoginFrame(self.frame, self.toggle_secret_key)
        self.login_frame.pack(pady=2, padx=10)

        self.deadline_entry = DateEntryFrame(self.frame, self.show_calendar_first, self.show_calendar_second)
        self.deadline_entry.pack(pady=5, padx=5)

        self.shpfile_entry = ShapefileEntryFrame(self.frame, self.open_shapefile, self.open_geojsonfile)
        self.shpfile_entry.pack(pady=5, padx=5)

        self.slider_entry_frame = SliderEntryFrame(self.frame)
        self.slider_entry_frame.pack(pady=5, padx=5)

        self.path_download_frame = PathDownloadFrame(self.frame, self.directory)
        self.path_download_frame.pack(pady=5, padx=5)

        self.button_download = ctk.CTkButton(
            master=self.frame,
            text="Скачать",
            command=lambda: threading.Thread(target=self.button_callback, daemon=True).start(),
            font=("Roboto", 14),
        )
        self.button_download.pack(pady=10, padx=10)

        self.setings_frame = SettingsFrame(self.root, self.change_appearance_mode_event, self.change_scaling_event)
        self.setings_frame.pack(side="bottom", pady=10)

    def change_scaling_event(self, event):
        self.setings_frame.change_scaling_event(event)

    def change_appearance_mode_event(self, event):
        self.setings_frame.change_appearance_mode_event(event)

    def toggle_secret_key(self):
        self.login_frame.toggle_secret_key()

    def show_calendar_first(self):
        self.deadline_entry.show_calendar_first()

    def show_calendar_second(self):
        self.deadline_entry.show_calendar_second()

    def update_selected_date_first(self):
        self.deadline_entry.update_selected_date_first()

    def update_selected_date_second(self):
        self.deadline_entry.update_selected_date_second()

    def open_shapefile(self):
        self.shpfile_entry.open_shapefile()

    def open_geojsonfile(self):
        self.shpfile_entry.open_geojsonfile()

    def directory(self):
        self.path_download_frame.directory()

    def button_callback(self):
        console = ConsoleRedirect()

        text = ctk.CTkTextbox(master=self.frame, width=900, height=200)
        text.pack(pady=5, padx=10, fill=tk.NONE, expand=False)

        text.configure(font=("serif", 13), spacing1=10)
        console.RedirectTextBox(text)
        sys.stdout = console

        platform = "SENTINEL-2"
        level = "S2MSI2A"

        s3_access_key = self.login_frame.get_access_key()
        s3_secret_key = self.login_frame.get_secret_key()

        if not s3_access_key or not s3_secret_key:
            messagebox.showerror("Ошибка", "Введите Access Key и Secret Key")
            return

        try:
            date_first = str(self.deadline_entry.calendar_first.get_date().strftime("%Y-%m-%d"))
            date_second = str(self.deadline_entry.calendar_second.get_date().strftime("%Y-%m-%d"))
            if date_first > date_second:
                messagebox.showerror("Ошибка", "Начальная дата не может быть позже конечной даты")
                return
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при получении дат: {str(e)}")
            return

        try:
            cloud_percent = self.slider_entry_frame.progress
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при получении процента облачности: {str(e)}")
            return

        try:
            shapefile = self.shpfile_entry.get_shapefile()
            bounds = shapefile.total_bounds
            footprint = box(bounds[0], bounds[1], bounds[2], bounds[3]).wkt
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при обработке файла формы: {str(e)}")
            return

        try:
            dir_download = self.path_download_frame.get_selected_directory()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при получении директории: {str(e)}")
            return

        try:
            grid = gpd.read_file(
                os.path.join(os.path.dirname(__file__), "sentinel2_grid", "sentinel_2_index_shapefile.shp")
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при чтении файла сетки: {str(e)}")
            return

        query_parameters = {
            "setillite": platform,
            "producttype": level,
            "cloud_percentage": cloud_percent,
            "footprint": footprint,
            "date_start": date_first,
            "date_end": date_second,
        }

        try:
            download_sentinel_images(
                s3_access_key, s3_secret_key, query_parameters, grid, shapefile, dir_download, self.frame
            )
            print("Все спутниковые снимки Sentinel-2 загружены!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке снимков: {str(e)}")
        finally:
            sys.stdout = ConsoleRedirect()
            sys.stderr = ConsoleRedirect()


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, toggle_secret_key):
        super().__init__(master)

        self.label_name = ctk.CTkLabel(master=self, text="Access Key", font=("Roboto", 15))
        self.label_name.grid(row=0, column=0, padx=10, pady=2)

        self.entry_name = ctk.CTkEntry(master=self, placeholder_text="access key", font=("Roboto", 13))
        self.entry_name.grid(row=1, column=0, padx=10, pady=2)

        self.label_pass = ctk.CTkLabel(master=self, text="Secret Key", font=("Roboto", 15))
        self.label_pass.grid(row=0, column=1, padx=10, pady=2)

        self.entry_pass = ctk.CTkEntry(master=self, placeholder_text="secret key", show="*")
        self.entry_pass.grid(row=1, column=1, padx=10, pady=2)

        self.button_pass = ctk.CTkButton(
            master=self, text="Показать secret key", command=toggle_secret_key, font=("Roboto", 13)
        )
        self.button_pass.grid(row=2, column=1, padx=10, pady=2)

    def toggle_secret_key(self):
        if self.entry_pass.cget("show") == "*":
            self.entry_pass.configure(show="")
        else:
            self.entry_pass.configure(show="*")

    def get_access_key(self):
        return self.entry_name.get()

    def get_secret_key(self):
        return self.entry_pass.get()


class DateEntryFrame(ctk.CTkFrame):
    def __init__(self, master, show_calendar_first, show_calendar_second):
        super().__init__(master)

        self.label_date_first = ctk.CTkLabel(master=self, text="Начальная дата", font=("Roboto", 15))
        self.label_date_first.grid(row=0, column=0, padx=30, pady=2)

        self.calendar_first = tkc.DateEntry(
            self, width=12, borderwidth=2, font=("roboto", 10), date_pattern="YYYY-MM-DD"
        )
        self.show_calendar_btn_first = ctk.CTkButton(
            self, text="Дата", command=show_calendar_first, font=("Roboto", 13)
        )
        self.show_calendar_btn_first.grid(row=1, column=0, padx=30, pady=2)

        self.selected_date_label_first = ctk.CTkLabel(self, text="Дата не выбрана", font=("Roboto", 14))
        self.selected_date_label_first.grid(row=2, column=0, padx=30, pady=2)

        self.label_date_second = ctk.CTkLabel(master=self, text="Конечная дата", font=("Roboto", 15))
        self.label_date_second.grid(row=0, column=1, padx=30, pady=2)

        self.calendar_second = tkc.DateEntry(
            self, width=12, borderwidth=2, font=("roboto", 10), date_pattern="YYYY-MM-DD"
        )
        self.show_calendar_btn_second = ctk.CTkButton(
            self, text="Дата", command=show_calendar_second, font=("Roboto", 13)
        )
        self.show_calendar_btn_second.grid(row=1, column=1, padx=30, pady=2)

        self.selected_date_label_second = ctk.CTkLabel(self, text="Дата не выбрана", font=("Roboto", 14))
        self.selected_date_label_second.grid(row=2, column=1, padx=30, pady=2)

    def show_calendar_first(self):
        self.calendar_first.drop_down()
        self.calendar_first.bind("<<DateEntrySelected>>", lambda event: self.update_selected_date_first())

    def show_calendar_second(self):
        self.calendar_second.drop_down()
        self.calendar_second.bind("<<DateEntrySelected>>", lambda event: self.update_selected_date_second())

    def update_selected_date_first(self):
        selected_date = self.calendar_first.get_date()
        self.selected_date_label_first.configure(text=selected_date.strftime("%Y-%m-%d"))

    def update_selected_date_second(self):
        selected_date = self.calendar_second.get_date()
        self.selected_date_label_second.configure(text=selected_date.strftime("%Y-%m-%d"))


class SliderEntryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.progress = 0

        self.progressbar_label = ctk.CTkLabel(master=self, text="Процент облачности: 0%", font=("Roboto", 15))
        self.progressbar_label.grid(row=0, column=0, padx=5, pady=2)

        self.slider = ctk.CTkSlider(master=self, command=self.slider_callback)
        self.slider.minimum = 0
        self.slider.maximum = 100
        self.slider.grid(row=1, column=0, padx=10, pady=2)
        self.slider.set(0)

        self.entry = ctk.CTkEntry(master=self, width=40, font=("Roboto", 15))
        self.entry.grid(row=1, column=1, padx=5, pady=2)
        self.entry.bind("<Return>", lambda event: self.entry_callback())

    def slider_callback(self, value):
        self.progress = round(float(value) * 100)
        self.progressbar_label.configure(text=f"Процент облачности: {self.progress} %")

    def entry_callback(self):
        try:
            value = int(self.entry.get())
            if value < self.slider.minimum:
                value = self.slider.minimum
            elif value > self.slider.maximum:
                value = self.slider.maximum
            progress = value / 100
            self.slider.set(progress)
            self.slider_callback(progress)
        except ValueError:
            pass  # Обработка процента облачности


class ShapefileEntryFrame(ctk.CTkTabview):
    def __init__(self, master, open_shapefile, open_geojsonfile):
        super().__init__(master, height=30)
        self.shapefile = None
        self.geojsonfile = None
        self.crs_file = "epsg:4326"

        self.add("Shapefile")
        self.add("GeoJson")
        self.tab("Shapefile").grid_columnconfigure(0, weight=1)
        self.tab("GeoJson").grid_columnconfigure(0, weight=1)

        self.create_shapefile_tab(open_shapefile)
        self.create_geojson_tab(open_geojsonfile)

    def create_shapefile_tab(self, open_shapefile):
        label_find_shp = ctk.CTkLabel(master=self.tab("Shapefile"), text="Найти Shapefile: ", font=("Roboto", 15))
        label_find_shp.grid(row=0, column=0, padx=20, pady=2)

        search_button_shp = ctk.CTkButton(
            self.tab("Shapefile"), text="Shapefile", command=open_shapefile, font=("Roboto", 13)
        )
        search_button_shp.grid(row=0, column=2, padx=10, pady=10)

        self.entry_find_shp = ctk.CTkLabel(master=self.tab("Shapefile"), text="Файл не загружен", font=("Roboto", 15))
        self.entry_find_shp.grid(row=0, column=1, padx=10, pady=10)

    def create_geojson_tab(self, open_geojsonfile):
        label_find_geojson = ctk.CTkLabel(master=self.tab("GeoJson"), text="Найти GeoJson file: ", font=("Roboto", 15))
        label_find_geojson.grid(row=0, column=0, padx=20, pady=2)

        search_button_geojson = ctk.CTkButton(
            self.tab("GeoJson"), text="GeoJson", command=open_geojsonfile, font=("Roboto", 13)
        )
        search_button_geojson.grid(row=0, column=2, padx=10, pady=10)

        self.entry_find_geojson = ctk.CTkLabel(master=self.tab("GeoJson"), text="Файл не загружен", font=("Roboto", 15))
        self.entry_find_geojson.grid(row=0, column=1, padx=10, pady=10)

    def open_shapefile(self):
        file_path = filedialog.askopenfilename(filetypes=[("Shapefile", "*.shp")])
        if file_path:
            shp_file = gpd.read_file(file_path)
            if shp_file.crs != self.crs_file:
                shp_file.to_crs(self.crs_file, inplace=True)
            self.shapefile = shp_file
            self.geojsonfile = None
            self.entry_find_shp.configure(text=os.path.basename(file_path))

    def open_geojsonfile(self):
        file_path = filedialog.askopenfilename(filetypes=[("GeoJSON", "*.geojson")])
        if file_path:
            geojson_file = gpd.read_file(file_path)
            if geojson_file.crs != self.crs_file:
                geojson_file.to_crs(self.crs_file, inplace=True)
            self.geojsonfile = geojson_file
            self.shapefile = None
            self.entry_find_geojson.configure(text=os.path.basename(file_path))

    def get_shapefile(self):
        if self.shapefile is None and self.geojsonfile is None:
            raise ValueError("No shapefile or GeoJSON file selected.")
        return self.shapefile if self.shapefile is not None else self.geojsonfile


class PathDownloadFrame(ctk.CTkFrame):
    def __init__(self, master, directory):
        super().__init__(master)

        self.label_path = ctk.CTkLabel(master=self, text="Сохранить в папку:", font=("Roboto", 15))
        self.label_path.grid(row=0, column=0, padx=20, pady=2)

        self.path_button = ctk.CTkButton(self, text="Папка", command=directory, font=("Roboto", 13))
        self.path_button.grid(row=0, column=2, padx=10, pady=10)

        self.entry_path = ctk.CTkLabel(master=self, text="Папка не выбрана", font=("Roboto", 15))
        self.entry_path.grid(row=0, column=1, padx=10, pady=10)

    def directory(self):
        files_save = filedialog.askdirectory()
        self.master.save_dir = files_save
        if self.master.save_dir:
            self.entry_path.configure(text=self.master.save_dir)
        else:
            messagebox.showerror("Error", "Папка не выбрана")

    def get_selected_directory(self):
        return self.master.save_dir


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, change_appearance_mode_event, change_scaling_event):
        super().__init__(master)

        # Darck mode
        self.optionemenu = ctk.CTkOptionMenu(
            self, values=["Dark", "Light", "System"], command=change_appearance_mode_event, font=("Roboto", 13)
        )
        self.optionemenu.set("Dark")
        self.optionemenu.grid(row=0, column=1, padx=10, pady=1)

        self.scaling_optionemenu = ctk.CTkOptionMenu(
            self, values=["80%", "90%", "100%", "110%", "120%"], command=change_scaling_event, font=("Roboto", 13)
        )
        self.scaling_optionemenu.set("100%")
        self.scaling_optionemenu.grid(row=0, column=2, padx=10, pady=1)

    def change_scaling_event(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace("%", "")) / 100
        ctk.set_widget_scaling(new_scaling_float)

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
