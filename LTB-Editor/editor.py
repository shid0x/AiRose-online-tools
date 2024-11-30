# editor.py

from PyQt5.QtWidgets import (
    QMainWindow, QAction, QFileDialog,
    QTableView, QVBoxLayout, QWidget,
    QHBoxLayout, QMessageBox, QComboBox, QLabel, QHeaderView, QInputDialog
)
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from ltb_file import LTBFile
import os
import shutil
from datetime import datetime
import logging
from typing import List  # Import List from typing
from PyQt5.QtWidgets import QLineEdit, QPushButton
from PyQt5.QtWidgets import QStyledItemDelegate, QPlainTextEdit, QWidget, QVBoxLayout
from PyQt5.QtWidgets import QStyledItemDelegate, QPlainTextEdit
from PyQt5.QtCore import Qt
import csv
from PyQt5.QtWidgets import QFileDialog, QMessageBox

class MultiLineDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setWordWrapMode(True)  # Enable word wrapping
        editor.setMinimumHeight(100)  # Set a minimum height for better visibility
        return editor

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole)
        editor.setPlainText(text if text else "")
        # Adjust the editor height dynamically based on text length
        lines = text.count("\n") + 1 if text else 1
        editor.setFixedHeight(min(200, max(100, lines * 20)))  # Adjust height based on line count

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        # Expand the editor slightly beyond the cell size for better visibility
        editor.setGeometry(option.rect.adjusted(-10, -10, 10, 10))

