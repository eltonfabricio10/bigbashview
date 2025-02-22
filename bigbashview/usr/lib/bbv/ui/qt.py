# -*- coding: utf-8 -*-
#
#  Copyright (C) 2008 Wilson Pinto Júnior <wilson@openlanhouse.org>
#  Copyright (C) 2011 Thomaz de Oliveira dos Reis <thor27@gmail.com>
#  Copyright (C) 2009-2024  Bruno Goncalves Araujo
#  Copyright (C) 2021 Elton Fabrício Ferreira <eltonfabricio10@gmail.com>
#
#  This file contains the implementation of a Qt-based UI for the BigBashView application.
#  It provides a window with a web view and various features such as download handling,
#  page inspection, and window customization.
#
#  The code is divided into several sections:
#  1. Importing necessary modules and packages
#  2. Setting up translations for internationalization
#  3. Defining the main window class
#  4. Implementing various methods for handling events and functionality
#  5. Running the application
#
#  The main window class, Window, inherits from QWidget and contains the following features:
#  - A QWebEngineView widget for displaying web content
#  - A QWebEngineView widget for inspecting web pages
#  - Shortcuts for reloading the web page and opening the developer tools
#  - A QSplitter widget for dividing the window into two panes
#  - Methods for handling download requests and feature permissions
#  - Methods for customizing the window appearance and behavior
#  - Methods for setting the window title and loading URLs
#  - Methods for managing the window size and position
#  - Methods for setting the window background color
#
#  The Window class also includes a main method, run, which starts the application event loop.
#
#  Note: This code is licensed under the GNU General Public License version 3 or later.
#  For more details, see http://www.gnu.org/licenses/

import sys
import os
from PySide6.QtCore import QUrl, Qt, QObject, Slot, Signal, QEvent
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSplitter, QApplication, QFileDialog
from PySide6.QtGui import QIcon, QColor, QKeySequence, QShortcut, QDesktopServices
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineDownloadRequest
from PySide6.QtWebChannel import QWebChannel

from bbv.globaldata import TITLE, PROCESS, EXTERNAL_LINK

# Import gettext module for translations
import gettext
lang_translations = gettext.translation(
    "bigbashview",
    localedir="/usr/share/locale",
    fallback=True
)
lang_translations.install()

# Define _ shortcut for translations
_ = lang_translations.gettext

# WindowControl class for handling window state changes and interactions
# between the web view and the main window, using signals and slots
# acessible from JavaScript code in the web page
# used in csd mode (client side decoration)
class WindowControl(QObject):
    windowStateChanged = Signal(str)  # Definição do sinal

    def __init__(self, window):
        super().__init__()
        self.window = window

    @Slot()
    def minimize(self):
        self.window.showMinimized()

    @Slot()
    def maximize(self):
        if not self.window.isMaximized():
            self.window.showMaximized()
        else:
            self.window.showNormal()

    @Slot(result=bool)
    def isMaximized(self):
        return self.window.isMaximized()

    @Slot()
    def close(self):
        self.window.close()

    @Slot()
    def moveWindow(self):
        if self.window.windowHandle():
            self.window.windowHandle().startSystemMove()

    @Slot(str)
    def resizeWindowBy(self, resizeRegion):
        edge = Qt.Edge(0)
        if 'left' in resizeRegion:
            edge |= Qt.LeftEdge
        if 'right' in resizeRegion:
            edge |= Qt.RightEdge
        if 'top' in resizeRegion:
            edge |= Qt.TopEdge
        if 'bottom' in resizeRegion:
            edge |= Qt.BottomEdge

        if edge and self.window.windowHandle():
            self.window.windowHandle().startSystemResize(edge)

