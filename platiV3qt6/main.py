import sys
import pickle
import requests
import webbrowser
import concurrent.futures
from operator import itemgetter

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLineEdit, QPushButton, QTableView, QHeaderView)
from PyQt6.QtCore import (QObject, QThread, pyqtSignal, QAbstractTableModel, 
                          Qt, QSortFilterProxyModel)

# ======================================================================================
# Класс для работы с данными (без изменений)
# ======================================================================================
class Products:
    data = []
    def read_cache_file(self, filename):
        try:
            with open(filename, 'rb') as file: self.data = pickle.load(file)
        except (FileNotFoundError, EOFError): self.data = []

    def write_cache_file(self, filename):
        with open(filename, 'wb') as file: pickle.dump(self.data, file)

    def _fetch_page(self, query, pagenum):
        try:
            url = f"https://plati.io/api/search.ashx?query={query}&pagesize=499&pagenum={pagenum}&visibleOnly=true&response=json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            contents = response.json()
            return [{'name': entry['name'], 'link': entry['url'], 'price': int(entry['price_rur']),
                     'rating': float(entry['seller_rating']), 'sold': int(entry['numsold'])}
                    for entry in contents.get('items', [])]
        except requests.RequestException: return None

    def parseAPI(self, query):
        self.data = []
        url = f"https://plati.io/api/search.ashx?query={query}&pagesize=499&visibleOnly=true&response=json"
        try:
            contents = requests.get(url).json()
            total_pages = int(contents.get('Totalpages', 0))
            self.data.extend(self._parse_items(contents))
            if total_pages > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                    futures = [executor.submit(self._fetch_page, query, i) for i in range(2, total_pages + 1)]
                    for future in concurrent.futures.as_completed(futures):
                        if page_items := future.result(): self.data.extend(page_items)
        except requests.RequestException: pass
        return self.data
        
    def _parse_items(self, contents):
        return [{'name': entry['name'], 'link': entry['url'], 'price': int(entry['price_rur']),
                 'rating': float(entry['seller_rating']), 'sold': int(entry['numsold'])}
                for entry in contents.get('items', [])]

# ======================================================================================
# Потоковый рабочий для выполнения сетевых запросов (без изменений)
# ======================================================================================
class Worker(QObject):
    finished = pyqtSignal(list)
    def __init__(self, query):
        super().__init__()
        self.products = Products()
        self.query = query

    def run(self):
        result = self.products.parseAPI(self.query)
        self.products.data = result
        self.products.write_cache_file("cache.dat")
        self.finished.emit(result)

# ======================================================================================
# Модель данных для таблицы (без изменений)
# ======================================================================================
class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data
        self.headers = ["name", "price", "rating", "sold"]

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            column_key = self.headers[index.column()]
            return self._data[index.row()].get(column_key)
        return None

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self.headers)

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section].capitalize()
        return None
        
    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        column_key = self.headers[column]
        is_numeric = column_key in ['price', 'rating', 'sold']
        try:
            self._data.sort(key=lambda x: float(x.get(column_key, 0)) if is_numeric else str(x.get(column_key, '')),
                            reverse=(order == Qt.SortOrder.DescendingOrder))
        except (ValueError, TypeError):
            pass
        self.layoutChanged.emit()

# ======================================================================================
# Главное окно приложения
# ======================================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plati.market Parser")
        self.setGeometry(100, 100, 800, 600)

        p = Products()
        p.read_cache_file("cache.dat")
        self.initial_data = p.data

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название товара...")
        self.search_button = QPushButton("Search")
        self.table = QTableView()
        
        self.model = TableModel(self.initial_data)
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.model)
        self.table.setModel(self.proxy_model)
        
        self.table.setSortingEnabled(True)
        
        # ========================================================================
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ ИЗМЕНЕНИЯ ЗДЕСЬ ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # ========================================================================
        
        # ЗАМЕНА РЕЖИМА РАСТЯГИВАНИЯ НА ИНТЕРАКТИВНЫЙ
        # Старая строка: self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        self.table.setAlternatingRowColors(True)

        # ДОБАВЛЕНО: Начальная подгонка размера колонок по содержимому
        self.table.resizeColumnsToContents()

        # ========================================================================
        # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        # ========================================================================

        layout = QVBoxLayout()
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_button)
        layout.addWidget(self.table)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.search_button.clicked.connect(self.start_search)
        self.table.doubleClicked.connect(self.open_link)
        
        self.thread = None
        self.worker = None

    def start_search(self):
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        self.thread = QThread()
        self.worker = Worker(self.search_input.text())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.search_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def search_finished(self, data):
        self.model.update_data(data)
        self.table.resizeColumnsToContents() # Эта строка также важна для обновления размеров после поиска
        self.search_button.setEnabled(True)
        self.search_button.setText("Search")

    def open_link(self, index):
        proxy_index = self.proxy_model.mapToSource(index)
        link = self.model._data[proxy_index.row()].get('link')
        if link:
            webbrowser.open(link)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())