class LTBTableModel(QAbstractTableModel):
    def __init__(self, table_data: List[List[str]], headers: List[str], parent=None):
        super().__init__(parent)
        self.table_data = table_data
        self.headers = headers

    def rowCount(self, parent=QModelIndex()):
        return len(self.table_data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self.table_data[index.row()][index.column()]
        if role == Qt.ToolTipRole:
            return f"Row: {index.row() + 1}, Column: {self.headers[index.column()]}"
        return QVariant()

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            # Allow empty strings to clear the cell content
            if isinstance(value, str):
                self.table_data[index.row()][index.column()] = value.strip()  # Save even empty strings
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
        return False

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return QVariant()
        if orientation == Qt.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
            else:
                return f"Col {section}"
        return super().headerData(section, orientation, role)


from PyQt5.QtWidgets import QPushButton

class LTBEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LTB File Editor")
        self.resize(1200, 800)

        # Initialize LTBFile instance
        self.ltb = LTBFile()

        # Define which columns to display (0 and 2)
        self.display_columns = [0, 2]  # Adjust as needed

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Create encoding and search layout
        encoding_layout = QHBoxLayout()
        encoding_label = QLabel("Select Encoding:")
        encoding_layout.addWidget(encoding_label)

        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["utf-16le", "euc-kr"])
        self.encoding_combo.currentTextChanged.connect(self.change_encoding)
        encoding_layout.addWidget(self.encoding_combo)

        # Add search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self.filter_table)
        encoding_layout.addWidget(self.search_box)

        # Add clear search button
        self.clear_search_button = QPushButton("Clear")
        self.clear_search_button.clicked.connect(self.clear_search)
        encoding_layout.addWidget(self.clear_search_button)

        encoding_layout.addStretch()
        layout.addLayout(encoding_layout)

        # Add "Add Row" and "Generate Dialog" buttons
        button_layout = QHBoxLayout()  # Create a horizontal layout for the buttons

        # Add Row button
        self.add_row_button = QPushButton("Add Row")
        self.add_row_button.setFixedSize(100, 30)  # Set a fixed size for the button
        self.add_row_button.clicked.connect(self.add_row)
        button_layout.addWidget(self.add_row_button)

        # Generate Dialog button
        self.generate_dialog_button = QPushButton("Generate Dialog")
        self.generate_dialog_button.setFixedSize(120, 30)  # Set a fixed size for the button
        self.generate_dialog_button.clicked.connect(self.generate_dialogue)  # Connect to the existing method
        button_layout.addWidget(self.generate_dialog_button)

        button_layout.addStretch()  # Add stretch to push the buttons to the left (optional)
        layout.addLayout(button_layout)

        # Create table view
        self.table_view = QTableView()
        layout.addWidget(self.table_view)

        # Create status bar
        self.statusBar().showMessage("Ready")

        # Setup menu
        self.create_menu()

        # Initialize model as None
        self.model = None

    def add_row(self):
        """
        Adds a new row to the table with default values.
        """
        if not self.model:
            QMessageBox.warning(self, "Error", "No table to add a row. Import a file first.")
            return

        # Define default values for the new row
        new_row = [""] * len(self.display_columns)

        # Add the row to the model's data
        self.model.table_data.append(new_row)

        # Emit a signal to inform the view of the update
        self.model.layoutChanged.emit()

        # Scroll to the new row
        new_row_index = self.model.rowCount() - 1
        self.table_view.scrollTo(self.model.index(new_row_index, 0))

        self.statusBar().showMessage("Added a new row.")

    def filter_table(self):
        """
        Filters the table based on the search query.
        """
        query = self.search_box.text().strip().lower()
        if not self.model or not query:
            self.table_view.setModel(self.model)
            return

        filtered_data = []
        for row in self.model.table_data:
            # Check if any cell in the visible columns matches the query
            if any(query in (cell or "").lower() for cell in row):
                filtered_data.append(row)

        # Create a new model with filtered data
        headers = self.get_headers()
        filtered_model = LTBTableModel(filtered_data, headers)
        self.table_view.setModel(filtered_model)

        self.statusBar().showMessage(f"Filtered results for '{query}'")

    def clear_search(self):
        """
        Clears the search box and restores the original table view.
        """
        self.search_box.clear()
        self.table_view.setModel(self.model)
        self.statusBar().showMessage("Cleared search and restored full table.")

    def create_menu(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("File")

        import_action = QAction("Import LTB", self)
        import_action.triggered.connect(self.import_ltb)
        file_menu.addAction(import_action)

        export_action = QAction("Export LTB", self)
        export_action.triggered.connect(self.export_ltb)
        file_menu.addAction(export_action)

        # New: Add CSV import option
        import_csv_action = QAction("Import from CSV", self)
        import_csv_action.triggered.connect(self.import_from_csv)
        file_menu.addAction(import_csv_action)

        export_csv_action = QAction("Export to CSV", self)
        export_csv_action.triggered.connect(self.export_to_csv)
        file_menu.addAction(export_csv_action)

        export_column_action = QAction("Export Column to Text File", self)
        export_column_action.triggered.connect(self.export_column_to_text)
        file_menu.addAction(export_column_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def export_column_to_text(self):
        """
        Exports the content of a selected column to a text file.
        """
        if not self.model:
            QMessageBox.warning(self, "Export Error", "No table loaded. Please import a file first.")
            return

        # Prompt user to select the column
        headers = self.get_headers()
        column, ok = QInputDialog.getItem(
            self,
            "Select Column",
            "Choose a column to export:",
            headers,
            0,  # Default selection is the first column
            False
        )

        if not ok:
            return  # User canceled

        # Determine the column index
        column_index = headers.index(column)

        # Collect data from the selected column
        column_data = [self.model.table_data[row][column_index] for row in range(self.model.rowCount())]

        # Prompt user to save the file
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Column to Text File",
            "",
            "Text Files (*.txt);;All Files (*)",
            options=options
        )

        if not file_path:
            return  # User canceled

        try:
            # Write the column data to the text file
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write("\n".join(column_data))

            QMessageBox.information(self, "Export Successful", f"Column '{column}' exported to {file_path}")
            self.statusBar().showMessage(f"Exported column '{column}' to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export column to text file:\n{str(e)}")

    def change_encoding(self, encoding: str):
        if self.ltb.rows > 0 and self.ltb.columns > 0:
            reply = QMessageBox.question(
                self,
                "Change Encoding",
                "Changing encoding will reload the current file. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                current_file = getattr(self, 'current_file', None)
                if current_file:
                    try:
                        self.ltb = LTBFile.read(current_file, encoding=encoding)
                        self.populate_table()
                        self.statusBar().showMessage(f"Reloaded {current_file} with encoding {encoding}")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Failed to reload LTB file with {encoding} encoding:\n{str(e)}")
            else:
                # Revert the combo box to previous encoding
                if encoding == 'utf-16le':
                    self.encoding_combo.blockSignals(True)
                    self.encoding_combo.setCurrentText('utf-16le')
                    self.encoding_combo.blockSignals(False)
                elif encoding == 'euc-kr':
                    self.encoding_combo.blockSignals(True)
                    self.encoding_combo.setCurrentText('euc-kr')
                    self.encoding_combo.blockSignals(False)

    def import_ltb(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import LTB File",
            "",
            "LTB Files (*.ltb);;All Files (*)",
            options=options
        )
        if file_path:
            try:
                encoding = self.encoding_combo.currentText()
                self.ltb = LTBFile.read(file_path, encoding=encoding)
                self.current_file = file_path  # Store current file path
                self.populate_table()
                self.statusBar().showMessage(f"Imported {file_path} with encoding {encoding}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import LTB file:\n{str(e)}")

    def export_ltb(self):
        if self.ltb.columns == 0 or self.ltb.rows == 0:
            QMessageBox.warning(self, "Export Error", "No data to export. Please import and edit an LTB file first.")
            return

        # Validate Dialog IDs
        if not self.validate_unique_dialog_ids():
            return

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export LTB File",
            "",
            "LTB Files (*.ltb);;All Files (*)",
            options=options
        )
        if file_path:
            try:
                backup_path = None  # Initialize backup_path

                # Create backup if file exists
                if os.path.exists(file_path):
                    backup_path = f"{file_path}.backup_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    shutil.copyfile(file_path, backup_path)
                    logging.info(f"Backup created at {backup_path}")  # Replace with logging if preferred

                # Confirm overwrite
                if os.path.exists(file_path):
                    reply = QMessageBox.question(
                        self,
                        "Overwrite Confirmation",
                        f"The file '{file_path}' already exists and has been backed up.\nDo you want to overwrite it?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return

                # Extract updated table data from the model
                updated_table_data = self.extract_table_data()

                # Update the row count in LTBFile
                self.ltb.rows = len(updated_table_data)

                # Write back to the specified file with updates
                self.ltb.write_with_update(file_path, updated_table_data, self.display_columns)

                # Prepare the success message
                if backup_path:
                    success_message = f"File exported successfully to {file_path}\nBackup created at {backup_path}"
                else:
                    success_message = f"File exported successfully to {file_path}"

                # Show information message
                QMessageBox.information(self, "Export Successful", success_message)
                self.statusBar().showMessage(f"Exported to {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export LTB file:\n{str(e)}")

    def populate_table(self):
        # Debugging statements
        logging.info("Available attributes in LTBFile: %s", dir(self.ltb))
        logging.info("Type of self.ltb: %s", type(self.ltb))

        table_data = self.ltb.to_string_table(self.display_columns)  # Ensure no space here
        if not table_data:
            self.model = None
            self.table_view.setModel(None)
            return
        headers = self.get_headers()
        self.model = LTBTableModel(table_data, headers)
        self.table_view.setModel(self.model)

        # Enable sorting
        self.table_view.setSortingEnabled(True)

        # Resize columns to fit content
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table_view.horizontalHeader().setStretchLastSection(True)

        # Update UI
        self.table_view.resizeRowsToContents()
        self.statusBar().showMessage("Table populated successfully.")

        # Set the custom delegate for multi-line editing
        delegate = MultiLineDelegate()
        self.table_view.setItemDelegate(delegate)

    def extract_table_data(self) -> List[List[str]]:
        """
        Extracts the edited data from the table.
        Returns a list of lists containing the data for selected columns.
        """
        table_data = self.model.table_data if self.model else []
        return table_data

    def get_headers(self) -> List[str]:
        """
        Retrieve headers for the selected columns.
        Modify this method if you have specific header names.
        """
        headers = []
        for col in self.display_columns:
            if col == 0:
                headers.append("Dialog ID")
            elif col == 2:
                headers.append("English Dialogue")
            else:
                headers.append(f"Col {col}")
        return headers

    def validate_unique_dialog_ids(self) -> bool:
        dialog_ids = set()
        duplicates = set()
        try:
            dialog_id_col = self.display_columns.index(0)  # Assuming column 0 is "Dialog ID"
        except ValueError:
            QMessageBox.critical(
                self,
                "Configuration Error",
                "Dialog ID column is not in the display columns."
            )
            return False

        for row in range(self.model.rowCount() if self.model else 0):
            index = self.model.index(row, dialog_id_col)
            dialog_id = self.model.data(index, Qt.DisplayRole).strip()
            if not dialog_id:
                continue  # Skip empty Dialog IDs
            if dialog_id in dialog_ids:
                duplicates.add(dialog_id)
            else:
                dialog_ids.add(dialog_id)

        if duplicates:
            QMessageBox.critical(
                self,
                "Validation Error",
                f"Duplicate Dialog IDs found: {', '.join(duplicates)}. Please ensure all Dialog IDs are unique."
            )
            return False

        return True

    def export_to_csv(self):
        """
        Exports selected columns (e.g., Dialog ID and English language) to a CSV file.
        """
        if not self.model:
            QMessageBox.warning(self, "Export Error", "No table loaded. Please import a file first.")
            return

        # Prompt the user to select a file path
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=options
        )
        if not file_path:
            return  # User canceled the dialog

        try:
            # Determine indices for Dialog ID and English language columns
            dialog_id_index = self.display_columns.index(0)  # Column 0: Dialog ID
            english_index = self.display_columns.index(2)  # Column 2: English Dialogue

            # Extract the data from the model
            data_to_export = [
                [self.model.table_data[row][dialog_id_index], self.model.table_data[row][english_index]]
                for row in range(self.model.rowCount())
            ]

            # Write the data to a CSV file
            with open(file_path, mode='w', encoding='utf-8', newline='') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(["Dialog ID", "English Dialogue"])  # Header row
                writer.writerows(data_to_export)

            QMessageBox.information(self, "Export Successful", f"Data exported successfully to {file_path}")
            self.statusBar().showMessage(f"Exported data to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export data to CSV:\n{str(e)}")

    def import_from_csv(self):
        """
        Imports data from a CSV file and updates columns 0 (Dialog ID) and 2 (English Dialogue).
        """
        if not self.model:
            QMessageBox.warning(self, "Import Error", "No table loaded. Please import a file first.")
            return

        # Prompt the user to select a CSV file
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=options
        )
        if not file_path:
            return  # User canceled the dialog

        try:
            with open(file_path, mode='r', encoding='utf-8') as csv_file:
                reader = csv.reader(csv_file)
                header = next(reader, None)  # Read the header row

                # Validate CSV structure
                if header is None or len(header) < 2 or header[0].lower() != "dialog id" or header[
                    1].lower() != "english dialogue":
                    QMessageBox.critical(self, "Import Error",
                                         "Invalid CSV format. Ensure the first two columns are 'Dialog ID' and 'English Dialogue'.")
                    return

                # Read the CSV data into a list
                csv_data = list(reader)

                # Check if the CSV has more rows than the table
                if len(csv_data) > self.model.rowCount():
                    QMessageBox.warning(
                        self,
                        "Row Mismatch",
                        f"The CSV contains {len(csv_data)} rows, but the table has {self.model.rowCount()} rows. Extra rows in the CSV will be ignored."
                    )

                # Update the table with CSV data
                for row_index, row in enumerate(csv_data):
                    if row_index >= self.model.rowCount():
                        break  # Stop if the CSV has more rows than the table
                    if len(row) < 2:
                        continue  # Skip rows with insufficient columns
                    dialog_id_index = self.display_columns.index(0)
                    english_index = self.display_columns.index(2)

                    self.model.table_data[row_index][dialog_id_index] = row[0]  # Update Dialog ID
                    self.model.table_data[row_index][english_index] = row[1]  # Update English Dialogue

                # Notify the model of data changes
                self.model.layoutChanged.emit()
                self.statusBar().showMessage("Imported data from CSV successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import data from CSV:\n{str(e)}")

    def generate_dialogue(self):
        """
        Generates a dialogue for the selected NPC based on its role and name.
        """
        selected_indexes = self.table_view.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please select at least one NPC to generate dialogue.")
            return

        # First, ask user which model to use
        model_choice, ok = QInputDialog.getItem(
            self,
            "Select Model",
            "Choose the model for dialogue generation:",
            ["GPT-4", "AiRose Assistant"],  # Rename here
            0,  # Default to GPT-4
            False  # Non-editable
        )
        if not ok:
            return

        use_assistant = model_choice == "AiRose Assistant"

        # Iterate over selected NPCs
        for index in selected_indexes:
            row = index.row()

            # Assuming column 0 is "Dialog ID" and column 2 is "English Dialogue"
            dialog_id = self.model.table_data[row][self.display_columns.index(0)]
            current_dialogue = self.model.table_data[row][self.display_columns.index(2)]

            # Prompt user for NPC details
            npc_name, ok = QInputDialog.getText(self, "NPC Name", f"Enter the name for NPC with Dialog ID {dialog_id}:")
            if not ok or not npc_name.strip():
                QMessageBox.warning(self, "Input Required", "NPC name cannot be empty.")
                continue
            npc_name = npc_name.strip()

            npc_role, ok = QInputDialog.getText(self, "NPC Role",
                                                f"Enter the role for NPC '{npc_name}' (e.g., Quest Giver, Store Owner):")
            if not ok or not npc_role.strip():
                QMessageBox.warning(self, "Input Required", "NPC role cannot be empty.")
                continue
            npc_role = npc_role.strip()

            # Optional context
            context, ok = QInputDialog.getText(self, "Dialogue Context",
                                               f"Provide context for NPC '{npc_name}' (optional):")
            if not ok:
                context = None
            else:
                context = context.strip() if context.strip() else None

            # Generate dialogue using selected model
            dialogue = self.ltb.generate_dialogue(npc_role, npc_name, context, use_assistant)
            if dialogue:
                self.model.table_data[row][self.display_columns.index(2)] = dialogue
                model_index = self.model.index(row, self.display_columns.index(2))
                self.model.dataChanged.emit(model_index, model_index, [Qt.DisplayRole, Qt.EditRole])
                logging.info(f"Dialogue generated for NPC '{npc_name}' (Dialog ID {dialog_id}) using {model_choice}.")
            else:
                QMessageBox.critical(self, "Generation Failed",
                                     f"Failed to generate dialogue for NPC '{npc_name}' (Dialog ID {dialog_id}). Check logs for details.")

        self.statusBar().showMessage(f"Dialogue generation completed using {model_choice}.")