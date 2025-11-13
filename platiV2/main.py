import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import webbrowser
from operator import itemgetter
import time
import re
import yaml
import requests
from playwright.sync_api import sync_playwright

class Products:
    data = []

    def read_yaml_file(self, filename):
        """Read the data from a YAML file and return a list of dictionaries"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                self.data = yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            self.data = []

    def write_yaml_file(self, filename):
        """Write the data in YAML format to a file"""
        with open(filename, 'w', encoding='utf-8') as file:
            yaml.dump(self.data, file)

    def sortProducts(self, criteria: str, order: bool = False):
        """Sort list of products by given criteria"""
        self.data.sort(key=itemgetter(criteria), reverse=order)

    def printData(self):
        for item in self.data:
            print(f"{item['name']}\t{item['link']}\n{item['price']}  {item['rating']}   {item['sold']}\n\n")

    def ParsePage(self, query):
        """Find all elements on page and store them into the dictionary using Playwright (DEPRECATED IN FAVOR OF API)"""
        self.data = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            q = requests.utils.quote(query)
            url = f"https://plati.market/search/{q}"
            page.goto(url)
            time.sleep(1)

            try:
                if page.locator('#gdpr_accept_button').is_visible():
                    page.locator('#gdpr_accept_button').click()
            except:
                pass

            while True:
                try:
                    allBlocks = page.locator('li.shadow').all()
                    if not allBlocks:
                        break
                    page_number_element = page.locator('a.active').nth(1)
                    if not page_number_element.is_visible():
                        break
                    pageNumber = int(page_number_element.inner_text())
                except:
                    print("Результаты не найдены")
                    break

                for block in allBlocks:
                    BlockTitle = block.locator('h1')
                    BlockName = BlockTitle.locator('a')
                    BlockLink = BlockName.get_attribute('href')
                    BlockPrice = BlockTitle.locator('span')
                    price_text = BlockPrice.inner_text()
                    RubPrice_match = re.search(r" [0-9]+ ", price_text)
                    RubPrice = int(RubPrice_match.group(0)) if RubPrice_match else 0
                    BlockInfo = block.locator("strong").all()
                    BlockRating = float(BlockInfo[0].inner_text().replace(',', '.'))
                    try:
                        BlockSold = int(BlockInfo[1].inner_text().replace('>', ''))
                    except (IndexError, ValueError):
                        BlockSold = 0
                    self.data.append({
                        'name': BlockName.inner_text(),
                        'link': "https://plati.market" + BlockLink,
                        'price': RubPrice,
                        'rating': BlockRating,
                        'sold': BlockSold
                    })
                try:
                    next_page_link = page.get_by_role("link", name=str(pageNumber + 1))
                    if next_page_link.is_visible():
                        next_page_link.click()
                        page.wait_for_load_state('networkidle')
                    else:
                        break
                except:
                    break
            browser.close()


    def parseAPI(self, query):
        """Find all elements on page and store them into the dictionary using plati.ru API"""
        self.data = []
        pagesize = 499
        try:
            contents = requests.get(f"https://plati.io/api/search.ashx?query={query}&pagesize={pagesize}&visibleOnly=true&response=json").json()
            total_pages = int(contents['Totalpages'])
            for entry in contents['items']:
                self.data.append({
                    'name': entry['name'],
                    'link': entry['url'],
                    'price': int(entry['price_rur']),
                    'rating': float(entry['seller_rating']),
                    'sold': int(entry['numsold'])
                })
            if total_pages > 1:
                for i in range(2, total_pages + 1):
                    contents = requests.get(f"https://plati.io/api/search.ashx?query={query}&pagesize={pagesize}&pagenum={i}&visibleOnly=true&response=json").json()
                    for entry in contents['items']:
                        self.data.append({
                            'name': entry['name'],
                            'link': entry['url'],
                            'price': int(entry['price_rur']),
                            'rating': float(entry['seller_rating']),
                            'sold': int(entry['numsold'])
                        })
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")


class App:
    def __init__(self, title):
        self.title = title
        self.window = None
        self.product = Products()
        self.filePath = "cache.yaml"
        self.data = []
        self.order = 0
        self.table = None

    def create_window(self):
        self.window = tk.Tk()
        self.window.title(self.title)
        self.window.geometry("720x480")

        self.product.read_yaml_file(self.filePath)
        self.data = self.product.data

        label = tk.Label(self.window, text="Input what you like to find in the field below\nDouble click on the result to open it in external browser")
        label.pack(pady=5)

        self.text_field = tk.Entry(self.window, width=50)
        self.text_field.pack(side=tk.TOP, pady=5)
        update_button = tk.Button(self.window, text="Search", command=self.search)
        update_button.pack(pady=5)
        
        self.table = MyListbox(self.window, self.data)
        self.table.create_treeview()
        self.table.update_treeview(self.data)

        self.window.mainloop()

    def update_window(self):
        self.product.read_yaml_file(self.filePath)
        self.data = self.product.data
        if not self.table:
            self.table = MyListbox(self.window, self.data)
            self.table.create_treeview()
        self.table.update_treeview(self.data)

    def search(self):
        self.product.parseAPI(self.text_field.get())
        self.product.write_yaml_file(self.filePath)
        self.update_window()

class MyListbox:
    def __init__(self, master, items):
        self.master = master
        self.items = items
        self.treeview = None
        self.columns = ["name", "price", "rating", "sold"]
        self.sort_column = None
        self.sort_descending = False

    def create_treeview(self):
        self.treeview = ttk.Treeview(self.master, columns=self.columns, show="headings", selectmode="browse")

        for column in self.columns:
            self.treeview.heading(column, text=column.capitalize(), anchor=tk.CENTER, command=lambda c=column: self.sort_by_column(c))
            self.treeview.column(column, anchor=tk.CENTER)

        self.treeview.bind("<Double-1>", self.open_link)
        self.treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    def autosize_columns(self):
        for col in self.columns:
            max_len = tkFont.Font().measure(col.title())
            for item in self.treeview.get_children():
                cell_value = self.treeview.set(item, col)
                cell_len = tkFont.Font().measure(cell_value)
                if cell_len > max_len:
                    max_len = cell_len
            self.treeview.column(col, width=max_len + 20)

    def sort_by_column(self, column):
        if self.sort_column == column:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column
            self.sort_descending = False
        
        if column in ['price', 'rating', 'sold']:
            self.items.sort(key=lambda x: float(x[self.sort_column]), reverse=self.sort_descending)
        else:
            self.items.sort(key=lambda x: str(x[self.sort_column]), reverse=self.sort_descending)

        self.update_treeview(self.items)

    def update_treeview(self, data):
        self.items = data
        self.treeview.delete(*self.treeview.get_children())
        for item in self.items:
            self.treeview.insert("", tk.END, values=(item['name'], item['price'], item['rating'], item['sold']), tags=(item['link'],))
        self.autosize_columns()

    def open_link(self, event):
        if not self.treeview.selection():
            return
        item = self.treeview.selection()[0]
        link = self.treeview.item(item, "tags")[0]
        webbrowser.open(link)

def main():
    my_window = App("Plati.market Parser")
    my_window.create_window()

if __name__ == "__main__":
    main()