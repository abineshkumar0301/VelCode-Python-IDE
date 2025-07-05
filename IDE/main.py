import sys
import re
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QPlainTextEdit,
    QTabWidget, QSplitter, QDockWidget, QWidget, QVBoxLayout,
    QFileDialog, QTextEdit, QSplashScreen
)
from PyQt6.QtGui import (
    QFileSystemModel, QAction, QKeySequence, QTextCursor,
    QFont, QPainter, QColor, QTextFormat, QIcon, QTextCharFormat, QSyntaxHighlighter, QPixmap, QShortcut
)
from PyQt6.QtCore import Qt, QDir, QRect, QSize, QProcess, QTimer

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return self.code_editor.line_number_area_size()

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)

class Highlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#F176DC"))
        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue', 'del', 'elif',
            'else', 'except', 'False', 'finally', 'for', 'from', 'global', 'if', 'import', 'in',
            'is', 'lambda', 'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True',
            'try', 'while', 'with', 'yield', 'self'
        ]
        for word in keywords:
            self.rules.append((re.compile(rf'\b{word}\b'), keyword_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#DB9758"))
        self.rules.append((re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|".*?"|\'.*?\')'), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#4BA154"))
        self.rules.append((re.compile(r'#.*'), comment_format))

        function_call_format = QTextCharFormat()
        function_call_format.setForeground(QColor("#F7FCA3"))
        self.rules.append((re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=\()'), function_call_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#8ECEF8"))
        self.rules.append((re.compile(r'\b\d+(\.\d+)?\b'), number_format))

        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#FFB86C"))
        self.rules.append((re.compile(r'[+\-*/%=<>!&|^~]+'), operator_format))

        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#8BE9FD"))
        self.rules.append((re.compile(r'\bclass\s+(\w+)'), class_format))

        decorator_format = QTextCharFormat()
        decorator_format.setForeground(QColor("#FF5555"))
        self.rules.append((re.compile(r'@\w+'), decorator_format))

        def_format = QTextCharFormat()
        def_format.setForeground(QColor("#5C7CF0"))
        self.rules.append((re.compile(r'\bdef\b'), def_format))

        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#FF9F43"))
        self.rules.append((re.compile(r'\bself\b'), self_format))

        builtin_format = QTextCharFormat()
        builtin_format.setForeground(QColor("#00D2D3"))
        self.rules.append((re.compile(r'\b(print|len|range|input|str|int|float|bool|list|dict|set|tuple|open|super|type)\b'), builtin_format))

        const_format = QTextCharFormat()
        const_format.setForeground(QColor("#FFD700"))
        const_format.setFontWeight(QFont.Weight.Bold)
        self.rules.append((re.compile(r'\b(True|False|None)\b'), const_format))

        bracket_format = QTextCharFormat()
        bracket_format.setForeground(QColor("#F6FF00"))
        self.rules.append((re.compile(r'[()\[\]{}]'), bracket_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                try:
                    start, end = match.span(1) if pattern.pattern.startswith(r'\bclass') or pattern.pattern.startswith(r'\bdef') else match.span()
                except IndexError:
                    start, end = match.span()
                self.setFormat(start, end - start, fmt)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setFont(QFont("Consolas", 12))
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.highlighter = Highlighter(self.document())

        self.line_number_area = LineNumberArea(self)
        self.update_line_number_area_width(0)

    def line_number_area_size(self):
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return QSize(space, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_size().width(), cr.height()))

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_size().width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        bg_color = QColor(30, 30, 30)
        fg_color = Qt.GlobalColor.lightGray
        painter.fillRect(event.rect(), bg_color)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(fg_color)
                painter.drawText(
                    0, top,
                    self.line_number_area.width() - 5,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(40, 40, 60))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)

    def keyPressEvent(self, event):
        key = event.text()
        cursor = self.textCursor()
        pairs = {'(': ')', '{': '}', '[': ']', '"': '"', "'": "'"}

        if key in pairs:
            cursor.insertText(key + pairs[key])
            cursor.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(cursor)

        elif event.key() == Qt.Key.Key_Return:
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            current_line = cursor.selectedText()
            indent = ""
            for ch in current_line:
                if ch in [' ', '\t']:
                    indent += ch
                else:
                    break
            should_indent_more = current_line.strip().endswith((':', '{'))
            super().keyPressEvent(event)
            self.insertPlainText(indent + ('    ' if should_indent_more else ''))

        elif event.key() == Qt.Key.Key_Tab:
            self.insertPlainText('    ')

        elif event.key() == Qt.Key.Key_Backtab:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
            if cursor.selectedText() == '    ':
                cursor.removeSelectedText()

        else:
            super().keyPressEvent(event)

class PythonIDE(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vel Code")
        self.setGeometry(100, 100, 1000, 700)
        self.showMaximized()
        self.init_ui()
        self.init_shortcuts()
        self.apply_dark_theme()

    def init_ui(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        self.output_console = QPlainTextEdit()
        self.output_console.setReadOnly(False)
        self.output_console.setFont(QFont("Consolas", 11))
        self.output_console.installEventFilter(self)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.on_output)
        self.process.readyReadStandardError.connect(self.on_output)

        self.tree = QTreeView()
        self.model = QFileSystemModel()
        self.model.setRootPath(QDir.currentPath())
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(QDir.currentPath()))
        self.tree.doubleClicked.connect(self.open_file_from_tree)

        self.tree.setColumnHidden(1, True)
        self.tree.setColumnHidden(2, True)
        self.tree.setColumnHidden(3, True)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.tab_widget)
        self.splitter.setSizes([200, 800])

        central_widget = QWidget()
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(self.splitter)
        self.setCentralWidget(central_widget)

        self.output_dock = QDockWidget("Output", self)
        self.output_dock.setWidget(self.output_console)
        self.output_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)

        self.init_menu()
        self.new_file()

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        run_menu = menubar.addMenu("Run")
        view_menu = menubar.addMenu("View")

        file_menu.addAction(QAction("New", self, triggered=self.new_file))
        file_menu.addAction(QAction("Open", self, triggered=self.open_file))
        file_menu.addAction(QAction("Save", self, triggered=self.save_file))
        run_menu.addAction(QAction("Run", self, triggered=self.run_code))

        self.view_terminal_action = QAction("Terminal", self, checkable=True)
        self.view_terminal_action.setChecked(True)
        self.view_terminal_action.triggered.connect(self.toggle_terminal)
        self.output_dock.visibilityChanged.connect(self.view_terminal_action.setChecked)
        view_menu.addAction(self.view_terminal_action)

    def toggle_terminal(self):
        self.output_dock.setVisible(self.view_terminal_action.isChecked())

    def init_shortcuts(self):
        for keys, action in [
            ("Ctrl+S", self.save_file),
            ("Ctrl+Return", self.run_code),
            ("Ctrl+N", self.new_file),
            ("Ctrl+O", self.open_file),
            ("Ctrl+W", lambda: self.close_tab(self.tab_widget.currentIndex()))
        ]:
            QShortcut(QKeySequence(keys), self).activated.connect(action)

    def new_file(self):
        editor = CodeEditor()
        self.tab_widget.addTab(editor, "untitled")
        self.tab_widget.setCurrentWidget(editor)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Python Files (*.py)")
        if path:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            editor = CodeEditor()
            editor.setPlainText(content)
            editor.file_path = path
            self.tab_widget.addTab(editor, os.path.basename(path))
            self.tab_widget.setCurrentWidget(editor)

    def open_file_from_tree(self, index):
        path = self.model.filePath(index)
        if path.endswith(".py"):
            with open(path, 'r') as f:
                content = f.read()
            editor = CodeEditor()
            editor.setPlainText(content)
            editor.file_path = path
            for i in range(self.tab_widget.count()):
                if getattr(self.tab_widget.widget(i), 'file_path', None) == path:
                    self.tab_widget.setCurrentIndex(i)
                    return
            self.tab_widget.addTab(editor, os.path.basename(path))
            self.tab_widget.setCurrentWidget(editor)

    def save_file(self):
        editor = self.tab_widget.currentWidget()
        if hasattr(editor, 'file_path'):
            path = editor.file_path
        else:
            path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Python Files (*.py)")
            if not path:
                return
            editor.file_path = path

        with open(editor.file_path, 'w') as f:
            f.write(editor.toPlainText())
        self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(editor.file_path))

    def run_code(self):
        editor = self.tab_widget.currentWidget()
        code = editor.toPlainText()
        if not hasattr(editor, 'file_path') or not editor.file_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save File Before Running", "", "Python Files (*.py)")
            if not path:
                return
            editor.file_path = path
            with open(path, 'w', encoding='utf-8') as f:
                f.write(code)
            self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(path))
        else:
            with open(editor.file_path, 'w', encoding='utf-8') as f:
                f.write(code)

        full_path = os.path.abspath(editor.file_path)
        cwd = os.path.dirname(full_path)
        powershell_line = f'PS {cwd}> python -u "{full_path}"\n'
        self.output_console.insertPlainText(powershell_line)

        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
        self.process.start("python", ["-u", full_path])

    def on_output(self):
        text = self.process.readAllStandardOutput().data().decode()
        self.output_console.moveCursor(QTextCursor.MoveOperation.End)
        self.output_console.insertPlainText(text)

    def eventFilter(self, obj, event):
        if obj is self.output_console and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return:
                cursor = self.output_console.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
                line = cursor.selectedText()
                last_prompt_index = line.rfind(">")
                user_input = line[last_prompt_index + 1:].strip() if last_prompt_index != -1 else line.strip()
                self.output_console.appendPlainText("")
                self.process.write((user_input + '\n').encode())
                return True
        return super().eventFilter(obj, event)

    def close_tab(self, index):
        self.tab_widget.removeTab(index)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QPlainTextEdit, QTextEdit {
                background: #1e1e1e;
                color: #dcdcdc;
            }
            QTreeView {
                background: #2b2b2b;
                color: #cfcfcf;
            }
            QTabWidget::pane { border: 1px solid #444; }
            QDockWidget {
                background: #2b2b2b;
                color: #dcdcdc;
            }
            QDockWidget::title {
                background: #2d2d2d;
                padding: 4px;
                font-weight: bold;
            }
            QMenuBar, QMenu, QAction {
                background-color: #2b2b2b;
                color: #ffffff;
            }
        """)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    splash_pix = QPixmap("IDE_Logo.png").scaled(480, 480)
    splash = QSplashScreen(splash_pix)
    splash.show()
    QTimer.singleShot(5000, splash.close)
    window = PythonIDE()
    window.setWindowIcon(QIcon("IDE_Logo.png"))
    window.show()
    sys.exit(app.exec())