class LinkOpener(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            # Abre o link clicado no navegador padrão do sistema
            QDesktopServices.openUrl(url.toString())
            return False  # Impede que o QWebEngineView siga o link
        return True  # Permite outras navegações, como redirecionamentos

class Window(QWidget):
    def __init__(self):
        # Initialize the application and web view
        self.app = QApplication(sys.argv)
        super().__init__()
        self.web = QWebEngineView()
        self.web.page().profile().setHttpUserAgent("BigBashView-Agent")
        self.inspector = QWebEngineView()

        # Set window title        
        self.app.setDesktopFileName(PROCESS)

        if TITLE:
            self.app.setApplicationName(TITLE)
            self.setWindowTitle(TITLE)
        else:
            self.web.titleChanged.connect(self.title_changed)

        if EXTERNAL_LINK:
            self.web.setPage(LinkOpener(self))

        # Connect various signals to their respective slots
        self.web.page().windowCloseRequested.connect(self.close_window)
        self.web.page().featurePermissionRequested.connect(self.onFeature)
        self.web.loadFinished.connect(self.add_script)
        self.key_f5 = QShortcut(QKeySequence(Qt.Key_F5), self.web)
        self.key_f5.activated.connect(self.web.reload)
        self.key_f12 = QShortcut(QKeySequence(Qt.Key_F12), self.web)
        self.key_f12.activated.connect(self.devpage)
        self.web.page().profile().downloadRequested.connect(self.onDownloadRequested)
        
        # Meta+Alt+S Keyboard shortcut for run orca
        self.key_meta_alt_s = QShortcut(QKeySequence("Meta+Alt+S"), self)
        self.key_meta_alt_s.activated.connect(self.run_orca)

        # Set up the layout and splitter for the main window
        self.hbox = QHBoxLayout(self)
        self.hbox.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.web)
        self.splitter2 = QSplitter(Qt.Horizontal)
        self.hbox.addWidget(self.splitter)
        self.setLayout(self.hbox)

        # Add control and channel for web interaction, to be used in csd mode
        self.control = WindowControl(self)
        self.channel = QWebChannel()
        self.web.page().setWebChannel(self.channel)
        self.channel.registerObject("windowControl", self.control)

    def run_orca(self):
        try:
            # Use pgrep to check if there are any running processes named 'orca'
            process_check = os.system("pgrep orca > /dev/null 2>&1")
            
            if process_check == 0:  # If pgrep returns 0, the Orca process is running
                os.system("bigbashview-orca --disable &")
                print("Orca process terminated.")
            else:
                os.system("bigbashview-orca --enable &")  # Start the Orca process in the background
                print("Orca process started.")
        except Exception as e:
            # Handle any exceptions that occur while managing the Orca process
            print(f"Error handling the Orca process: {e}")


    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.WindowStateChange:
            if self.isMaximized():
                self.control.windowStateChanged.emit('maximized')
            elif self.windowState() == Qt.WindowNoState:
                self.control.windowStateChanged.emit('normal')

    def onDownloadRequested(self, download: QWebEngineDownloadRequest):
        # Handle download requests by showing a file dialog for saving the file
        home_directory = os.path.expanduser('~')
        save_path, _ = QFileDialog.getSaveFileName(self, download.suggestedFileName(), os.path.join(home_directory, download.suggestedFileName()))
        if save_path:
            save_directory = os.path.dirname(save_path)
            save_filename = os.path.basename(save_path)
            download.setDownloadDirectory(save_directory)
            download.setDownloadFileName(save_filename)
            download.accept()

    def onFeature(self, url, feature):
        # Handle feature permission requests by granting or denying the requested feature
        if feature in (
            QWebEnginePage.Feature.MediaAudioCapture,
            QWebEnginePage.Feature.MediaVideoCapture,
            QWebEnginePage.Feature.MediaAudioVideoCapture,
        ):
            self.web.page().setFeaturePermission(
                url,
                feature,
                QWebEnginePage.PermissionGrantedByUser
            )
        else:
            self.web.page().setFeaturePermission(
                url,
                feature,
                QWebEnginePage.PermissionDeniedByUser
            )

    def devpage(self):
        # Toggle between displaying the web view and the inspector view in the splitter
        if self.splitter.count() == 1 or self.splitter2.count() == 1:
            self.inspector.page().setInspectedPage(self.web.page())
            self.splitter2.hide()
            self.splitter.addWidget(self.web)
            self.splitter.addWidget(self.inspector)
            self.splitter.setSizes([(int(self.width()/3))*2, int(self.width()/3)])
            self.splitter.show()
            self.hbox.addWidget(self.splitter)
            self.setLayout(self.hbox)
        else:
            self.splitter.hide()
            self.splitter2.addWidget(self.web)
            self.splitter2.show()
            self.hbox.addWidget(self.splitter2)
            self.setLayout(self.hbox)

    def add_script(self, event):
        # Add a JavaScript function to the web page for executing commands
        script = """
        function _run(run){
            // Step 1: instantiate the abort controller
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 1000);

            // Step 2: make the fetch() aware of controller.signal
            fetch('/execute$'+run, { signal: controller.signal });
        };
        """
        if event:
            self.web.page().runJavaScript(script)

    def viewer(self, window_state):
        # Set the window state based on the provided argument
        if window_state == "maximized":
            self.setWindowState(Qt.WindowMaximized)
        elif window_state == "fullscreen":
            self.setWindowState(Qt.WindowFullScreen)
        elif window_state == "frameless":
            self.setWindowFlags(Qt.FramelessWindowHint)
        elif window_state == "alwaystop":
            self.setWindowFlags(Qt.WindowStaysOnTopHint)
        elif window_state == "framelesstop":
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        elif window_state == "maximizedframelesstop":
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.setWindowState(Qt.WindowMaximized)
        self.show()

    def run(self):
        # Start the application event loop
        self.app.exec_()

    def close_window(self):
        # Quit the application when the window is closed
        self.app.quit()

    def title_changed(self, title):
        # Set the window title
        self.setWindowTitle(title)

    def load_url(self, url):
        # Load the specified URL in the web view
        self.url = QUrl.fromEncoded(url.encode("utf-8"))
        self.web.load(self.url)

    def set_size(self, width, height, window_state, min_width, min_height):
        # Set the window size and position based on the provided arguments
        display = self.app.primaryScreen()
        if display is None:
            width = 1024
            height = 600
        else:
            size = display.availableGeometry()
            if width <= 0:
                width = int(size.width() / 2)
            if height <= 0:
                height = int(size.height() / 2)

        self.setMinimumSize(min_width, min_height)
        self.resize(width, height)
        if window_state == "fixed":
            self.setFixedSize(width, height)

    def set_icon(self, icon):
        # Tentar carregar o ícone do tema do sistema
        icon_system = QIcon.fromTheme(icon)
        # Verificar se o ícone carregado é válido
        if icon_system.isNull():
            # Se o ícone não for válido, usar um ícone de fallback
            icon = "bigbashview"
            
        #Set window icon
        self.setWindowIcon(QIcon.fromTheme(icon))

    def style(self, colorful):
        # Set the window background color based on the provided argument
        if colorful == 'black':
            self.web.page().setBackgroundColor(QColor.fromRgbF(0, 0, 0, 1))
        elif colorful == "transparent":
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.web.page().setBackgroundColor(QColor.fromRgbF(0, 0, 0, 0))
            self.setStyleSheet("background:transparent;")
        elif os.environ.get('XDG_CURRENT_DESKTOP') == 'KDE':
            rgb = os.popen("kreadconfig5 --group WM --key activeBackground").read().split(',')

            if len(rgb) > 1:
                r, g, b = rgb if len(rgb) == 3 else rgb[:-1]
                r = float(int(r)/255)
                g = float(int(g)/255)
                b = float(int(b)/255)
                self.web.page().setBackgroundColor(QColor.fromRgbF(r, g, b, 1))
            else:
                self.web.page().setBackgroundColor(QColor.fromRgbF(0, 0, 0, 0))
        else:
            self.web.page().setBackgroundColor(QColor.fromRgbF(0, 0, 0, 0))
